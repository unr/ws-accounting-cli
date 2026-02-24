"""Transaction DataTable with vim-style navigation."""

from textual.message import Message
from textual.widgets import DataTable

from ws_accounting.core.models import Transaction, TransactionStatus


class TransactionTable(DataTable):
    """DataTable subclass with vim keybindings for financial data."""

    DEFAULT_CSS = """
    TransactionTable {
        height: 1fr;
    }
    """

    BINDINGS = [
        ("j", "cursor_down", "Down"),
        ("k", "cursor_up", "Up"),
        ("home", "scroll_home", "Top"),
        ("end", "scroll_end", "Bottom"),
        ("G", "scroll_end", "Bottom"),
        ("ctrl+d", "page_down", "Pg Down"),
        ("ctrl+u", "page_up", "Pg Up"),
        ("enter", "select_cursor", "Open"),
        ("o", "select_cursor", "Open"),
        ("space", "toggle_selection", "Select"),
        ("a", "accept", "Accept"),
    ]

    class TransactionSelected(Message):
        def __init__(self, transaction: Transaction) -> None:
            super().__init__()
            self.transaction = transaction

    class TransactionAccepted(Message):
        def __init__(self, transaction: Transaction) -> None:
            super().__init__()
            self.transaction = transaction

    def __init__(self, **kwargs) -> None:
        super().__init__(cursor_type="row", zebra_stripes=True, **kwargs)
        self._transactions: dict[str, Transaction] = {}
        self._columns_added = False

    def on_mount(self) -> None:
        """Add columns when the widget is mounted."""
        self.setup_columns()

    def setup_columns(self) -> None:
        """Add standard transaction columns (idempotent)."""
        if self._columns_added:
            return
        self.add_columns("Date", "Description", "Category", "Amount", "Status")
        self._columns_added = True

    def load_transactions(self, transactions: list[Transaction]) -> None:
        """Load transaction data into the table."""
        self.clear()
        self._transactions.clear()
        for txn in transactions:
            date_str = txn.date.isoformat()
            desc = txn.description

            category = ""
            amount_str = ""
            for p in txn.postings:
                if p.account.startswith(("expenses:", "income:")):
                    category = p.account.split(":")[-1]
                    if p.amount:
                        amount_str = str(p.amount)
                    break

            status = ""
            if txn.status == TransactionStatus.CLEARED:
                status = "\u25cf"
            elif txn.status == TransactionStatus.PENDING:
                status = "\u25d0"
            else:
                status = "\u25cb"

            row_key = self.add_row(date_str, desc, category, amount_str, status)
            self._transactions[str(row_key)] = txn

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Post TransactionSelected when a row is activated."""
        key = str(event.row_key.value) if event.row_key else None
        if key and key in self._transactions:
            self.post_message(self.TransactionSelected(self._transactions[key]))

    def action_toggle_selection(self) -> None:
        """Toggle selection on the current row."""
        pass

    def action_accept(self) -> None:
        """Accept/clear the current transaction."""
        row_key = self.cursor_row
        if row_key is not None:
            key = str(row_key)
            if key in self._transactions:
                self.post_message(self.TransactionAccepted(self._transactions[key]))
