"""Dashboard screen -- at-a-glance financial overview."""

from __future__ import annotations

import json
import logging
from decimal import Decimal

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Label, Static
from textual.worker import Worker, WorkerState

from ws_accounting.core.hledger import (
    HLedgerError,
    HLedgerGateway,
    HLedgerNotFoundError,
)
from ws_accounting.core.parser import (
    parse_amount,
    parse_balance_report,
    parse_register,
)
from ws_accounting.widgets.quick_actions import QuickActions
from ws_accounting.widgets.summary_card import SummaryCard

log = logging.getLogger(__name__)


class DashboardScreen(Screen):
    """Home screen with financial overview, budget bars, recent txns."""

    CSS_PATH = "../styles/dashboard.tcss"

    BINDINGS = []

    def __init__(self, gateway: HLedgerGateway | None = None, **kwargs):
        super().__init__(**kwargs)
        self._gateway = gateway
        self._has_data = False

    def compose(self) -> ComposeResult:
        # Summary cards row
        with Horizontal(id="summary-cards"):
            yield SummaryCard(
                "Net Worth",
                show_sign=False,
                id="card-net-worth",
            )
            yield SummaryCard(
                "Monthly Income",
                show_sign=False,
                id="card-income",
            )
            yield SummaryCard(
                "Monthly Expenses",
                show_sign=False,
                id="card-expenses",
            )
            yield SummaryCard(
                "Monthly Net",
                show_sign=True,
                id="card-net",
            )

        # Main content area: budgets (left) + recent txns (right)
        with Horizontal(id="dashboard-body"):
            with Vertical(id="budget-section"):
                yield Label(
                    "Budget Status",
                    classes="section-title",
                )
                yield Container(id="budget-bars")

            with Vertical(id="recent-section"):
                yield Label(
                    "Recent Transactions",
                    classes="section-title",
                )
                yield Container(id="recent-txns")

        # Quick actions row
        yield QuickActions(id="quick-actions")

        # Empty state overlay (hidden when data exists)
        yield Container(
            Static(
                "Welcome to ws-accounting!\n\n"
                "No financial data found yet. "
                "Import a CSV or add a transaction to get started.",
                id="empty-msg",
            ),
            id="empty-state",
        )

    def on_mount(self) -> None:
        """Kick off data loading when the screen is mounted."""
        if self._gateway is not None:
            self._load_data()

    def set_gateway(self, gateway: HLedgerGateway) -> None:
        """Set the hledger gateway and trigger a data reload."""
        self._gateway = gateway
        if self.is_mounted:
            self._load_data()

    def _load_data(self) -> None:
        """Spawn async workers to fetch all dashboard data."""
        self.run_worker(
            self._fetch_all_data(),
            name="dashboard-data",
            exclusive=True,
        )

    async def _fetch_all_data(self) -> None:
        """Fetch net worth, income/expenses, budgets, recent txns."""
        if self._gateway is None:
            return

        journal = self._gateway.journal_path
        if not journal.exists():
            self._show_empty_state()
            return

        try:
            await self._gateway.check_installation()
        except (HLedgerNotFoundError, HLedgerError) as exc:
            log.warning("hledger not available: %s", exc)
            self._show_empty_state()
            return

        # Fetch all data, tolerating individual failures
        await self._fetch_net_worth()
        await self._fetch_monthly()
        await self._fetch_budgets()
        await self._fetch_recent()

    async def _fetch_net_worth(self) -> None:
        """Fetch net worth = assets + liabilities."""
        try:
            raw = await self._gateway.balance(
                accounts=["assets", "liabilities"],
            )
            data = json.loads(raw)
            balances = parse_balance_report(data)
            total = Decimal("0")
            commodity = "$"
            for bal in balances:
                # Assets are positive, liabilities negative in hledger
                total += bal.balance.quantity
                commodity = bal.balance.commodity
            card = self.query_one("#card-net-worth", SummaryCard)
            card.update_amount(total, commodity)
            self._has_data = True
        except Exception as exc:
            log.debug("Failed to fetch net worth: %s", exc)

    async def _fetch_monthly(self) -> None:
        """Fetch monthly income and expenses."""
        try:
            raw = await self._gateway.income_statement(
                period="thismonth",
            )
            data = json.loads(raw)
            income_total = Decimal("0")
            expense_total = Decimal("0")
            commodity = "$"

            # hledger incomestatement JSON is a compound balance report:
            # {"cbrSubreports": [["Title", {prTotals: ...}, bool], ...], ...}
            for subreport in data.get("cbrSubreports", []):
                if not isinstance(subreport, list) or len(subreport) < 2:
                    continue
                title = subreport[0].lower()
                report_data = subreport[1]
                if not isinstance(report_data, dict):
                    continue
                totals = report_data.get("prTotals", {})
                row_totals = totals.get("prrTotal", [])
                if row_totals:
                    amt = parse_amount(row_totals[0])
                    commodity = amt.commodity
                    if "income" in title or "revenue" in title:
                        income_total = abs(amt.quantity)
                    elif "expense" in title:
                        expense_total = abs(amt.quantity)

            card_income = self.query_one(
                "#card-income", SummaryCard
            )
            card_income.update_amount(income_total, commodity)

            card_expenses = self.query_one(
                "#card-expenses", SummaryCard
            )
            card_expenses.update_amount(expense_total, commodity)

            net = income_total - expense_total
            card_net = self.query_one("#card-net", SummaryCard)
            card_net.update_amount(net, commodity)
            self._has_data = True
        except Exception as exc:
            log.debug("Failed to fetch monthly data: %s", exc)

    async def _fetch_budgets(self) -> None:
        """Fetch budget status for the current month."""
        try:
            raw = await self._gateway.balance(
                budget=True,
                period="thismonth",
            )
            data = json.loads(raw)
            balances = parse_balance_report(data)

            container = self.query_one("#budget-bars", Container)
            container.remove_children()

            if not balances:
                container.mount(
                    Static(
                        "No budgets configured",
                        classes="muted-text",
                    )
                )
                return

            # Show up to 5 budget bars
            for bal in balances[:5]:
                name = bal.account.split(":")[-1].title()
                spent = abs(bal.balance.quantity)
                # Budget bars are a simplified display
                bar_widget = BudgetBar(
                    name=name,
                    spent=spent,
                )
                container.mount(bar_widget)
            self._has_data = True
        except Exception as exc:
            log.debug("Failed to fetch budgets: %s", exc)
            container = self.query_one("#budget-bars", Container)
            container.remove_children()
            container.mount(
                Static(
                    "Budget data unavailable",
                    classes="muted-text",
                )
            )

    async def _fetch_recent(self) -> None:
        """Fetch the last 5 transactions."""
        try:
            raw = await self._gateway.print_journal(json_format=True)
            data = json.loads(raw)
            all_txns = parse_register(data)
            transactions = all_txns[-5:] if len(all_txns) > 5 else all_txns

            container = self.query_one("#recent-txns", Container)
            container.remove_children()

            if not transactions:
                container.mount(
                    Static(
                        "No transactions yet",
                        classes="muted-text",
                    )
                )
                return

            for txn in reversed(transactions):
                desc = txn.description
                if txn.payee:
                    desc = f"{txn.payee} | {desc}"
                date_str = txn.date.isoformat()

                # Compute net amount from postings
                amt_str = ""
                for posting in txn.postings:
                    if (
                        posting.amount
                        and not posting.account.startswith("assets")
                        and not posting.account.startswith(
                            "liabilities"
                        )
                    ):
                        q = posting.amount.quantity
                        c = posting.amount.commodity
                        sign = "+" if q >= 0 else "-"
                        amt_str = (
                            f"{sign}{c}{abs(q):,.2f}"
                        )
                        break

                row_text = (
                    f"{date_str}  {desc:<30s}  {amt_str}"
                )
                container.mount(
                    Static(row_text, classes="txn-row")
                )
            self._has_data = True
        except Exception as exc:
            log.debug("Failed to fetch recent txns: %s", exc)
            container = self.query_one("#recent-txns", Container)
            container.remove_children()
            container.mount(
                Static(
                    "Transaction data unavailable",
                    classes="muted-text",
                )
            )

    def _show_empty_state(self) -> None:
        """Show the empty state overlay and hide data sections."""
        try:
            empty = self.query_one("#empty-state")
            empty.display = True
            body = self.query_one("#dashboard-body")
            body.display = False
        except Exception:
            pass

    def _hide_empty_state(self) -> None:
        """Hide the empty state overlay and show data sections."""
        try:
            empty = self.query_one("#empty-state")
            empty.display = False
            body = self.query_one("#dashboard-body")
            body.display = True
        except Exception:
            pass

    def on_worker_state_changed(
        self, event: Worker.StateChanged
    ) -> None:
        """Toggle empty state based on whether we loaded data."""
        if event.worker.name != "dashboard-data":
            return
        if event.state == WorkerState.SUCCESS:
            if self._has_data:
                self._hide_empty_state()
            else:
                self._show_empty_state()

    def on_quick_actions_import_csv(
        self, event: QuickActions.ImportCSV
    ) -> None:
        """Handle import CSV quick action."""
        self.app.action_switch_screen("csv_import")

    def on_quick_actions_new_transaction(
        self, event: QuickActions.NewTransaction
    ) -> None:
        """Handle new transaction quick action."""
        self.app.action_new_transaction()

    def on_quick_actions_view_accounts(
        self, event: QuickActions.ViewAccounts
    ) -> None:
        """Handle view accounts quick action."""
        self.app.action_switch_screen("accounts")


class BudgetBar(Static):
    """A single budget progress bar with label."""

    DEFAULT_CSS = """
    BudgetBar {
        height: 2;
        margin-bottom: 1;
        layout: horizontal;
    }
    BudgetBar .budget-label {
        width: 16;
        text-style: bold;
    }
    BudgetBar .budget-amount {
        width: 14;
        text-align: right;
    }
    BudgetBar ProgressBar {
        width: 1fr;
    }
    """

    def __init__(
        self,
        name: str,
        spent: Decimal,
        budget: Decimal | None = None,
        **kwargs,
    ) -> None:
        self._bar_name = name
        self._spent = spent
        self._budget = budget or Decimal("0")
        super().__init__(**kwargs)

    def compose(self) -> ComposeResult:
        yield Label(
            self._bar_name, classes="budget-label"
        )
        yield Label(
            f"${self._spent:,.2f}",
            classes="budget-amount",
        )
