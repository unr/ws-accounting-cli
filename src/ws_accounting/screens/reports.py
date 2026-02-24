"""Reports screen -- financial charts and data analysis."""

from __future__ import annotations

import json
import logging
from datetime import date
from decimal import Decimal

from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import (
    DataTable,
    Footer,
    Label,
    Static,
    TabbedContent,
    TabPane,
)
from textual_plotext import PlotextPlot

from ws_accounting.core.hledger import (
    HLedgerError,
    HLedgerGateway,
    HLedgerNotFoundError,
)
from ws_accounting.core.parser import parse_amount, parse_balance_report
from ws_accounting.widgets.nav_header import NavHeader
from ws_accounting.widgets.period_selector import PeriodSelector

log = logging.getLogger(__name__)

# Accessible colors: blue/orange palette (not red/green)
COLOR_INCOME = "dodger_blue"
COLOR_EXPENSE = "orange"
COLOR_NET_WORTH = "dodger_blue"
COLOR_BAR = "orange"


def _month_label(year: int, month: int) -> str:
    """Return short month label like 'Jan', 'Feb', etc."""
    months = [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    ]
    return months[month - 1]


def _month_range(
    num_months: int,
) -> list[tuple[int, int]]:
    """Return a list of (year, month) tuples for the last N months.

    Includes the current month as the final element.
    """
    today = date.today()
    result: list[tuple[int, int]] = []
    for i in range(num_months - 1, -1, -1):
        month = today.month - i
        year = today.year
        while month <= 0:
            month += 12
            year -= 1
        result.append((year, month))
    return result


def _month_ranges_period(num_months: int) -> str:
    """Build an hledger period string for the last N months."""
    today = date.today()
    # Calculate start date: go back num_months months
    start_year = today.year
    start_month = today.month - num_months + 1
    while start_month <= 0:
        start_month += 12
        start_year -= 1
    start = date(start_year, start_month, 1)
    # End is first of next month
    end_year = today.year
    end_month = today.month + 1
    if end_month > 12:
        end_month = 1
        end_year += 1
    end = date(end_year, end_month, 1)
    return f"monthly from {start.isoformat()} to {end.isoformat()}"


