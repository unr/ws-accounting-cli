"""Dashboard quick action buttons."""

from textual.containers import Horizontal
from textual.message import Message
from textual.widgets import Button, Static


class QuickActions(Static):
    """Row of quick action buttons for the dashboard."""

    DEFAULT_CSS = """
    QuickActions {
        height: auto;
        padding: 1 0;
    }
    QuickActions Horizontal {
        height: auto;
    }
    QuickActions Button {
        margin: 0 1;
    }
    """

    class ImportCSV(Message):
        """User wants to import a CSV."""

    class NewTransaction(Message):
        """User wants to create a new transaction."""

    class ViewAccounts(Message):
        """User wants to view accounts."""

    def compose(self):
        with Horizontal():
            yield Button("Import CSV", id="action-import", variant="primary")
            yield Button("Add Transaction", id="action-add-txn")
            yield Button("View Accounts", id="action-view-accounts")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Translate button presses into semantic messages."""
        if event.button.id == "action-import":
            self.post_message(self.ImportCSV())
        elif event.button.id == "action-add-txn":
            self.post_message(self.NewTransaction())
        elif event.button.id == "action-view-accounts":
            self.post_message(self.ViewAccounts())
