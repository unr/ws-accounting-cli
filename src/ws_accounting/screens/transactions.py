"""Transactions screen -- browse, search, filter, and review transactions."""

from __future__ import annotations

import json
import logging
from dataclasses import replace
from pathlib import Path

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
    Select,
    Static,
)

from ws_accounting.config.settings import AppConfig
from ws_accounting.core.hledger import (
    HLedgerError,
    HLedgerGateway,
    HLedgerNotFoundError,
)
from ws_accounting.core.models import (
    Transaction,
    TransactionStatus,
)
from ws_accounting.core.parser import parse_register
from ws_accounting.widgets.period_selector import PeriodSelector
from ws_accounting.widgets.transaction_table import (
    TransactionTable,
)

log = logging.getLogger(__name__)


STATUS_FILTER_OPTIONS: list[tuple[str, str]] = [
    ("All", "all"),
    ("Needs Review", "unmarked"),
    ("Pending", "pending"),
    ("Cleared", "cleared"),
]

STATUS_MAP: dict[str, TransactionStatus | None] = {
    "all": None,
    "unmarked": TransactionStatus.UNMARKED,
    "pending": TransactionStatus.PENDING,
    "cleared": TransactionStatus.CLEARED,
}


# ── Transaction Detail Modal ──────────────────────────────────────


class TransactionDetailModal(ModalScreen[Transaction | None]):
    """Modal showing full transaction details with status toggle."""

    DEFAULT_CSS = """
    TransactionDetailModal {
        align: center middle;
    }
    #detail-container {
        width: 70;
        max-width: 90%;
        max-height: 85%;
        background: $surface;
        border: round $primary;
        padding: 1 2;
    }
    #detail-header {
        text-style: bold;
        margin-bottom: 1;
        color: $text;
        width: 1fr;
    }
    .detail-row {
        height: auto;
        margin-bottom: 0;
    }
    .detail-label {
        width: 14;
        text-style: bold;
        color: $text-muted;
    }
    .detail-value {
        width: 1fr;
    }
    #postings-container {
        height: auto;
        max-height: 12;
        margin: 1 0;
        border: round $panel;
        padding: 0 1;
    }
    .posting-row {
        height: 1;
    }
    .posting-account {
        width: 1fr;
    }
    .posting-amount {
        width: 16;
        text-align: right;
    }
    #detail-status-select {
        width: 20;
        margin: 1 0;
    }
    #detail-buttons {
        height: 3;
        align: right middle;
        margin-top: 1;
    }
    #detail-buttons Button {
        margin-left: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
        Binding(
            "ctrl+s", "save", "Save", show=True, priority=True
        ),
    ]

    def __init__(self, transaction: Transaction) -> None:
        self._transaction = transaction
        self._new_status = transaction.status
        super().__init__()

    def compose(self) -> ComposeResult:
        txn = self._transaction

        with Vertical(id="detail-container"):
            yield Static(
                "Transaction Details", id="detail-header"
            )

            # Date
            with Horizontal(classes="detail-row"):
                yield Static("Date", classes="detail-label")
                date_str = txn.date.isoformat()
                if txn.date2:
                    date_str += f" ({txn.date2.isoformat()})"
                yield Static(date_str, classes="detail-value")

            # Description / Payee
            with Horizontal(classes="detail-row"):
                yield Static(
                    "Description", classes="detail-label"
                )
                desc = txn.description
                if txn.payee:
                    desc = f"{txn.payee} | {desc}"
                yield Static(desc, classes="detail-value")

            # Comment
            if txn.comment:
                with Horizontal(classes="detail-row"):
                    yield Static(
                        "Note", classes="detail-label"
                    )
                    yield Static(
                        txn.comment, classes="detail-value"
                    )

            # Tags
            if txn.tags:
                with Horizontal(classes="detail-row"):
                    yield Static(
                        "Tags", classes="detail-label"
                    )
                    tags_str = ", ".join(
                        f"{k}: {v}"
                        for k, v in txn.tags.items()
                    )
                    yield Static(
                        tags_str, classes="detail-value"
                    )

            # Postings
            yield Static(
                "Postings",
                classes="detail-label",
            )
            with ScrollableContainer(id="postings-container"):
                for posting in txn.postings:
                    with Horizontal(classes="posting-row"):
                        yield Static(
                            posting.account,
                            classes="posting-account",
                        )
                        if posting.amount is not None:
                            qty = posting.amount.quantity
                            abs_qty = abs(qty)
                            fmt = f"{abs_qty:,.2f}"
                            c = posting.amount.commodity
                            if qty < 0:
                                amt_str = f"-{c}{fmt}"
                            else:
                                amt_str = f" {c}{fmt}"
                        else:
                            amt_str = "(auto)"
                        yield Static(
                            amt_str,
                            classes="posting-amount",
                        )

            # Status selector
            with Horizontal(classes="detail-row"):
                yield Static(
                    "Status", classes="detail-label"
                )
                current = txn.status.name.lower()
                yield Select(
                    [
                        ("Unmarked", "unmarked"),
                        ("Pending", "pending"),
                        ("Cleared", "cleared"),
                    ],
                    value=current,
                    id="detail-status-select",
                    allow_blank=False,
                )

            # Source info
            if txn.source_file:
                with Horizontal(classes="detail-row"):
                    yield Static(
                        "Source", classes="detail-label"
                    )
                    source = txn.source_file
                    if txn.source_line:
                        source += f":{txn.source_line}"
                    yield Static(
                        source, classes="detail-value"
                    )

            # Buttons
            with Horizontal(id="detail-buttons"):
                yield Button(
                    "Cancel",
                    variant="default",
                    id="btn-cancel",
                )
                yield Button(
                    "Save",
                    variant="primary",
                    id="btn-save",
                )

    def on_select_changed(
        self, event: Select.Changed
    ) -> None:
        """Track status changes."""
        if event.select.id == "detail-status-select":
            status_map = {
                "unmarked": TransactionStatus.UNMARKED,
                "pending": TransactionStatus.PENDING,
                "cleared": TransactionStatus.CLEARED,
            }
            val = str(event.value) if event.value else ""
            self._new_status = status_map.get(
                val, self._transaction.status
            )

    def on_button_pressed(
        self, event: Button.Pressed
    ) -> None:
        if event.button.id == "btn-save":
            self.action_save()
        elif event.button.id == "btn-cancel":
            self.action_cancel()

    def action_save(self) -> None:
        """Dismiss with the updated transaction."""
        if self._new_status != self._transaction.status:
            updated = replace(
                self._transaction, status=self._new_status
            )
            self.dismiss(updated)
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        """Dismiss without changes."""
        self.dismiss(None)


# ── Help text ─────────────────────────────────────────────────────

HELP_TEXT = """\
[bold]Keyboard Shortcuts[/bold]

