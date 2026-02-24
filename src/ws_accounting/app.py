"""Main Textual application for ws-accounting."""

from __future__ import annotations

import logging
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Tabs

from ws_accounting.config.paths import database_path
from ws_accounting.config.settings import AppConfig
from ws_accounting.core.hledger import HLedgerGateway
from ws_accounting.db.database import Database
from ws_accounting.screens.accounts import AccountsScreen
from ws_accounting.screens.budgets import BudgetsScreen
from ws_accounting.screens.csv_import import CSVImportScreen
from ws_accounting.screens.dashboard import DashboardScreen
from ws_accounting.screens.insights import InsightsScreen
from ws_accounting.screens.onboarding import OnboardingScreen
from ws_accounting.screens.reports import ReportsScreen
from ws_accounting.screens.settings import SettingsScreen
from ws_accounting.screens.transactions import TransactionsScreen
from ws_accounting.theme import financial_dark, financial_light
from ws_accounting.widgets.nav_header import NavHeader

log = logging.getLogger(__name__)

# Map tab IDs to screen names
TAB_TO_SCREEN: dict[str, str] = {
    "tab-dashboard": "dashboard",
    "tab-transactions": "transactions",
    "tab-csv_import": "csv_import",
    "tab-budgets": "budgets",
    "tab-reports": "reports",
    "tab-insights": "insights",
    "tab-accounts": "accounts",
    "tab-settings": "settings",
}


class WSAccountingApp(App):
    """Personal finance TUI built with Textual + hledger."""

    TITLE = "ws-accounting"
    CSS_PATH = "styles/app.tcss"

    SCREENS = {
        "dashboard": DashboardScreen,
        "transactions": TransactionsScreen,
        "csv_import": CSVImportScreen,
        "budgets": BudgetsScreen,
        "reports": ReportsScreen,
        "insights": InsightsScreen,
        "accounts": AccountsScreen,
        "settings": SettingsScreen,
        "onboarding": OnboardingScreen,
    }

    BINDINGS = [
        Binding(
            "ctrl+1",
            "switch_screen('dashboard')",
            "Dashboard",
            show=False,
        ),
        Binding(
            "ctrl+2",
            "switch_screen('transactions')",
            "Txns",
            show=False,
        ),
        Binding(
            "ctrl+3",
            "switch_screen('csv_import')",
            "Import",
            show=False,
        ),
        Binding(
            "ctrl+4",
            "switch_screen('budgets')",
            "Budget",
            show=False,
        ),
        Binding(
            "ctrl+5",
            "switch_screen('reports')",
            "Reports",
            show=False,
        ),
        Binding(
            "ctrl+6",
            "switch_screen('insights')",
            "AI",
            show=False,
        ),
        Binding(
            "ctrl+7",
            "switch_screen('accounts')",
            "Accounts",
            show=False,
        ),
        Binding("q", "quit", "Quit"),
        Binding(
            "question_mark", "help", "Help", show=False
        ),
        Binding(
            "n", "new_transaction", "New Txn", show=False
        ),
        Binding(
            "slash", "focus_search", "Search", show=False
        ),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.register_theme(financial_dark)
        self.register_theme(financial_light)
        self._config = AppConfig.load()
        self._db: Database | None = None
        self._gateway: HLedgerGateway | None = None

    def compose(self) -> ComposeResult:
        yield NavHeader()
        yield Footer()

    def on_mount(self) -> None:
        """Initialize services and navigate to the first screen."""
        # Apply saved theme
        self.theme = self._config.theme

        # Initialize database
        self._init_database()

        # Initialize hledger gateway
        self._init_gateway()

        # Navigate to dashboard (or onboarding on first run)
        if self._config.first_run:
            self.push_screen("onboarding")
        self.switch_screen("dashboard")

    def _init_database(self) -> None:
        """Create the database and run migrations."""
        try:
            db_path = database_path()
            self._db = Database(db_path)
            self._db.migrate()
        except Exception as exc:
            log.error("Failed to initialize database: %s", exc)

    def _init_gateway(self) -> None:
        """Create the hledger gateway from config."""
        journal_path = self._config.journal_path
        if not journal_path:
            # Fall back to default location
            from ws_accounting.config.paths import (
                default_journal_dir,
            )

            journal_path = str(
                default_journal_dir() / "main.journal"
            )
        self._gateway = HLedgerGateway(
            journal_path=Path(journal_path),
        )

    @property
    def gateway(self) -> HLedgerGateway | None:
        """The hledger gateway instance."""
        return self._gateway

    @property
    def database(self) -> Database | None:
        """The SQLite database instance."""
        return self._db

    # ---------------------------------------------------------------
    # Screen switching
    # ---------------------------------------------------------------

    def action_switch_screen(self, screen_name: str) -> None:
        """Switch to a named screen and update the nav tabs."""
        self.switch_screen(screen_name)
        self._sync_nav_tab(screen_name)
        self._inject_gateway(screen_name)

    def _sync_nav_tab(self, screen_name: str) -> None:
        """Keep the NavHeader tabs in sync with the active screen."""
        try:
            nav = self.query_one(NavHeader)
            nav.set_active(screen_name)
        except Exception:
            pass

    def _inject_gateway(self, screen_name: str) -> None:
        """Inject the hledger gateway into screens that need it."""
        if self._gateway is None:
            return
        try:
            screen = self.get_screen(screen_name)
            if hasattr(screen, "set_gateway"):
                screen.set_gateway(self._gateway)
        except Exception:
            pass

    def on_tabs_changed(self, event: Tabs.Changed) -> None:
        """Handle tab navigation from the NavHeader."""
        tab_id = event.tab.id if event.tab else None
        if tab_id and tab_id in TAB_TO_SCREEN:
            screen_name = TAB_TO_SCREEN[tab_id]
            self.switch_screen(screen_name)
            self._inject_gateway(screen_name)

    # ---------------------------------------------------------------
    # Actions
    # ---------------------------------------------------------------

    def action_help(self) -> None:
        """Show help information."""
        self.notify(
            "Keyboard shortcuts:\n"
            "\n"
            "Navigation:\n"
            "  Ctrl+1  Dashboard\n"
            "  Ctrl+2  Transactions\n"
            "  Ctrl+3  CSV Import\n"
            "  Ctrl+4  Budgets\n"
            "  Ctrl+5  Reports\n"
            "  Ctrl+6  AI Insights\n"
            "  Ctrl+7  Accounts\n"
            "\n"
            "Actions:\n"
            "  n  New transaction\n"
            "  /  Focus search bar\n"
            "  ?  Show this help\n"
            "  q  Quit application\n"
            "\n"
            "Transactions screen:\n"
            "  j/k        Move down/up\n"
            "  Enter      Open details\n"
            "  Space      Toggle selection\n"
            "  a          Mark as cleared\n"
            "  r          Filter needs review",
            title="Help -- Keyboard Shortcuts",
            timeout=15,
        )

    def action_new_transaction(self) -> None:
        """Placeholder for new transaction modal."""
        self.notify("New transaction -- coming soon")

    def action_focus_search(self) -> None:
        """Placeholder for search focus."""
        self.notify("Search -- coming soon")

    # ---------------------------------------------------------------
    # Lifecycle
    # ---------------------------------------------------------------

    def on_unmount(self) -> None:
        """Clean up database connection on exit."""
        if self._db:
            self._db.close()
