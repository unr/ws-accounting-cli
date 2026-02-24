"""Quick action buttons for the dashboard."""

from textual.app import ComposeResult
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Button


class QuickActions(Widget):
    """Row of buttons for common dashboard actions."""

    DEFAULT_CSS = """
    QuickActions {
        layout: horizontal;
        height: auto;
        min-height: 3;
        padding: 0 1;
        align: left middle;
    }
    QuickActions Button {
        margin: 0 1 0 0;
        min-width: 16;
    }
    """

    class ImportCSV(Message):
        """User wants to import a CSV file."""

    class NewTransaction(Message):
        """User wants to create a new transaction."""

    class ViewAccounts(Message):
        """User wants to view accounts."""

    def compose(self) -> ComposeResult:
        yield Button(
            "Import CSV",
            id="btn-import-csv",
            variant="primary",
        )
        yield Button(
            "New Transaction",
            id="btn-new-txn",
            variant="default",
        )
        yield Button(
            "View Accounts",
            id="btn-view-accounts",
            variant="default",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Dispatch messages based on which button was pressed."""
        if event.button.id == "btn-import-csv":
            self.post_message(self.ImportCSV())
        elif event.button.id == "btn-new-txn":
            self.post_message(self.NewTransaction())
        elif event.button.id == "btn-view-accounts":
            self.post_message(self.ViewAccounts())
