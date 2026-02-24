"""AI Insights screen -- AI-powered financial analysis and advice."""

from __future__ import annotations

import logging
from datetime import date

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import (
    Button,
    Footer,
    Label,
    LoadingIndicator,
    Markdown,
    Select,
    Static,
)

from ws_accounting.ai.client import ClaudeProvider
from ws_accounting.ai.insights import InsightsGenerator
from ws_accounting.core.hledger import HLedgerGateway
from ws_accounting.db.database import Database
from ws_accounting.db.queries import get_cached_insights, get_setting
from ws_accounting.widgets.nav_header import NavHeader

log = logging.getLogger(__name__)


def _month_options() -> list[tuple[str, str]]:
    """Generate month options for the last 12 months."""
    today = date.today()
    options: list[tuple[str, str]] = []
    for i in range(12):
        month = today.month - i
        year = today.year
        while month <= 0:
            month += 12
            year -= 1
        label = date(year, month, 1).strftime("%B %Y")
        value = f"{year}-{month:02d}"
        options.append((label, value))
    return options


class InsightsScreen(Screen):
    """AI-powered financial insights and analysis."""

    CSS_PATH = "../styles/insights.tcss"

    BINDINGS = []

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._gateway: HLedgerGateway | None = None
        self._db: Database | None = None
        self._current_period: str = ""
        self._generator: InsightsGenerator | None = None

    def compose(self) -> ComposeResult:
        yield NavHeader()

        with Container(id="insights-container"):
            yield Label(
                "AI Financial Insights",
                id="insights-title",
                classes="screen-title",
            )

            with Horizontal(id="insights-controls"):
                yield Label(
                    "Period: ",
                    id="period-label",
                    classes="control-label",
                )
                yield Select(
                    _month_options(),
                    value=self._default_period(),
                    id="insights-period-select",
                    allow_blank=False,
                )
                yield Button(
                    "Generate Insights",
                    variant="primary",
                    id="btn-generate",
                )
                yield Button(
                    "Regenerate",
                    variant="default",
                    id="btn-regenerate",
                )

            # No API key warning
            yield Static(
                "AI insights require an API key.\n"
                "Configure one in Settings (Ctrl+8) to "
                "enable AI-powered analysis.\n\n"
                "If cached insights exist for this period, "
                "they will be shown below.",
                id="no-api-key-msg",
                classes="warning-box",
            )

            # Loading indicator
            yield Container(
                LoadingIndicator(),
                Label(
                    "Analyzing your financial data...",
                    id="loading-text",
                ),
                id="insights-loading",
            )

            # Insights content area
            with Vertical(id="insights-content"):
                yield Markdown(
                    "",
                    id="insights-markdown",
                )

            # Last generated timestamp
            yield Static(
                "",
                id="insights-timestamp",
                classes="timestamp",
            )

            # Empty state
            yield Static(
                "No insights available for this period.\n\n"
                "Click 'Generate Insights' to create an "
                "AI-powered analysis of your finances.",
                id="insights-empty",
                classes="empty-state",
            )

        yield Footer()

    def on_mount(self) -> None:
        """Initialize state when the screen is mounted."""
        self.query_one(NavHeader).set_active("insights")
        self._current_period = self._default_period()
        self._init_services()
        self._check_and_display()

    def set_gateway(self, gateway: HLedgerGateway) -> None:
        """Set the hledger gateway and reinitialize."""
        self._gateway = gateway
        if self.is_mounted:
            self._init_services()
            self._check_and_display()

    def _init_services(self) -> None:
        """Initialize the AI generator with current app services."""
        # Try to get database from the app if not set
        if self._db is None:
            try:
                app = self.app
                if hasattr(app, "database") and app.database:
                    self._db = app.database
            except Exception:
                pass

        # Try to get gateway from the app if not set
        if self._gateway is None:
            try:
                app = self.app
                if hasattr(app, "gateway") and app.gateway:
                    self._gateway = app.gateway
            except Exception:
                pass

        if self._gateway is None or self._db is None:
            return

        # Create AI provider if API key is configured
        provider = self._create_provider()
        self._generator = InsightsGenerator(
            gateway=self._gateway,
            db=self._db,
            provider=provider,
        )

    def _create_provider(self) -> ClaudeProvider | None:
        """Create an AI provider if API key is available."""
        api_key = self._get_api_key()
        if not api_key:
            return None

        model = "claude-sonnet-4-5-20250929"
        try:
            app = self.app
            if hasattr(app, "_config"):
                model = app._config.ai.model
        except Exception:
            pass

        return ClaudeProvider(api_key=api_key, model=model)

    def _get_api_key(self) -> str | None:
        """Retrieve the AI API key from settings or config."""
        # Try database settings first
        if self._db is not None:
            try:
                key = get_setting(self._db, "ai_api_key")
                if key:
                    return key
            except Exception:
                pass

        # Fall back to app config
        try:
            app = self.app
            if hasattr(app, "_config"):
                key = app._config.ai.api_key
                if key:
                    return key
        except Exception:
            pass

        return None

    def _check_and_display(self) -> None:
        """Check for cached insights and update the display."""
        has_api_key = bool(self._get_api_key())
        has_cache = False

        # Check for cached insights
        if self._db is not None:
            try:
                cached = get_cached_insights(
                    self._db, self._current_period
                )
                if cached:
                    has_cache = True
                    self._show_insights(
                        cached.content,
                        cached.generated_at,
                    )
            except Exception as exc:
                log.debug(
                    "Failed to check insights cache: %s", exc
                )

        # Update visibility of elements
        api_msg = self.query_one("#no-api-key-msg", Static)
        btn_gen = self.query_one("#btn-generate", Button)
        btn_regen = self.query_one("#btn-regenerate", Button)
        empty = self.query_one("#insights-empty", Static)
        loading = self.query_one("#insights-loading")
        content = self.query_one("#insights-content")

        loading.display = False

        if not has_api_key and not has_cache:
            # No API key and no cache: show warning + empty
            api_msg.display = True
            btn_gen.disabled = True
            btn_regen.display = False
            empty.display = True
            content.display = False
        elif not has_api_key and has_cache:
            # No API key but cache exists: show cache + warning
            api_msg.display = True
            btn_gen.disabled = True
            btn_regen.display = False
            empty.display = False
            content.display = True
        elif has_api_key and has_cache:
            # Has API key and cache: show cache + regenerate
            api_msg.display = False
            btn_gen.display = False
            btn_regen.display = True
            empty.display = False
            content.display = True
        else:
            # Has API key but no cache: show generate button
            api_msg.display = False
            btn_gen.display = True
            btn_gen.disabled = False
            btn_regen.display = False
            empty.display = True
            content.display = False

    def _show_insights(
        self,
        content: str,
        generated_at: str | None = None,
    ) -> None:
        """Display insights content in the markdown viewer."""
        md = self.query_one("#insights-markdown", Markdown)
        md.update(content)

        timestamp = self.query_one("#insights-timestamp", Static)
        if generated_at:
            timestamp.update(
                f"Last generated: {generated_at}"
            )
            timestamp.display = True
        else:
            timestamp.display = False

        content_area = self.query_one("#insights-content")
        content_area.display = True
        empty = self.query_one("#insights-empty", Static)
        empty.display = False

    # -----------------------------------------------------------------
    # Event handlers
    # -----------------------------------------------------------------

    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle period selection change."""
        if event.select.id != "insights-period-select":
            return
        value = str(event.value) if event.value else ""
        if value and value != self._current_period:
            self._current_period = value
            self._check_and_display()

    def on_button_pressed(
        self, event: Button.Pressed
    ) -> None:
        """Handle button presses."""
        if event.button.id == "btn-generate":
            self._start_generation(force_refresh=False)
        elif event.button.id == "btn-regenerate":
            self._start_generation(force_refresh=True)

    def _start_generation(
        self, force_refresh: bool = False
    ) -> None:
        """Start the AI insights generation process."""
        if self._generator is None:
            self._init_services()
        if self._generator is None:
            self.notify(
                "Cannot generate insights: "
                "services not initialized.",
                severity="error",
            )
            return

        # Show loading state
        loading = self.query_one("#insights-loading")
        loading.display = True
        content = self.query_one("#insights-content")
        content.display = False
        empty = self.query_one("#insights-empty", Static)
        empty.display = False

        # Disable buttons during generation
        btn_gen = self.query_one("#btn-generate", Button)
        btn_gen.disabled = True
        btn_regen = self.query_one("#btn-regenerate", Button)
        btn_regen.disabled = True

        self.run_worker(
            self._generate_insights(force_refresh),
            name="generate-insights",
            exclusive=True,
        )

    async def _generate_insights(
        self, force_refresh: bool
    ) -> None:
        """Generate insights for the current period."""
        if self._generator is None:
            return

        try:
            result = await self._generator.generate(
                period=self._current_period,
                force_refresh=force_refresh,
            )
            self._show_insights(result)
            self.notify(
                "Insights generated successfully.",
                severity="information",
            )
        except Exception as exc:
            log.error("Insights generation failed: %s", exc)
            self.notify(
                f"Failed to generate insights: {exc}",
                severity="error",
            )
        finally:
            # Restore UI state
            loading = self.query_one("#insights-loading")
            loading.display = False
            btn_gen = self.query_one("#btn-generate", Button)
            btn_gen.disabled = False
            btn_regen = self.query_one(
                "#btn-regenerate", Button
            )
            btn_regen.disabled = False
            self._check_and_display()

    # -----------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------

    def _default_period(self) -> str:
        """Return the current month as YYYY-MM."""
        today = date.today()
        return f"{today.year}-{today.month:02d}"