[bold]Navigation[/bold]
  j / k          Move down / up
  Home / End     Jump to top / bottom
  Ctrl+D / U     Page down / up
  Enter          Open transaction details

[bold]Actions[/bold]
  Space          Toggle row selection
  a              Accept (mark as cleared)
  r              Filter to needs review
  /              Focus search
  ?              Toggle this help

[bold]Search[/bold]
  Uses hledger query syntax:
  desc:coffee    Search descriptions
  acct:food      Search accounts
  amt:>50        Amount filters
  date:2026      Date filters

[bold]Quick Add[/bold]
  Type in the bottom bar:
  coffee 4.50 expenses:food:dining
"""


# ── Main Transactions Screen ─────────────────────────────────────


class TransactionsScreen(Screen):
    """Transaction list with search, filter, and review workflow."""

    CSS_PATH = "../styles/transactions.tcss"

    BINDINGS = [
        Binding(
            "slash",
            "focus_search",
            "Search",
            show=True,
            key_display="/",
        ),
        Binding(
            "question_mark",
            "toggle_help",
            "Help",
            show=True,
            key_display="?",
        ),
        Binding(
            "escape",
            "dismiss_overlay",
            "Back",
            show=False,
        ),
        Binding(
            "r",
            "show_needs_review",
            "Review",
            show=True,
        ),
    ]

    def __init__(
        self,
        gateway: HLedgerGateway | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._gateway = gateway
        self._all_transactions: list[Transaction] = []
        self._current_period: str = "thismonth"
        self._current_query: str = ""
        self._current_status_filter: (
            TransactionStatus | None
        ) = None
        self._search_timer_handle = None

    def compose(self) -> ComposeResult:
        # Toolbar: search + filters
        with Horizontal(id="txn-toolbar"):
            yield Input(
                placeholder=(
                    "Search transactions"
                    " (hledger query)..."
                ),
                id="search-input",
            )
            yield PeriodSelector(id="period-selector")
            yield Select(
                [
                    (label, value)
                    for label, value in STATUS_FILTER_OPTIONS
                ],
                value="all",
                id="status-filter",
                allow_blank=False,
            )
            yield Static("", id="review-badge")

        # Main content area
        with Vertical(id="txn-content"):
            yield Static(
                "Loading transactions...",
                id="loading-indicator",
            )
            yield Static(
                "No transactions found.\n\n"
                "Import a CSV or add transactions manually\n"
                "to get started.",
                id="empty-state",
            )
            yield TransactionTable(id="txn-table")

        # Quick-add bar at bottom
        with Horizontal(id="quick-add-bar"):
            yield Input(
                placeholder=(
                    "Quick add: description amount category"
                    "  (e.g. coffee 4.50"
                    " expenses:food:dining)"
                ),
                id="quick-add-input",
            )

        # Help overlay (hidden by default via TCSS)
        yield Static(HELP_TEXT, id="help-overlay")

        yield Footer()

    def on_mount(self) -> None:
        """Initialize gateway from config if not provided."""
        if self._gateway is None:
            self._init_gateway()
        self._load_data()

    def set_gateway(self, gateway: HLedgerGateway) -> None:
        """Set the hledger gateway and trigger a reload."""
        self._gateway = gateway
        if self.is_mounted:
            self._load_data()

    def _init_gateway(self) -> None:
        """Create HLedgerGateway from saved config."""
        try:
            config = AppConfig.load()
            if config.journal_path:
                self._gateway = HLedgerGateway(
                    Path(config.journal_path)
                )
        except Exception:
            log.exception("Failed to load config for gateway")

    # ── Data loading ──────────────────────────────────────────────

    def _load_data(self) -> None:
        """Spawn an async worker to fetch transactions."""
        self.run_worker(
            self._fetch_transactions(),
            name="txn-load",
            exclusive=True,
        )

    async def _fetch_transactions(self) -> None:
        """Fetch transactions from hledger."""
        self._show_loading(True)

        if self._gateway is None:
            self._display_empty("No journal configured.")
            return

        try:
            raw = await self._gateway.print_journal(
                query=self._current_query or None,
                period=self._current_period or None,
                json_format=True,
            )
            data = json.loads(raw)
            transactions = parse_register(data)
            self._display_transactions(transactions)
        except HLedgerNotFoundError:
            self._display_empty(
                "hledger not found.\n\n"
                "Install hledger to view transactions:\n"
                "https://hledger.org/install.html"
            )
        except HLedgerError as exc:
            log.warning("hledger error: %s", exc)
            self._display_empty(
                f"Error loading transactions:\n{exc}"
            )
        except Exception:
            log.exception("Failed to load transactions")
            self._display_empty(
                "No transactions found.\n\n"
                "Import a CSV or add transactions manually\n"
                "to get started."
            )

    # ── Display helpers ───────────────────────────────────────────

    def _show_loading(self, show: bool) -> None:
        """Toggle loading indicator visibility."""
        loading = self.query_one("#loading-indicator")
        table = self.query_one("#txn-table")
        empty = self.query_one("#empty-state")
        if show:
            loading.add_class("visible")
            table.display = False
            empty.remove_class("visible")
        else:
            loading.remove_class("visible")

    def _display_transactions(
        self, transactions: list[Transaction]
    ) -> None:
        """Populate the table with fetched transactions."""
        self._all_transactions = transactions
        self._show_loading(False)

        filtered = self._apply_status_filter(transactions)
        table = self.query_one(
            "#txn-table", TransactionTable
        )
        empty = self.query_one("#empty-state")

        if filtered:
            table.load_transactions(filtered)
            table.display = True
            empty.remove_class("visible")
        else:
            table.display = False
            empty.add_class("visible")

        self._update_review_badge()

    def _display_empty(self, message: str) -> None:
        """Show empty-state message, hide table and loading."""
        self._show_loading(False)
        self.query_one("#txn-table").display = False
        empty = self.query_one("#empty-state", Static)
        empty.update(message)
        empty.add_class("visible")
        self._update_review_badge()

    def _apply_status_filter(
        self, transactions: list[Transaction]
    ) -> list[Transaction]:
        """Filter by the currently selected status."""
        if self._current_status_filter is None:
            return transactions
        return [
            t
            for t in transactions
            if t.status == self._current_status_filter
        ]

    def _update_review_badge(self) -> None:
        """Update badge showing count of unreviewed transactions."""
        badge = self.query_one("#review-badge", Static)
        count = sum(
            1
            for t in self._all_transactions
            if t.status == TransactionStatus.UNMARKED
        )
        if count > 0:
            badge.update(f" {count} to review ")
            badge.add_class("visible")
        else:
            badge.remove_class("visible")

    # ── Event handlers ────────────────────────────────────────────

    def on_input_changed(
        self, event: Input.Changed
    ) -> None:
        """Debounce search input (300ms)."""
        if event.input.id != "search-input":
            return
        if self._search_timer_handle is not None:
            self._search_timer_handle.stop()
        self._search_timer_handle = self.set_timer(
            0.3, self._execute_search
        )

    def _execute_search(self) -> None:
        """Run the debounced search query."""
        try:
            inp = self.query_one("#search-input", Input)
            self._current_query = inp.value.strip()
        except Exception:
            return
        self._load_data()

    def on_period_selector_period_changed(
        self, event: PeriodSelector.PeriodChanged
    ) -> None:
        """Reload when the period filter changes."""
        self._current_period = event.period
        self._load_data()

    def on_select_changed(
        self, event: Select.Changed
    ) -> None:
        """Handle status filter dropdown changes."""
        if event.select.id != "status-filter":
            return
        value = str(event.value) if event.value else "all"
        self._current_status_filter = STATUS_MAP.get(value)
        # Re-filter already-loaded data (no network call)
        filtered = self._apply_status_filter(
            self._all_transactions
        )
        table = self.query_one(
            "#txn-table", TransactionTable
        )
        empty = self.query_one("#empty-state", Static)
        if filtered:
            table.load_transactions(filtered)
            table.display = True
            empty.remove_class("visible")
        else:
            table.display = False
            empty.update(
                "No transactions match the current filters."
            )
            empty.add_class("visible")

    def on_transaction_table_transaction_selected(
        self,
        event: TransactionTable.TransactionSelected,
    ) -> None:
        """Open detail modal for the selected transaction."""
        self.app.push_screen(
            TransactionDetailModal(event.transaction),
            callback=self._on_detail_dismissed,
        )

    def _on_detail_dismissed(
        self, result: Transaction | None
    ) -> None:
        """Handle modal result -- reload if changes were made."""
        if result is not None:
            log.info(
                "Transaction status updated: %s -> %s",
                result.description,
                result.status.name,
            )
            # In full implementation: write change to journal
            self._load_data()

    def on_transaction_table_transaction_accepted(
        self,
        event: TransactionTable.TransactionAccepted,
    ) -> None:
        """Mark transaction as cleared when 'a' is pressed."""
        txn = event.transaction
        if txn.status == TransactionStatus.UNMARKED:
            log.info(
                "Accepted transaction: %s",
                txn.description,
            )
            # In full implementation: write status to journal
            self._load_data()

    def on_input_submitted(
        self, event: Input.Submitted
    ) -> None:
        """Handle quick-add bar submission."""
        if event.input.id != "quick-add-input":
            return
        text = event.value.strip()
        if text:
            self._handle_quick_add(text)
            event.input.value = ""

    def _handle_quick_add(self, text: str) -> None:
        """Parse quick-add text: 'description amount [category]'."""
        parts = text.split()
        if len(parts) < 2:
            self.notify(
                "Format: description amount [category]",
                severity="warning",
                title="Quick Add",
            )
            return

        # Find the first numeric-looking token
        amount_idx = None
        for i, part in enumerate(parts):
            cleaned = part.replace(",", "").lstrip("$")
            try:
                float(cleaned)
                amount_idx = i
                break
            except ValueError:
                continue

        if amount_idx is None:
            self.notify(
                "Could not find amount in input.",
                severity="warning",
                title="Quick Add",
            )
            return

        description = " ".join(parts[:amount_idx])
        if not description:
            description = "Quick entry"

        amount_str = (
            parts[amount_idx].replace(",", "").lstrip("$")
        )
        category = (
            parts[amount_idx + 1]
            if amount_idx + 1 < len(parts)
            else "expenses:miscellaneous"
        )

        self.notify(
            f"Added: {description} ${amount_str}"
            f" -> {category}",
            title="Quick Add",
        )
        # In full implementation: create Transaction and write

    # ── Actions ───────────────────────────────────────────────────

    def action_focus_search(self) -> None:
        """Focus the search input."""
        self.query_one("#search-input", Input).focus()

    def action_toggle_help(self) -> None:
        """Toggle the help overlay."""
        overlay = self.query_one("#help-overlay")
        if overlay.has_class("visible"):
            overlay.remove_class("visible")
        else:
            overlay.add_class("visible")

    def action_dismiss_overlay(self) -> None:
        """Dismiss any visible overlay."""
        overlay = self.query_one("#help-overlay")
        if overlay.has_class("visible"):
            overlay.remove_class("visible")

    def action_show_needs_review(self) -> None:
        """Filter to unreviewed transactions."""
        select = self.query_one("#status-filter", Select)
        select.value = "unmarked"
