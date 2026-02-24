"""DataTable subclass with vim-style keybindings for transaction browsing."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from textual.binding import Binding
from textual.message import Message
from textual.widgets import DataTable
from textual.widgets.data_table import ColumnKey, RowKey

from ws_accounting.core.models import (
    Amount,
    Transaction,
    TransactionStatus,
)


# Column definitions: (key, label, width)
COLUMNS: list[tuple[str, str, int | None]] = [
    ("date", "Date", 12),
    ("description", "Description", None),
    ("category", "Category", 28),
    ("amount", "Amount", 14),
    ("status", "Status", 8),
]

STATUS_DISPLAY: dict[TransactionStatus, str] = {
    TransactionStatus.UNMARKED: "   ",
    TransactionStatus.PENDING: " ! ",
    TransactionStatus.CLEARED: " * ",
}


def _primary_category(txn: Transaction) -> str:
    """Extract the primary expense/income account from postings."""
    for posting in txn.postings:
        acct = posting.account.lower()
        if acct.startswith(("expenses:", "income:")):
            return posting.account
    # Fallback: return first non-asset/liability account, or first account
    for posting in txn.postings:
        acct = posting.account.lower()
        if not acct.startswith(("assets:", "liabilities:")):
            return posting.account
    if txn.postings:
        return txn.postings[0].account
    return ""


def _primary_amount(txn: Transaction) -> Amount:
    """Extract the primary display amount from a transaction.

    Uses the first posting amount. For expenses, this is typically
    the debit amount.
    """
    for posting in txn.postings:
        if posting.amount is not None:
            return posting.amount
    return Amount(Decimal("0"), "$")


class TransactionTable(DataTable):
    """DataTable with vim-style keybindings for transaction browsing."""

    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("home", "scroll_top", "Top", show=False),
        Binding("end", "scroll_bottom", "Bottom", show=False),
        Binding(
            "ctrl+d", "page_down", "Page Down", show=False
        ),
        Binding(
            "ctrl+u", "page_up", "Page Up", show=False
        ),
        Binding(
            "enter",
            "select_cursor",
            "Open",
            show=False,
        ),
        Binding(
            "space",
            "toggle_select",
            "Select",
            show=False,
        ),
        Binding("a", "accept", "Accept", show=False),
    ]

    class TransactionSelected(Message):
        """Emitted when user presses Enter on a row."""

        def __init__(self, transaction: Transaction) -> None:
            self.transaction = transaction
            super().__init__()

    class TransactionAccepted(Message):
        """Emitted when user presses 'a' to accept/clear a transaction."""

        def __init__(self, transaction: Transaction) -> None:
            self.transaction = transaction
            super().__init__()

    class SelectionToggled(Message):
        """Emitted when user toggles row selection with space."""

        def __init__(
            self, row_key: RowKey, selected: bool
        ) -> None:
            self.row_key = row_key
            self.selected = selected
            super().__init__()

    def __init__(self, **kwargs) -> None:
        super().__init__(
            cursor_type="row",
            zebra_stripes=True,
            **kwargs,
        )
        self._transactions: dict[RowKey, Transaction] = {}
        self._selected_rows: set[RowKey] = set()
        self._sort_column: str | None = None
        self._sort_reverse: bool = False
        self._column_keys: dict[str, ColumnKey] = {}

    def on_mount(self) -> None:
        """Set up table columns."""
        for key, label, width in COLUMNS:
            if width:
                col_key = self.add_column(
                    label, key=key, width=width
                )
            else:
                col_key = self.add_column(label, key=key)
            self._column_keys[key] = col_key

    def load_transactions(
        self, transactions: list[Transaction]
    ) -> None:
        """Clear and reload the table with new transaction data."""
        self.clear()
        self._transactions.clear()
        self._selected_rows.clear()

        for txn in transactions:
            amount = _primary_amount(txn)
            abs_qty = abs(amount.quantity)
            formatted_amount = f"{abs_qty:,.2f}"
            if amount.quantity < 0:
                amount_str = f"-{amount.commodity}{formatted_amount}"
            else:
                amount_str = (
                    f" {amount.commodity}{formatted_amount}"
                )

            row_key = self.add_row(
                txn.date.isoformat(),
                txn.payee or txn.description,
                _primary_category(txn),
                amount_str,
                STATUS_DISPLAY.get(txn.status, "   "),
            )
            self._transactions[row_key] = txn

    def get_transaction_at_cursor(self) -> Transaction | None:
        """Get the Transaction object for the currently highlighted row."""
        if self.row_count == 0:
            return None
        try:
            row_key, _ = self.coordinate_to_cell_key(
                self.cursor_coordinate
            )
            return self._transactions.get(row_key)
        except Exception:
            return None

    def get_selected_transactions(self) -> list[Transaction]:
        """Return all transactions in selected rows."""
        return [
            self._transactions[rk]
            for rk in self._selected_rows
            if rk in self._transactions
        ]

    @property
    def unreviewed_count(self) -> int:
        """Count transactions with UNMARKED status."""
        return sum(
            1
            for txn in self._transactions.values()
            if txn.status == TransactionStatus.UNMARKED
        )

    def action_toggle_select(self) -> None:
        """Toggle selection on the current row."""
        if self.row_count == 0:
            return
        try:
            row_key, _ = self.coordinate_to_cell_key(
                self.cursor_coordinate
            )
        except Exception:
            return

        if row_key in self._selected_rows:
            self._selected_rows.discard(row_key)
            selected = False
        else:
            self._selected_rows.add(row_key)
            selected = True
        self.post_message(
            self.SelectionToggled(row_key, selected)
        )

    def action_accept(self) -> None:
        """Accept/clear the transaction at cursor."""
        txn = self.get_transaction_at_cursor()
        if txn is not None:
            self.post_message(self.TransactionAccepted(txn))

    def on_data_table_row_selected(
        self, event: DataTable.RowSelected
    ) -> None:
        """Forward row selection as TransactionSelected message."""
        if event.row_key in self._transactions:
            self.post_message(
                self.TransactionSelected(
                    self._transactions[event.row_key]
                )
            )

    def on_data_table_header_selected(
        self, event: DataTable.HeaderSelected
    ) -> None:
        """Sort by the clicked column header."""
        col_key = event.column_key
        col_id = str(col_key)

        # Toggle sort direction if same column clicked again
        if self._sort_column == col_id:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_column = col_id
            self._sort_reverse = False

        self._apply_sort(col_id)

    def _apply_sort(self, column_id: str) -> None:
        """Sort the table by the given column."""
        sort_keys: dict[str, Any] = {
            "date": lambda row: row[0],
            "description": lambda row: row[1].lower(),
            "category": lambda row: row[2].lower(),
            "amount": lambda row: _parse_sort_amount(row[3]),
            "status": lambda row: row[4],
        }

        key_fn = sort_keys.get(column_id)
        if key_fn is None:
            return

        self.sort(
            column_id,
            key=key_fn,
            reverse=self._sort_reverse,
        )

    def filter_by_status(
        self,
        transactions: list[Transaction],
        status: TransactionStatus | None,
    ) -> list[Transaction]:
        """Filter transactions by status. None means show all."""
        if status is None:
            return transactions
        return [t for t in transactions if t.status == status]


def _parse_sort_amount(amount_str: str) -> Decimal:
    """Parse an amount display string back to Decimal for sorting."""
    cleaned = amount_str.strip().replace(",", "")
    # Remove currency symbol (first non-digit, non-minus, non-dot char)
    result = ""
    for ch in cleaned:
        if ch in "-0123456789.":
            result += ch
    try:
        return Decimal(result) if result else Decimal("0")
    except Exception:
        return Decimal("0")