class ReportsScreen(Screen):
    """Financial reports with charts -- Net Worth, Spending, Cash Flow."""

    CSS_PATH = "../styles/reports.tcss"

    BINDINGS = []

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._gateway: HLedgerGateway | None = None

    def compose(self) -> ComposeResult:
        yield NavHeader()

        with Container(id="reports-container"):
            yield Label(
                "Financial Reports",
                id="reports-title",
                classes="screen-title",
            )
            yield PeriodSelector(id="reports-period")

            with TabbedContent(
                id="reports-tabs",
                initial="tab-net-worth",
            ):
                with TabPane("Net Worth", id="tab-net-worth"):
                    yield PlotextPlot(id="net-worth-chart")
                    yield Static(
                        "No net worth data available. "
                        "Add transactions to see your net worth "
                        "trend over time.",
                        id="net-worth-empty",
                        classes="empty-state",
                    )

                with TabPane("Spending", id="tab-spending"):
                    yield PlotextPlot(id="spending-chart")
                    yield Static(
                        "No spending data available. "
                        "Record some expenses to see spending "
                        "by category.",
                        id="spending-empty",
                        classes="empty-state",
                    )

                with TabPane("Cash Flow", id="tab-cashflow"):
                    yield PlotextPlot(id="cashflow-chart")
                    yield Static(
                        "No cash flow data available. "
                        "Add income and expense transactions "
                        "to see your monthly cash flow.",
                        id="cashflow-empty",
                        classes="empty-state",
                    )

                with TabPane("Comparison", id="tab-comparison"):
                    yield DataTable(id="comparison-table")
                    yield Static(
                        "No comparison data available. "
                        "Add transactions across multiple "
                        "periods to compare.",
                        id="comparison-empty",
                        classes="empty-state",
                    )

        yield Footer()

    def on_mount(self) -> None:
        """Load initial data when the screen is mounted."""
        self.query_one(NavHeader).set_active("reports")
        # Grab the gateway from the app if not already set
        if self._gateway is None and hasattr(self.app, "gateway"):
            self._gateway = self.app.gateway
        # Set up the comparison DataTable columns
        table = self.query_one("#comparison-table", DataTable)
        table.add_columns(
            "Category", "Current Period", "Previous Period", "Change"
        )
        if self._gateway is not None:
            self._load_all_tabs()

    def set_gateway(self, gateway: HLedgerGateway) -> None:
        """Set the hledger gateway and trigger a data reload."""
        self._gateway = gateway
        if self.is_mounted:
            self._load_all_tabs()

    def on_period_selector_period_changed(
        self, event: PeriodSelector.PeriodChanged
    ) -> None:
        """Reload data when the period changes."""
        if self._gateway is not None:
            self._load_all_tabs()

    def _load_all_tabs(self) -> None:
        """Spawn workers for all report tabs."""
        self.run_worker(
            self._fetch_net_worth(),
            name="net-worth",
            exclusive=True,
            group="reports",
        )
        self.run_worker(
            self._fetch_spending(),
            name="spending",
            exclusive=True,
            group="reports",
        )
        self.run_worker(
            self._fetch_cashflow(),
            name="cashflow",
            exclusive=True,
            group="reports",
        )
        self.run_worker(
            self._fetch_comparison(),
            name="comparison",
            exclusive=True,
            group="reports",
        )

    # -----------------------------------------------------------------
    # Tab 1: Net Worth
    # -----------------------------------------------------------------

    async def _fetch_net_worth(self) -> None:
        """Fetch monthly net worth for the last 12 months."""
        if self._gateway is None:
            return

        chart = self.query_one("#net-worth-chart", PlotextPlot)
        empty = self.query_one("#net-worth-empty", Static)

        try:
            period_str = _month_ranges_period(12)
            raw = await self._gateway.balance(
                accounts=["assets", "liabilities"],
                period=period_str,
            )
            data = json.loads(raw)
            # Monthly balance data comes as list of
            # [amounts, account, ...] per period
            # With --monthly, hledger returns period columns
            months = _month_range(12)
            labels = [
                _month_label(y, m) for y, m in months
            ]

            # Parse the balance data for net worth trend
            # hledger balance --monthly returns running totals
            balances = parse_balance_report(data)

            if not balances:
                chart.display = False
                empty.display = True
                return

            # Sum all account balances for net worth
            total = Decimal("0")
            for bal in balances:
                total += bal.balance.quantity

            # For a simple chart, show the total as a single
            # point. For a real trend we need monthly data.
            # Let's try to get monthly snapshots.
            values = await self._get_monthly_net_worth(months)

            if not values or all(v == 0 for v in values):
                chart.display = False
                empty.display = True
                return

            chart.display = True
            empty.display = False

            plt = chart.plt
            plt.clear_data()
            plt.clear_figure()
            plt.title("Net Worth (Last 12 Months)")
            plt.xlabel("Month")
            plt.ylabel("Amount")
            plt.plot(
                list(range(len(values))),
                values,
                marker="braille",
                color=COLOR_NET_WORTH,
                label="Net Worth",
            )
            plt.xticks(
                list(range(len(labels))),
                labels,
            )
            chart.refresh()

        except (HLedgerError, HLedgerNotFoundError) as exc:
            log.debug("Net worth fetch failed: %s", exc)
            chart.display = False
            empty.display = True
        except Exception as exc:
            log.debug("Net worth fetch failed: %s", exc)
            chart.display = False
            empty.display = True

    async def _get_monthly_net_worth(
        self, months: list[tuple[int, int]]
    ) -> list[float]:
        """Get net worth balance at end of each month."""
        values: list[float] = []
        for year, month in months:
            try:
                # End of month = first day of next month
                if month == 12:
                    end = date(year + 1, 1, 1)
                else:
                    end = date(year, month + 1, 1)
                period = f"to {end.isoformat()}"
                raw = await self._gateway.balance(
                    accounts=["assets", "liabilities"],
                    period=period,
                )
                data = json.loads(raw)
                balances = parse_balance_report(data)
                total = Decimal("0")
                for bal in balances:
                    total += bal.balance.quantity
                values.append(float(total))
            except Exception:
                # Use 0 for months without data
                values.append(
                    values[-1] if values else 0.0
                )
        return values

    # -----------------------------------------------------------------
    # Tab 2: Spending
    # -----------------------------------------------------------------

    async def _fetch_spending(self) -> None:
        """Fetch expense breakdown by category for selected period."""
        if self._gateway is None:
            return

        chart = self.query_one("#spending-chart", PlotextPlot)
        empty = self.query_one("#spending-empty", Static)

        try:
            period = self._get_period()
            raw = await self._gateway.balance(
                accounts=["expenses"],
                depth=2,
                period=period if period else None,
            )
            data = json.loads(raw)
            balances = parse_balance_report(data)

            if not balances:
                chart.display = False
                empty.display = True
                return

            # Sort by absolute amount descending, top 10
            sorted_bals = sorted(
                balances,
                key=lambda b: abs(b.balance.quantity),
                reverse=True,
            )[:10]

            # Filter out zero amounts
            sorted_bals = [
                b for b in sorted_bals
                if b.balance.quantity != Decimal("0")
            ]

            if not sorted_bals:
                chart.display = False
                empty.display = True
                return

            chart.display = True
            empty.display = False

            # Shorten account names: "expenses:food" -> "Food"
            labels = []
            values = []
            for bal in reversed(sorted_bals):
                parts = bal.account.split(":")
                name = parts[-1].title() if parts else bal.account
                # Truncate long names
                if len(name) > 15:
                    name = name[:12] + "..."
                labels.append(name)
                values.append(float(abs(bal.balance.quantity)))

            plt = chart.plt
            plt.clear_data()
            plt.clear_figure()
            plt.title("Spending by Category")
            plt.bar(
                labels,
                values,
                orientation="h",
                color=COLOR_BAR,
            )
            chart.refresh()

        except (HLedgerError, HLedgerNotFoundError) as exc:
            log.debug("Spending fetch failed: %s", exc)
            chart.display = False
            empty.display = True
        except Exception as exc:
            log.debug("Spending fetch failed: %s", exc)
            chart.display = False
            empty.display = True

    # -----------------------------------------------------------------
    # Tab 3: Cash Flow
    # -----------------------------------------------------------------

    async def _fetch_cashflow(self) -> None:
        """Fetch monthly income vs expenses for the last 6 months."""
        if self._gateway is None:
            return

        chart = self.query_one("#cashflow-chart", PlotextPlot)
        empty = self.query_one("#cashflow-empty", Static)

        try:
            period_str = _month_ranges_period(6)
            months = _month_range(6)
            labels = [
                _month_label(y, m) for y, m in months
            ]

            income_values: list[float] = []
            expense_values: list[float] = []

            for year, month in months:
                period = f"{year}-{month:02d}"
                try:
                    raw = await self._gateway.income_statement(
                        period=period
                    )
                    data = json.loads(raw)
                    inc, exp = self._parse_income_expense(
                        data
                    )
                    income_values.append(inc)
                    expense_values.append(exp)
                except Exception:
                    income_values.append(0.0)
                    expense_values.append(0.0)

            has_data = any(
                v != 0
                for v in income_values + expense_values
            )
            if not has_data:
                chart.display = False
                empty.display = True
                return

            chart.display = True
            empty.display = False

            plt = chart.plt
            plt.clear_data()
            plt.clear_figure()
            plt.title("Cash Flow (Last 6 Months)")
            plt.multiple_bar(
                labels,
                [income_values, expense_values],
                labels=["Income", "Expenses"],
                color=[COLOR_INCOME, COLOR_EXPENSE],
            )
            plt.ylabel("Amount")
            chart.refresh()

        except (HLedgerError, HLedgerNotFoundError) as exc:
            log.debug("Cash flow fetch failed: %s", exc)
            chart.display = False
            empty.display = True
        except Exception as exc:
            log.debug("Cash flow fetch failed: %s", exc)
            chart.display = False
            empty.display = True

    def _parse_income_expense(
        self, data: list | dict
    ) -> tuple[float, float]:
        """Parse income statement JSON into (income, expenses) floats."""
        income = 0.0
        expenses = 0.0

        if isinstance(data, list):
            for subreport in data:
                if not isinstance(subreport, dict):
                    continue
                title = subreport.get("title", "").lower()
                totals = subreport.get("totals", {})
                row_totals = totals.get("row_total", [])
                if row_totals:
                    amt = parse_amount(row_totals[0])
                    if "income" in title or "revenue" in title:
                        income = float(abs(amt.quantity))
                    elif "expense" in title:
                        expenses = float(abs(amt.quantity))
        return income, expenses

    # -----------------------------------------------------------------
    # Tab 4: Comparison
    # -----------------------------------------------------------------

    async def _fetch_comparison(self) -> None:
        """Fetch side-by-side period comparison data."""
        if self._gateway is None:
            return

        table = self.query_one("#comparison-table", DataTable)
        empty = self.query_one("#comparison-empty", Static)

        try:
            # Current and previous month
            today = date.today()
            current_period = (
                f"{today.year}-{today.month:02d}"
            )
            prev_month = today.month - 1
            prev_year = today.year
            if prev_month == 0:
                prev_month = 12
                prev_year -= 1
            prev_period = f"{prev_year}-{prev_month:02d}"

            # Fetch expenses for both periods
            current_raw = await self._gateway.balance(
                accounts=["expenses"],
                depth=2,
                period=current_period,
            )
            prev_raw = await self._gateway.balance(
                accounts=["expenses"],
                depth=2,
                period=prev_period,
            )

            current_data = json.loads(current_raw)
            prev_data = json.loads(prev_raw)

            current_bals = parse_balance_report(current_data)
            prev_bals = parse_balance_report(prev_data)

            if not current_bals and not prev_bals:
                table.display = False
                empty.display = True
                return

            table.display = True
            empty.display = False

            # Build lookup maps
            current_map: dict[str, Decimal] = {
                b.account: b.balance.quantity
                for b in current_bals
            }
            prev_map: dict[str, Decimal] = {
                b.account: b.balance.quantity
                for b in prev_bals
            }

            # Combine all categories
            all_accounts = sorted(
                set(current_map.keys()) | set(prev_map.keys())
            )

            table.clear()
            current_label = _month_label(
                today.year, today.month
            )
            prev_label = _month_label(prev_year, prev_month)

            # Update column headers
            table.columns.clear()
            table.add_columns(
                "Category",
                f"{current_label} {today.year}",
                f"{prev_label} {prev_year}",
                "Change",
            )

            for account in all_accounts:
                cur_amt = abs(
                    current_map.get(account, Decimal("0"))
                )
                prv_amt = abs(
                    prev_map.get(account, Decimal("0"))
                )
                change = cur_amt - prv_amt

                # Format name
                parts = account.split(":")
                name = (
                    ":".join(parts[1:]).title()
                    if len(parts) > 1
                    else account.title()
                )

                # Format change with sign
                if change > 0:
                    change_str = f"+${change:,.2f}"
                elif change < 0:
                    change_str = f"-${abs(change):,.2f}"
                else:
                    change_str = "$0.00"

                table.add_row(
                    name,
                    f"${cur_amt:,.2f}",
                    f"${prv_amt:,.2f}",
                    change_str,
                )

        except (HLedgerError, HLedgerNotFoundError) as exc:
            log.debug("Comparison fetch failed: %s", exc)
            table.display = False
            empty.display = True
        except Exception as exc:
            log.debug("Comparison fetch failed: %s", exc)
            table.display = False
            empty.display = True

    # -----------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------

    def _get_period(self) -> str:
        """Get the currently selected period from the PeriodSelector."""
        try:
            selector = self.query_one(
                "#reports-period", PeriodSelector
            )
            return selector.period
        except Exception:
            return "thismonth"
