"""Budgets screen -- budget tracking, savings goals, and recurring bills."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import (
    Horizontal,
    ScrollableContainer,
    Vertical,
)
from textual.screen import ModalScreen, Screen
from textual.widgets import (
    Button,
    Footer,
    Input,
    Label,
    Static,
    Switch,
)

from ws_accounting.core.budget import (
    BudgetStatus,
    calculate_budget_status,
    calculate_rollover,
)
from ws_accounting.db.database import Database
from ws_accounting.db.models import Budget, Goal, RecurringTransaction
from ws_accounting.db.queries import (
    delete_budget,
    get_budgets,
    get_due_recurring,
    get_goals,
    upsert_budget,
)
from ws_accounting.widgets.budget_bar import BudgetBar
from ws_accounting.widgets.nav_header import NavHeader

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _current_month() -> str:
    """Return current month as YYYY-MM."""
    return date.today().strftime("%Y-%m")


def _prev_month(month_str: str) -> str:
    """Return the previous month as YYYY-MM."""
    year, month = int(month_str[:4]), int(month_str[5:7])
    if month == 1:
        return f"{year - 1:04d}-12"
    return f"{year:04d}-{month - 1:02d}"


def _month_display(month_str: str) -> str:
    """Format YYYY-MM as 'January 2026' for display."""
    try:
        year, month = int(month_str[:4]), int(month_str[5:7])
        d = date(year, month, 1)
        return d.strftime("%B %Y")
    except Exception:
        return month_str


def _upcoming_window() -> str:
    """Return ISO date string 7 days from today."""
    return (date.today() + timedelta(days=7)).isoformat()


# ---------------------------------------------------------------------------
# Add/Edit Budget Modal
# ---------------------------------------------------------------------------


class AddBudgetModal(ModalScreen[dict | None]):
    """Modal dialog for adding or editing a budget category."""

    DEFAULT_CSS = """
    AddBudgetModal {
        align: center middle;
    }
    #add-budget-container {
        width: 60;
        max-width: 90%;
        height: auto;
        background: $surface;
        border: round $primary;
        padding: 1 2;
    }
    #add-budget-header {
        text-style: bold;
        margin-bottom: 1;
        width: 1fr;
    }
    .form-row {
        height: auto;
        margin-bottom: 1;
    }
    .form-label {
        width: 16;
        text-style: bold;
        color: $text-muted;
        padding-top: 1;
    }
    .form-field {
        width: 1fr;
    }
    #modal-buttons {
        height: 3;
        align: right middle;
        margin-top: 1;
    }
    #modal-buttons Button {
        margin-left: 1;
    }
    .rollover-row {
        height: 3;
        margin-bottom: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
    ]

    def __init__(
        self,
        month: str,
        existing: Budget | None = None,
    ) -> None:
        self._month = month
        self._existing = existing
        super().__init__()

    def compose(self) -> ComposeResult:
        title = (
            "Edit Budget" if self._existing else "Add Budget"
        )
        cat_value = (
            self._existing.category if self._existing else ""
        )
        amt_value = (
            self._existing.amount if self._existing else ""
        )
        rollover_on = (
            self._existing.rollover
            if self._existing
            else False
        )
        cap_value = (
            self._existing.rollover_cap or ""
            if self._existing
            else ""
        )

        with Vertical(id="add-budget-container"):
            yield Static(title, id="add-budget-header")

            with Horizontal(classes="form-row"):
                yield Static("Category", classes="form-label")
                yield Input(
                    value=cat_value,
                    placeholder="expenses:food:groceries",
                    id="input-category",
                    classes="form-field",
                    disabled=self._existing is not None,
                )

            with Horizontal(classes="form-row"):
                yield Static("Amount", classes="form-label")
                yield Input(
                    value=amt_value,
                    placeholder="600.00",
                    id="input-amount",
                    classes="form-field",
                )

            with Horizontal(classes="rollover-row"):
                yield Static(
                    "Rollover", classes="form-label"
                )
                yield Switch(
                    value=rollover_on, id="switch-rollover"
                )

            with Horizontal(classes="form-row"):
                yield Static(
                    "Rollover Cap", classes="form-label"
                )
                yield Input(
                    value=cap_value,
                    placeholder="(optional) e.g. 200.00",
                    id="input-rollover-cap",
                    classes="form-field",
                )

            with Horizontal(id="modal-buttons"):
                yield Button(
                    "Cancel",
                    variant="default",
                    id="btn-modal-cancel",
                )
                yield Button(
                    "Save",
                    variant="primary",
                    id="btn-modal-save",
                )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-modal-save":
            self._save()
        elif event.button.id == "btn-modal-cancel":
            self.action_cancel()

    def _save(self) -> None:
        """Validate and dismiss with result dict."""
        cat = self.query_one("#input-category", Input).value.strip()
        amt_raw = (
            self.query_one("#input-amount", Input)
            .value.strip()
            .replace(",", "")
            .lstrip("$")
        )
        rollover = self.query_one(
            "#switch-rollover", Switch
        ).value
        cap_raw = (
            self.query_one("#input-rollover-cap", Input)
            .value.strip()
            .replace(",", "")
            .lstrip("$")
        )

        if not cat:
            self.notify(
                "Category is required.", severity="warning"
            )
            return
        try:
            Decimal(amt_raw)
        except (InvalidOperation, ValueError):
            self.notify(
                "Invalid amount.", severity="warning"
            )
            return

        cap: str | None = None
        if cap_raw:
            try:
                Decimal(cap_raw)
                cap = cap_raw
            except (InvalidOperation, ValueError):
                self.notify(
                    "Invalid rollover cap.",
                    severity="warning",
                )
                return

        self.dismiss({
            "category": cat,
            "amount": amt_raw,
            "rollover": rollover,
            "rollover_cap": cap,
        })

    def action_cancel(self) -> None:
        self.dismiss(None)


