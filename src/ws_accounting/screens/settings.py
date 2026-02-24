"""Settings screen -- application configuration management."""

from __future__ import annotations

import logging

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import (
    Button,
    Footer,
    Input,
    Label,
    Select,
    Static,
    Switch,
    TabbedContent,
    TabPane,
)

from ws_accounting.config.settings import AppConfig

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AI_MODEL_OPTIONS: list[tuple[str, str]] = [
    ("Claude Sonnet 4.5", "claude-sonnet-4-5-20250929"),
    ("Claude Haiku 4.5", "claude-haiku-4-5-20251001"),
]

MONTH_OPTIONS: list[tuple[str, int]] = [
    ("January", 1),
    ("February", 2),
    ("March", 3),
    ("April", 4),
    ("May", 5),
    ("June", 6),
    ("July", 7),
    ("August", 8),
    ("September", 9),
    ("October", 10),
    ("November", 11),
    ("December", 12),
]

IMPORT_STATUS_OPTIONS: list[tuple[str, str]] = [
    ("* (Cleared)", "*"),
    ("! (Pending)", "!"),
]


# ---------------------------------------------------------------------------
# SettingsScreen
# ---------------------------------------------------------------------------


class SettingsScreen(Screen):
    """Application settings with tabbed sections."""

    CSS_PATH = "../styles/settings.tcss"
    BINDINGS = []

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._config: AppConfig = AppConfig.load()

    def compose(self) -> ComposeResult:
        yield Static("Settings", id="settings-title")

        with TabbedContent(id="settings-tabs"):
            # ── General Tab ──────────────────────────────
            with TabPane("General", id="tab-general"):
                with Vertical(classes="settings-form"):
                    yield Label(
                        "Journal file path:",
                        classes="field-label",
                    )
                    yield Input(
                        value=self._config.journal_path,
                        placeholder="~/finances/main.journal",
                        id="input-journal-path",
                    )

                    yield Label(
                        "Data directory:",
                        classes="field-label",
                    )
                    yield Input(
                        value=self._config.data_dir,
                        placeholder="(default: platform data dir)",
                        id="input-data-dir",
                    )

                    yield Label(
                        "Fiscal year start month:",
                        classes="field-label",
                    )
                    yield Select(
                        MONTH_OPTIONS,
                        value=self._config.fiscal_year_start,
                        id="select-fiscal-month",
                        allow_blank=False,
                    )

                    with Horizontal(classes="switch-row"):
                        yield Label(
                            "Dark theme:",
                            classes="switch-label",
                        )
                        yield Switch(
                            value=self._config.theme == "financial-dark",
                            id="switch-theme",
                        )

                    yield Button(
                        "Save General",
                        variant="primary",
                        id="btn-save-general",
                        classes="save-btn",
                    )

            # ── AI Tab ───────────────────────────────────
            with TabPane("AI", id="tab-ai"):
                with Vertical(classes="settings-form"):
                    yield Label(
                        "Claude API key:",
                        classes="field-label",
                    )
                    yield Input(
                        value=self._config.ai.api_key,
                        placeholder="sk-ant-...",
                        id="input-api-key",
                        password=True,
                    )

                    yield Label(
                        "Model:",
                        classes="field-label",
                    )
                    yield Select(
                        AI_MODEL_OPTIONS,
                        value=self._config.ai.model,
                        id="select-ai-model",
                        allow_blank=False,
                    )

                    with Horizontal(classes="switch-row"):
                        yield Label(
                            "Enable AI features:",
                            classes="switch-label",
                        )
                        yield Switch(
                            value=self._config.ai.enabled,
                            id="switch-ai-enabled",
                        )

                    yield Static(
                        "AI features use the Claude API which may incur "
                        "token usage costs. Categorization typically uses "
                        "~200 tokens per transaction batch.",
                        id="ai-usage-note",
                        classes="info-note",
                    )

                    yield Button(
                        "Save AI Settings",
                        variant="primary",
                        id="btn-save-ai",
                        classes="save-btn",
                    )

            # ── Import Tab ───────────────────────────────
            with TabPane("Import", id="tab-import"):
                with Vertical(classes="settings-form"):
                    yield Label(
                        "Default import status:",
                        classes="field-label",
                    )
                    yield Select(
                        IMPORT_STATUS_OPTIONS,
                        value=self._config.import_config.default_status,
                        id="select-import-status",
                        allow_blank=False,
                    )

                    yield Label(
                        "Rules directory:",
                        classes="field-label",
                    )
                    yield Input(
                        value=self._config.import_config.rules_dir,
                        placeholder="(default: journal dir/rules/)",
                        id="input-rules-dir",
                    )

                    yield Button(
                        "Save Import Settings",
                        variant="primary",
                        id="btn-save-import",
                        classes="save-btn",
                    )

            # ── Appearance Tab ───────────────────────────
            with TabPane("Appearance", id="tab-appearance"):
                with Vertical(classes="settings-form"):
                    with Horizontal(classes="switch-row"):
                        yield Label(
                            "Dark theme:",
                            classes="switch-label",
                        )
                        yield Switch(
                            value=self._config.theme == "financial-dark",
                            id="switch-appearance-theme",
                        )

                    with Horizontal(classes="switch-row"):
                        yield Label(
                            "Compact mode:",
                            classes="switch-label",
                        )
                        yield Switch(
                            value=self._config.compact_mode,
                            id="switch-compact-mode",
                        )

                    yield Button(
                        "Save Appearance",
                        variant="primary",
                        id="btn-save-appearance",
                        classes="save-btn",
                    )

        yield Footer()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_mount(self) -> None:
        """Reload config values into widgets on mount."""
        self._load_config_into_widgets()

    def _load_config_into_widgets(self) -> None:
        """Populate form fields from the current config."""
        self._config = AppConfig.load()

        try:
            self.query_one("#input-journal-path", Input).value = (
                self._config.journal_path
            )
            self.query_one("#input-data-dir", Input).value = (
                self._config.data_dir
            )
            self.query_one("#select-fiscal-month", Select).value = (
                self._config.fiscal_year_start
            )
            self.query_one("#switch-theme", Switch).value = (
                self._config.theme == "financial-dark"
            )

            self.query_one("#input-api-key", Input).value = (
                self._config.ai.api_key
            )
            self.query_one("#select-ai-model", Select).value = (
                self._config.ai.model
            )
            self.query_one("#switch-ai-enabled", Switch).value = (
                self._config.ai.enabled
            )

            self.query_one("#select-import-status", Select).value = (
                self._config.import_config.default_status
            )
            self.query_one("#input-rules-dir", Input).value = (
                self._config.import_config.rules_dir
            )

            self.query_one("#switch-appearance-theme", Switch).value = (
                self._config.theme == "financial-dark"
            )
            self.query_one("#switch-compact-mode", Switch).value = (
                self._config.compact_mode
            )
        except Exception:
            log.debug("Some settings widgets not yet mounted", exc_info=True)

    # ------------------------------------------------------------------
    # Theme toggle live preview
    # ------------------------------------------------------------------

    def on_switch_changed(self, event: Switch.Changed) -> None:
        """Handle theme toggle switches for live preview."""
        if event.switch.id in ("switch-theme", "switch-appearance-theme"):
            theme_name = "financial-dark" if event.value else "financial-light"
            self.app.theme = theme_name
            # Keep the other theme switch in sync
            other_id = (
                "switch-appearance-theme"
                if event.switch.id == "switch-theme"
                else "switch-theme"
            )
            try:
                other = self.query_one(f"#{other_id}", Switch)
                if other.value != event.value:
                    other.value = event.value
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Route save buttons to their handlers."""
        bid = event.button.id
        if bid == "btn-save-general":
            self._save_general()
        elif bid == "btn-save-ai":
            self._save_ai()
        elif bid == "btn-save-import":
            self._save_import()
        elif bid == "btn-save-appearance":
            self._save_appearance()

    # ------------------------------------------------------------------
    # Save handlers
    # ------------------------------------------------------------------

    def _save_general(self) -> None:
        """Save general settings."""
        self._config.journal_path = (
            self.query_one("#input-journal-path", Input).value.strip()
        )
        self._config.data_dir = (
            self.query_one("#input-data-dir", Input).value.strip()
        )
        fiscal_sel = self.query_one("#select-fiscal-month", Select)
        if fiscal_sel.value is not Select.BLANK:
            self._config.fiscal_year_start = int(fiscal_sel.value)
        theme_switch = self.query_one("#switch-theme", Switch)
        self._config.theme = (
            "financial-dark" if theme_switch.value else "financial-light"
        )

        self._config.save()
        self.notify("General settings saved.", severity="information")

    def _save_ai(self) -> None:
        """Save AI settings."""
        self._config.ai.api_key = (
            self.query_one("#input-api-key", Input).value.strip()
        )
        model_sel = self.query_one("#select-ai-model", Select)
        if model_sel.value is not Select.BLANK:
            self._config.ai.model = str(model_sel.value)
        self._config.ai.enabled = (
            self.query_one("#switch-ai-enabled", Switch).value
        )

        self._config.save()
        self.notify("AI settings saved.", severity="information")

    def _save_import(self) -> None:
        """Save import settings."""
        status_sel = self.query_one("#select-import-status", Select)
        if status_sel.value is not Select.BLANK:
            self._config.import_config.default_status = str(status_sel.value)
        self._config.import_config.rules_dir = (
            self.query_one("#input-rules-dir", Input).value.strip()
        )

        self._config.save()
        self.notify("Import settings saved.", severity="information")

    def _save_appearance(self) -> None:
        """Save appearance settings."""
        theme_switch = self.query_one("#switch-appearance-theme", Switch)
        self._config.theme = (
            "financial-dark" if theme_switch.value else "financial-light"
        )
        self._config.compact_mode = (
            self.query_one("#switch-compact-mode", Switch).value
        )

        self._config.save()
        self.notify("Appearance settings saved.", severity="information")
