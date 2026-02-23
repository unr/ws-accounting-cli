"""Navigation header with app title and tab bar."""

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Tab, Tabs

SCREEN_TABS = [
    ("dashboard", "Dashboard"),
    ("transactions", "Txns"),
    ("csv_import", "Import"),
    ("budgets", "Budget"),
    ("reports", "Reports"),
    ("insights", "AI"),
    ("accounts", "Accts"),
    ("settings", "Settings"),
]


class NavHeader(Widget):
    """Persistent Tabs navigation bar."""

    DEFAULT_CSS = """
    NavHeader {
        dock: top;
        height: 3;
    }
    """

    def compose(self) -> ComposeResult:
        yield Tabs(
            *[
                Tab(label, id=f"tab-{sid}")
                for sid, label in SCREEN_TABS
            ],
            id="nav-tabs",
        )

    def set_active(self, screen_id: str) -> None:
        """Activate the tab corresponding to the given screen id."""
        tabs = self.query_one(Tabs)
        tabs.active = f"tab-{screen_id}"