# ---------------------------------------------------------------------------
# Main Budgets Screen
# ---------------------------------------------------------------------------


class BudgetsScreen(Screen):
    """Budget tracking, savings goals, and upcoming recurring bills."""

    CSS_PATH = "../styles/budgets.tcss"

    BINDINGS = [
        Binding(
            "a",
            "add_budget",
            "Add Budget",
            show=True,
        ),
        Binding(
            "d",
            "delete_budget",
            "Delete",
            show=True,
        ),
        Binding(
            "r",
            "refresh_data",
            "Refresh",
            show=True,
        ),
    ]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._db: Database | None = None
        self._month: str = _current_month()
        self._budgets: list[Budget] = []
        self._budget_statuses: list[BudgetStatus] = []
        self._goals: list[Goal] = []
        self._recurring: list[RecurringTransaction] = []

    def compose(self) -> ComposeResult:
        yield NavHeader()

        # Header row: title + month navigation
        with Horizontal(id="budgets-header"):
            yield Static(
                "Budgets", id="budgets-title"
            )
            yield Button(
                "\u25c0", id="btn-prev-month", classes="month-nav"
            )
            yield Static(
                _month_display(self._month),
                id="month-label",
            )
            yield Button(
                "\u25b6", id="btn-next-month", classes="month-nav"
            )
            yield Button(
                "+ Add Budget",
                variant="primary",
                id="btn-add-budget",
            )

        # Summary stats row
        with Horizontal(id="budget-summary"):
            yield Static(
                "Total Budgeted: $0.00",
                id="total-budgeted",
                classes="summary-stat",
            )
            yield Static(
                "Total Spent: $0.00",
                id="total-spent",
                classes="summary-stat",
            )
            yield Static(
                "Total Remaining: $0.00",
                id="total-remaining",
                classes="summary-stat",
            )

        # Main scrollable area: budget bars
        with ScrollableContainer(id="budgets-list"):
            yield Static(
                "No budgets configured for this month.\n\n"
                "Press 'a' or click '+ Add Budget' to create one.",
                id="budgets-empty",
            )

        # Lower section: goals + recurring
        with Horizontal(id="budgets-lower"):
            with Vertical(id="goals-section"):
                yield Label(
                    "Savings Goals",
                    classes="section-title",
                )
                yield ScrollableContainer(id="goals-list")

            with Vertical(id="recurring-section"):
                yield Label(
                    "Upcoming Bills (7 days)",
                    classes="section-title",
                )
                yield ScrollableContainer(id="recurring-list")

        yield Footer()

    def on_mount(self) -> None:
        """Load data on mount."""
        self.query_one(NavHeader).set_active("budgets")
        # Grab the database from the app if not already set
        if self._db is None and hasattr(self.app, "database"):
            self._db = self.app.database
        self._load_data()

    def set_database(self, db: Database) -> None:
        """Set or replace the database and reload."""
        self._db = db
        if self.is_mounted:
            self._load_data()

    # ---- Data loading ------------------------------------------------

    def _load_data(self) -> None:
        """Load all budget, goal, and recurring data."""
        if self._db is None:
            return

        self._budgets = get_budgets(self._db, self._month)
        self._budget_statuses = self._compute_statuses()
        self._goals = get_goals(self._db)
        self._recurring = get_due_recurring(
            self._db, _upcoming_window()
        )

        self._render_budget_bars()
        self._render_summary()
        self._render_goals()
        self._render_recurring()
        self._update_month_label()

    def _compute_statuses(self) -> list[BudgetStatus]:
        """Compute BudgetStatus for each budget category."""
        statuses: list[BudgetStatus] = []
        prev_month = _prev_month(self._month)
        prev_budgets = (
            get_budgets(self._db, prev_month)
            if self._db
            else []
        )
        prev_map = {b.category: b for b in prev_budgets}

        for budget in self._budgets:
            budgeted = Decimal(budget.amount)
            # Spending data would come from hledger in a full
            # integration.  Here we default to 0 and let the
            # screen's ``set_spending`` helper populate it.
            spent = Decimal("0")

            rollover = Decimal("0")
            if budget.rollover:
                prev = prev_map.get(budget.category)
                if prev is not None:
                    prev_budgeted = Decimal(prev.amount)
                    cap = (
                        Decimal(prev.rollover_cap)
                        if prev.rollover_cap
                        else None
                    )
                    rollover = calculate_rollover(
                        prev_budgeted,
                        Decimal("0"),  # prev spent unknown
                        cap,
                    )

            cap = (
                Decimal(budget.rollover_cap)
                if budget.rollover_cap
                else None
            )
            status = calculate_budget_status(
                category=budget.category,
                budgeted=budgeted,
                spent=spent,
                rollover=rollover,
                rollover_cap=cap,
            )
            statuses.append(status)

        return statuses

    def set_spending(
        self, spending: dict[str, Decimal]
    ) -> None:
        """Inject actual spending data (e.g. from hledger balance).

        Args:
            spending: Mapping of category -> spent amount.
        """
        updated: list[BudgetStatus] = []
        prev_month = _prev_month(self._month)
        prev_budgets = (
            get_budgets(self._db, prev_month)
            if self._db
            else []
        )
        prev_map = {b.category: b for b in prev_budgets}

        for budget in self._budgets:
            budgeted = Decimal(budget.amount)
            spent = spending.get(budget.category, Decimal("0"))

            rollover = Decimal("0")
            if budget.rollover:
                prev = prev_map.get(budget.category)
                if prev is not None:
                    prev_budgeted = Decimal(prev.amount)
                    prev_spent = spending.get(
                        prev.category, Decimal("0")
                    )
                    cap = (
                        Decimal(prev.rollover_cap)
                        if prev.rollover_cap
                        else None
                    )
                    rollover = calculate_rollover(
                        prev_budgeted, prev_spent, cap
                    )

            cap = (
                Decimal(budget.rollover_cap)
                if budget.rollover_cap
                else None
            )
            status = calculate_budget_status(
                category=budget.category,
                budgeted=budgeted,
                spent=spent,
                rollover=rollover,
                rollover_cap=cap,
            )
            updated.append(status)

        self._budget_statuses = updated
        self._render_budget_bars()
        self._render_summary()

    # ---- Rendering ---------------------------------------------------

    def _render_budget_bars(self) -> None:
        """Populate the budget list with BudgetBar widgets."""
        try:
            container = self.query_one(
                "#budgets-list", ScrollableContainer
            )
        except Exception:
            return

        container.remove_children()

        if not self._budget_statuses:
            container.mount(
                Static(
                    "No budgets configured for this month.\n\n"
                    "Press 'a' or click '+ Add Budget'"
                    " to create one.",
                    id="budgets-empty",
                )
            )
            return

        for status in self._budget_statuses:
            bar = BudgetBar(
                category=status.category,
                budgeted=status.budgeted,
                spent=status.spent,
                percentage=status.percentage,
            )
            container.mount(bar)

    def _render_summary(self) -> None:
        """Update the summary stats."""
        total_budgeted = sum(
            (s.budgeted for s in self._budget_statuses),
            Decimal("0"),
        )
        total_spent = sum(
            (s.spent for s in self._budget_statuses),
            Decimal("0"),
        )
        total_remaining = total_budgeted - total_spent

        try:
            self.query_one("#total-budgeted", Static).update(
                f"Total Budgeted: ${total_budgeted:,.2f}"
            )
            self.query_one("#total-spent", Static).update(
                f"Total Spent: ${total_spent:,.2f}"
            )
            self.query_one("#total-remaining", Static).update(
                f"Total Remaining: ${total_remaining:,.2f}"
            )
        except Exception:
            pass

    def _render_goals(self) -> None:
        """Populate the goals section."""
        try:
            container = self.query_one(
                "#goals-list", ScrollableContainer
            )
        except Exception:
            return

        container.remove_children()

        if not self._goals:
            container.mount(
                Static(
                    "No savings goals set.",
                    classes="muted-text",
                )
            )
            return

        for goal in self._goals:
            target = Decimal(goal.target_amount)
            current = Decimal(goal.current_amount)
            pct = (
                float(current / target) * 100
                if target > 0
                else 0.0
            )
            pct_clamped = min(100.0, max(0.0, pct))
            text = (
                f"{goal.name}: ${current:,.2f}"
                f" / ${target:,.2f}"
                f" ({pct_clamped:.0f}%)"
            )
            if goal.target_date:
                text += f"  due {goal.target_date}"
            container.mount(
                Static(text, classes="goal-row")
            )

    def _render_recurring(self) -> None:
        """Populate the upcoming recurring bills section."""
        try:
            container = self.query_one(
                "#recurring-list", ScrollableContainer
            )
        except Exception:
            return

        container.remove_children()

        if not self._recurring:
            container.mount(
                Static(
                    "No upcoming bills.",
                    classes="muted-text",
                )
            )
            return

        for rec in self._recurring:
            text = (
                f"{rec.next_due}  {rec.description}"
                f"  ${Decimal(rec.amount):,.2f}"
                f"  ({rec.frequency})"
            )
            container.mount(
                Static(text, classes="recurring-row")
            )

    def _update_month_label(self) -> None:
        """Update the month display label."""
        try:
            self.query_one("#month-label", Static).update(
                _month_display(self._month)
            )
        except Exception:
            pass

    # ---- Event handlers ----------------------------------------------

    def on_button_pressed(
        self, event: Button.Pressed
    ) -> None:
        if event.button.id == "btn-add-budget":
            self.action_add_budget()
        elif event.button.id == "btn-prev-month":
            self._navigate_month(-1)
        elif event.button.id == "btn-next-month":
            self._navigate_month(1)

    def on_budget_bar_budget_edited(
        self, event: BudgetBar.BudgetEdited
    ) -> None:
        """Handle inline budget edit from a BudgetBar."""
        if self._db is None:
            return
        # Find existing budget for rollover state
        existing = next(
            (
                b
                for b in self._budgets
                if b.category == event.category
            ),
            None,
        )
        rollover = existing.rollover if existing else False
        cap = existing.rollover_cap if existing else None

        upsert_budget(
            self._db,
            category=event.category,
            month=self._month,
            amount=str(event.new_amount),
            rollover=rollover,
            rollover_cap=cap,
        )
        self.notify(
            f"Updated {event.category} to"
            f" ${event.new_amount:,.2f}",
            title="Budget Updated",
        )
        self._load_data()

    # ---- Actions -----------------------------------------------------

    def action_add_budget(self) -> None:
        """Open the add budget modal."""
        self.app.push_screen(
            AddBudgetModal(month=self._month),
            callback=self._on_add_budget_result,
        )

    def _on_add_budget_result(
        self, result: dict | None
    ) -> None:
        """Handle modal result from add/edit budget."""
        if result is None or self._db is None:
            return
        upsert_budget(
            self._db,
            category=result["category"],
            month=self._month,
            amount=result["amount"],
            rollover=result["rollover"],
            rollover_cap=result.get("rollover_cap"),
        )
        self.notify(
            f"Budget saved for {result['category']}",
            title="Budget Saved",
        )
        self._load_data()

    def action_delete_budget(self) -> None:
        """Delete the currently focused budget."""
        if not self._budgets or self._db is None:
            self.notify(
                "No budget to delete.",
                severity="warning",
            )
            return

        # Find which BudgetBar has focus
        focused = self.focused
        if focused is not None:
            # Walk up to find the BudgetBar ancestor
            widget = focused
            while widget is not None and not isinstance(
                widget, BudgetBar
            ):
                widget = widget.parent
            if isinstance(widget, BudgetBar):
                cat = widget.category
                budget = next(
                    (
                        b
                        for b in self._budgets
                        if b.category == cat
                    ),
                    None,
                )
                if budget and budget.id is not None:
                    delete_budget(self._db, budget.id)
                    self.notify(
                        f"Deleted budget for {cat}",
                        title="Budget Deleted",
                    )
                    self._load_data()
                    return

        # Fallback: delete the last budget in the list
        last = self._budgets[-1]
        if last.id is not None:
            delete_budget(self._db, last.id)
            self.notify(
                f"Deleted budget for {last.category}",
                title="Budget Deleted",
            )
            self._load_data()

    def action_refresh_data(self) -> None:
        """Reload all data."""
        self._load_data()
        self.notify("Data refreshed", title="Budgets")

    def _navigate_month(self, delta: int) -> None:
        """Move forward or backward by one month."""
        year, month = (
            int(self._month[:4]),
            int(self._month[5:7]),
        )
        month += delta
        if month < 1:
            month = 12
            year -= 1
        elif month > 12:
            month = 1
            year += 1
        self._month = f"{year:04d}-{month:02d}"
        self._load_data()
