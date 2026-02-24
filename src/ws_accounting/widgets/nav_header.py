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

    # Map screen/mode names to tab IDs for convenience
    _NAME_TO_TAB: dict[str, str] = {
        "dashboard": "tab-dashboard",
        "transactions": "tab-transactions",
        "csv_import": "tab-import",
        "import": "tab-import",
        "budgets": "tab-budgets",
        "reports": "tab-reports",
        "insights": "tab-ai",
        "ai": "tab-ai",
        "accounts": "tab-accounts",
        "settings": "tab-settings",
    }

    def set_active(self, name: str) -> None:
        """Set the active tab by screen/mode name or tab ID."""
        tab_id = self._NAME_TO_TAB.get(name, name)
        # If it still doesn't start with "tab-", add the prefix
        if not tab_id.startswith("tab-"):
            tab_id = f"tab-{tab_id}"
        self.active = tab_id
