"""Dashboard quick action buttons."""

from textual.containers import Horizontal
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

    def compose(self):
        with Horizontal():
            yield Button("Import CSV", id="action-import", variant="primary")
            yield Button("Add Transaction", id="action-add-txn")
            yield Button("Load Sample Data", id="action-sample")
