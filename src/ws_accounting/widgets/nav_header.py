"""Single-row Tabs navigation bar — replaces Header widget to save vertical space."""

from textual.widgets import Tabs, Tab


SCREEN_TABS = [
    ("Dashboard", "tab-dashboard"),
    ("Trans", "tab-transactions"),
    ("Import", "tab-import"),
    ("Budget", "tab-budgets"),
    ("Reports", "tab-reports"),
    ("AI", "tab-ai"),
    ("Accts", "tab-accounts"),
    ("\u2699", "tab-settings"),  # gear icon
]


class NavHeader(Tabs):
    """Navigation tabs across the top of every screen."""

    DEFAULT_CSS = """
    NavHeader {
        dock: top;
        height: 1;
    }
    """

    def __init__(self) -> None:
        super().__init__(
            *[Tab(label, id=tab_id) for label, tab_id in SCREEN_TABS],
        )

    def set_active(self, tab_id: str) -> None:
        """Set the active tab by ID."""
        self.active = tab_id
