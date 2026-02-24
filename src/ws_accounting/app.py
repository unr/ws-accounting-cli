"""Main Textual application for ws-accounting."""

from __future__ import annotations

import logging
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.reactive import reactive
from textual.widgets import Footer

from ws_accounting.config.paths import database_path, default_journal_dir
from ws_accounting.config.settings import AppConfig
from ws_accounting.core.hledger import HLedgerGateway
from ws_accounting.db.database import Database
from ws_accounting.screens.onboarding import OnboardingScreen
from ws_accounting.theme import ALL_THEMES, financial_dark, financial_light
from ws_accounting.widgets.nav_header import NavHeader

log = logging.getLogger(__name__)

# Map tab IDs (from NavHeader) to mode names
TAB_TO_MODE: dict[str, str] = {
    "tab-dashboard": "dashboard",
    "tab-transactions": "transactions",
    "tab-import": "csv_import",
    "tab-budgets": "budgets",
    "tab-reports": "reports",
    "tab-ai": "insights",
    "tab-accounts": "accounts",
    "tab-settings": "settings",
}


class WsAccountingApp(App):
    """Personal finance TUI built with Textual + hledger."""

    TITLE = "ws-accounting"
    CSS_PATH = "styles/app.tcss"

    # MODES -- each screen is a mode, preserving state when switching.
    # String paths enable lazy loading (screens imported on first access).
    MODES = {
        "dashboard": "ws_accounting.screens.dashboard.DashboardScreen",
        "transactions": "ws_accounting.screens.transactions.TransactionsScreen",
        "csv_import": "ws_accounting.screens.csv_import.CSVImportScreen",
        "budgets": "ws_accounting.screens.budgets.BudgetsScreen",
        "reports": "ws_accounting.screens.reports.ReportsScreen",
        "insights": "ws_accounting.screens.insights.InsightsScreen",
        "accounts": "ws_accounting.screens.accounts.AccountsScreen",
        "settings": "ws_accounting.screens.settings.SettingsScreen",
    }

    DEFAULT_MODE = "dashboard"

    # Shared reactive state -- screens can watch these
    current_period = reactive("2026-02")
    journal_modified = reactive(0)

    BINDINGS = [
        Binding("ctrl+1", "switch_to('dashboard')", "Dashboard", show=False),
        Binding("ctrl+2", "switch_to('transactions')", "Txns", show=False),
        Binding("ctrl+3", "switch_to('csv_import')", "Import", show=False),
        Binding("ctrl+4", "switch_to('budgets')", "Budget", show=False),
        Binding("ctrl+5", "switch_to('reports')", "Reports", show=False),
        Binding("ctrl+6", "switch_to('insights')", "AI", show=False),
        Binding("ctrl+7", "switch_to('accounts')", "Accounts", show=False),
        Binding("q", "quit_app", "Quit"),
        Binding("question_mark", "help", "Help", show=False),
        Binding("n", "new_transaction", "New Txn", show=False),
        Binding("slash", "focus_search", "Search", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._config = AppConfig.load()
        self._db: Database | None = None
        self._gateway: HLedgerGateway | None = None

    def on_mount(self) -> None:
        """Initialize services and apply theme."""
        # Register custom themes
        for theme in ALL_THEMES:
            self.register_theme(theme)

        # Apply saved theme
        self.theme = self._config.theme

        # Initialize database
        self._init_database()

        # Initialize hledger gateway
        self._init_gateway()

        # Check for first run
        if self._config.first_run:
            self.push_screen(
                OnboardingScreen(),
                callback=self._on_onboarding_complete,
            )

    def _on_onboarding_complete(self, result: bool) -> None:
        """Handle onboarding completion."""
        if result:
            # Reload config (onboarding already saved it)
            self._config = AppConfig.load()
            # Re-init gateway with possibly updated journal dir
            self._init_gateway()

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
        journal_dir = self._config.journal_dir
        if not journal_dir:
            journal_dir = default_journal_dir()
        self._gateway = HLedgerGateway()

    # ---------------------------------------------------------------
    # Properties for screen access
    # ---------------------------------------------------------------

    @property
    def config(self) -> AppConfig:
        """The application configuration."""
        return self._config

    @property
    def gateway(self) -> HLedgerGateway | None:
        """The hledger gateway instance."""
        return self._gateway

    @property
    def hledger(self) -> HLedgerGateway | None:
        """Alias for gateway -- used by dashboard."""
        return self._gateway

    @property
    def database(self) -> Database | None:
        """The SQLite database instance."""
        return self._db

    # ---------------------------------------------------------------
    # Mode / screen switching
    # ---------------------------------------------------------------

    def action_switch_to(self, mode: str) -> None:
        """Switch to a named mode and update the nav tabs."""
        self.switch_mode(mode)
        self._sync_nav_tab(mode)
        self._inject_gateway(mode)

    def _sync_nav_tab(self, mode_name: str) -> None:
        """Keep the NavHeader tabs in sync with the active mode."""
        try:
            screen = self.screen
            navs = screen.query(NavHeader)
            for nav in navs:
                nav.set_active(mode_name)
        except Exception:
            pass

    def _inject_gateway(self, mode_name: str) -> None:
        """Inject the hledger gateway into screens that need it."""
        if self._gateway is None:
            return
        try:
            screen = self.screen
            if hasattr(screen, "set_gateway"):
                screen.set_gateway(self._gateway)
        except Exception:
            pass

    def on_tabs_changed(self, event) -> None:
        """Handle tab navigation from the NavHeader."""
        from textual.widgets import Tabs

        if not isinstance(event, Tabs.Changed):
            return
        tab_id = event.tab.id if event.tab else None
        if tab_id and tab_id in TAB_TO_MODE:
            mode_name = TAB_TO_MODE[tab_id]
            self.switch_mode(mode_name)
            self._inject_gateway(mode_name)

    # ---------------------------------------------------------------
    # Actions
    # ---------------------------------------------------------------

    def action_quit_app(self) -> None:
        """Quit the application."""
        self.exit()

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
