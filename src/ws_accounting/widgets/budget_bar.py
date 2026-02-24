"""Budget progress bar widget with color gradient and status icons."""

from __future__ import annotations

from decimal import Decimal

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Input, Label, ProgressBar, Static


# Threshold constants for color changes
_THRESHOLD_WARN = 0.75
_THRESHOLD_DANGER = 0.90


class BudgetBar(Widget):
    """A single budget row: category, amounts, and a colored progress bar.

    Color scheme (accessible blue/amber/orange, no red/green):
      - 0-75%:  blue (normal)
      - 75-90%: amber (warning)
      - 90%+:   orange (danger / exceeded)
    """

    DEFAULT_CSS = """
    BudgetBar {
        height: 3;
        padding: 0 1;
    }
    BudgetBar .budget-row {
        height: 1;
        width: 1fr;
    }
    BudgetBar .budget-category {
        width: 24;
        text-style: bold;
    }
    BudgetBar .budget-amounts {
        width: 30;
        text-align: right;
    }
    BudgetBar .budget-remaining {
        width: 14;
        text-align: right;
    }
    BudgetBar .budget-status-icon {
        width: 3;
        text-align: center;
    }
    BudgetBar .budget-pct {
        width: 6;
        text-align: right;
    }
    BudgetBar ProgressBar {
        width: 1fr;
        margin: 0 1;
    }
    BudgetBar .bar-normal ProgressBar > .bar--bar {
        color: $primary;
    }
    BudgetBar .bar-warn ProgressBar > .bar--bar {
        color: $warning;
    }
    BudgetBar .bar-danger ProgressBar > .bar--bar {
        color: $error;
    }
    BudgetBar .edit-input {
        display: none;
        width: 14;
    }
    BudgetBar .edit-input.visible {
        display: block;
    }
    """

    category: reactive[str] = reactive("")
    budgeted: reactive[Decimal] = reactive(Decimal("0"))
    spent: reactive[Decimal] = reactive(Decimal("0"))
    percentage: reactive[float] = reactive(0.0)
    is_editing: reactive[bool] = reactive(False)

    class BudgetEdited(Message):
        """Emitted when the user edits a budget amount inline."""

        def __init__(
            self,
            category: str,
            new_amount: Decimal,
        ) -> None:
            self.category = category
            self.new_amount = new_amount
            super().__init__()

    def __init__(
        self,
        category: str = "",
        budgeted: Decimal = Decimal("0"),
        spent: Decimal = Decimal("0"),
        percentage: float = 0.0,
        commodity: str = "$",
        rollover: Decimal = Decimal("0"),
        **kwargs,
    ) -> None:
        self._commodity = commodity
        self._rollover = rollover
        super().__init__(**kwargs)
        self.category = category
        self.budgeted = budgeted
        self.spent = spent
        self.percentage = percentage

    def compose(self) -> ComposeResult:
        remaining = self.budgeted - self.spent
        pct_int = min(999, max(0, int(self.percentage * 100)))
        icon = self._status_icon()

        with Horizontal(classes="budget-row"):
            yield Label(
                self.category.split(":")[-1].title(),
                classes="budget-category",
            )
            yield Label(
                self._fmt_amounts(),
                classes="budget-amounts",
                id="amounts-label",
            )
            yield Label(
                self._fmt_remaining(remaining),
                classes="budget-remaining",
                id="remaining-label",
            )
            yield Input(
                placeholder="Amount",
                id="edit-amount",
                classes="edit-input",
            )

        with Horizontal(classes="budget-row"):
            bar_class = self._bar_class()
            with Horizontal(classes=bar_class, id="bar-container"):
                yield ProgressBar(
                    total=100,
                    show_eta=False,
                    show_percentage=False,
                    id="progress",
                )
            yield Label(
                f"{pct_int}%",
                classes="budget-pct",
                id="pct-label",
            )
            yield Static(icon, classes="budget-status-icon", id="icon")

    def on_mount(self) -> None:
        """Set the initial progress bar value."""
        bar = self.query_one("#progress", ProgressBar)
        bar.update(progress=min(100, max(0, self.percentage * 100)))

    def _fmt_amounts(self) -> str:
        """Format 'spent / budgeted' display."""
        c = self._commodity
        s = f"{self.spent:,.2f}"
        b = f"{self.budgeted:,.2f}"
        return f"{c}{s} / {c}{b}"

    def _fmt_remaining(self, remaining: Decimal) -> str:
        """Format remaining amount with sign."""
        c = self._commodity
        if remaining >= 0:
            return f"{c}{remaining:,.2f}"
        return f"-{c}{abs(remaining):,.2f}"

    def _bar_class(self) -> str:
        """Return CSS class name based on percentage thresholds."""
        if self.percentage >= _THRESHOLD_DANGER:
            return "bar-danger"
        if self.percentage >= _THRESHOLD_WARN:
            return "bar-warn"
        return "bar-normal"

    def _status_icon(self) -> str:
        """Return a status icon string based on spending level."""
        if self.percentage > 1.0:
            return "!"
        if self.percentage >= _THRESHOLD_DANGER:
            return "\u26a0"  # Warning sign
        return " "

    def update_values(
        self,
        budgeted: Decimal,
        spent: Decimal,
        percentage: float,
    ) -> None:
        """Update the bar values and refresh the display."""
        self.budgeted = budgeted
        self.spent = spent
        self.percentage = percentage
        self._refresh_display()

    def _refresh_display(self) -> None:
        """Refresh all child widget values."""
        if not self.is_mounted:
            return

        remaining = self.budgeted - self.spent
        pct_int = min(999, max(0, int(self.percentage * 100)))

        try:
            self.query_one(
                "#amounts-label", Label
            ).update(self._fmt_amounts())
            self.query_one(
                "#remaining-label", Label
            ).update(self._fmt_remaining(remaining))
            self.query_one("#pct-label", Label).update(f"{pct_int}%")
            self.query_one("#icon", Static).update(
                self._status_icon()
            )

            bar = self.query_one("#progress", ProgressBar)
            bar.update(
                progress=min(100, max(0, self.percentage * 100))
            )

            # Update bar color class
            container = self.query_one("#bar-container", Horizontal)
            container.remove_class(
                "bar-normal", "bar-warn", "bar-danger"
            )
            container.add_class(self._bar_class())
        except Exception:
            pass

    def on_key(self, event) -> None:
        """Enter key toggles inline editing."""
        if event.key == "enter" and not self.is_editing:
            self._start_edit()
            event.stop()

    def _start_edit(self) -> None:
        """Show the inline amount editor."""
        self.is_editing = True
        try:
            edit_input = self.query_one("#edit-amount", Input)
            edit_input.add_class("visible")
            edit_input.value = str(self.budgeted)
            edit_input.focus()
        except Exception:
            self.is_editing = False

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle inline edit submission."""
        if event.input.id != "edit-amount":
            return
        text = event.value.strip().replace(",", "").lstrip("$")
        try:
            new_amount = Decimal(text)
            self.post_message(
                self.BudgetEdited(
                    category=self.category,
                    new_amount=new_amount,
                )
            )
        except Exception:
            self.notify(
                "Invalid amount", severity="warning"
            )
        self._end_edit()
        event.stop()

    def _end_edit(self) -> None:
        """Hide the inline editor."""
        self.is_editing = False
        try:
            edit_input = self.query_one("#edit-amount", Input)
            edit_input.remove_class("visible")
        except Exception:
            pass
