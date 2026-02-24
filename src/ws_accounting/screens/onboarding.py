"""Onboarding screen -- first-run setup wizard (4-step ModalScreen)."""

from __future__ import annotations

import logging
import platform
import shutil
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Center, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    ContentSwitcher,
    Input,
    Label,
    Select,
    Static,
)

from ws_accounting.config.defaults import DEFAULT_COMMODITY
from ws_accounting.config.paths import get_default_journal_dir
from ws_accounting.config.settings import AppConfig

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Platform-specific install instructions
# ---------------------------------------------------------------------------

_INSTALL_GUIDES: dict[str, str] = {
    "Darwin": (
        "Install hledger on macOS:\n\n"
        "  brew install hledger\n\n"
        "Or download from https://hledger.org/install.html"
    ),
    "Linux": (
        "Install hledger on Linux:\n\n"
        "  # Debian/Ubuntu\n"
        "  sudo apt install hledger\n\n"
        "  # Or use the official install script:\n"
        "  curl -sO https://raw.githubusercontent.com/"
        "simonmichael/hledger/master/hledger-install/"
        "hledger-install.sh\n"
        "  bash hledger-install.sh\n\n"
        "Or download from https://hledger.org/install.html"
    ),
    "Windows": (
        "Install hledger on Windows:\n\n"
        "  scoop install hledger\n\n"
        "  # Or via chocolatey:\n"
        "  choco install hledger\n\n"
        "Or download from https://hledger.org/install.html"
    ),
}


def _get_install_guide() -> str:
    """Return platform-specific hledger install instructions."""
    system = platform.system()
    return _INSTALL_GUIDES.get(system, _INSTALL_GUIDES["Linux"])


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

STEP_IDS = [
    "step-hledger",
    "step-preferences",
    "step-api-key",
    "step-finish",
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

FINISH_CHOICES: list[tuple[str, str]] = [
    ("Start empty", "empty"),
    ("Load sample data", "sample"),
    ("Import first CSV", "import"),
]


# ---------------------------------------------------------------------------
# OnboardingScreen
# ---------------------------------------------------------------------------


class OnboardingScreen(ModalScreen[bool]):
    """First-run setup wizard -- 4-step modal overlay."""

    CSS_PATH = "../styles/onboarding.tcss"
    BINDINGS = []

    DEFAULT_CSS = """
    OnboardingScreen {
        align: center middle;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._current_step: int = 0
        self._hledger_found: bool = False
        self._hledger_version: str = ""

    def compose(self) -> ComposeResult:
        with Vertical(id="onboarding-container"):
            yield Static(
                "ws-accounting Setup",
                id="onboarding-title",
            )
            yield Static(
                "Step 1 of 4",
                id="step-indicator",
            )

            with ContentSwitcher(
                id="onboarding-switcher", initial="step-hledger"
            ):
                # ── Step 1: hledger check + Journal ──
                with Vertical(id="step-hledger"):
                    yield Label(
                        "Check hledger + Journal Setup",
                        classes="step-title",
                    )
                    yield Label(
                        "ws-accounting uses hledger as its accounting "
                        "engine. Let's verify it is installed.",
                        classes="step-description",
                    )
                    yield Static(
                        "Checking...",
                        id="hledger-status",
                        classes="status-box",
                    )
                    yield Static(
                        "",
                        id="hledger-install-guide",
                        classes="install-guide",
                    )
                    yield Label(
                        "Journal directory:",
                        classes="field-label",
                    )
                    yield Input(
                        value=str(get_default_journal_dir()),
                        placeholder="~/finances",
                        id="input-journal-dir",
                    )
                    with Horizontal(classes="step-buttons"):
                        yield Button(
                            "Check Again",
                            variant="default",
                            id="btn-hledger-recheck",
                        )
                        yield Button(
                            "Next",
                            variant="primary",
                            id="btn-step1-next",
                        )

                # ── Step 2: Currency + Preferences ──
                with Vertical(id="step-preferences"):
                    yield Label(
                        "Currency & Preferences",
                        classes="step-title",
                    )
                    yield Label(
                        "Set your primary currency and fiscal year start.",
                        classes="step-description",
                    )
                    yield Label(
                        "Currency symbol:",
                        classes="field-label",
                    )
                    yield Input(
                        value=DEFAULT_COMMODITY,
                        placeholder="$",
                        id="input-onb-currency",
                    )
                    yield Label(
                        "Fiscal year start month:",
                        classes="field-label",
                    )
                    yield Select(
                        MONTH_OPTIONS,
                        value=1,
                        id="select-onb-fiscal",
                        allow_blank=False,
                    )
                    with Horizontal(classes="step-buttons"):
                        yield Button(
                            "Back",
                            variant="default",
                            id="btn-step2-back",
                        )
                        yield Button(
                            "Skip",
                            variant="default",
                            id="btn-step2-skip",
                        )
                        yield Button(
                            "Next",
                            variant="primary",
                            id="btn-step2-next",
                        )

                # ── Step 3: API Key (optional) ──
                with Vertical(id="step-api-key"):
                    yield Label(
                        "AI Features (Optional)",
                        classes="step-title",
                    )
                    yield Label(
                        "Enter your Claude API key to enable AI-powered "
                        "categorization and insights. You can always add "
                        "this later in Settings.",
                        classes="step-description",
                    )
                    yield Label(
                        "Claude API key:",
                        classes="field-label",
                    )
                    yield Input(
                        placeholder="sk-ant-...",
                        id="input-onb-api-key",
                        password=True,
                    )
                    with Horizontal(classes="step-buttons"):
                        yield Button(
                            "Back",
                            variant="default",
                            id="btn-step3-back",
                        )
                        yield Button(
                            "Skip",
                            variant="warning",
                            id="btn-step3-skip",
                        )
                        yield Button(
                            "Next",
                            variant="primary",
                            id="btn-step3-next",
                        )

                # ── Step 4: Get Started ──
                with Vertical(id="step-finish"):
                    yield Label(
                        "Get Started",
                        classes="step-title",
                    )
                    yield Label(
                        "Choose how you want to begin:",
                        classes="step-description",
                    )
                    yield Select(
                        FINISH_CHOICES,
                        value="empty",
                        id="select-finish-choice",
                        allow_blank=False,
                    )
                    yield Static(
                        "",
                        id="finish-info",
                        classes="info-text",
                    )
                    with Horizontal(classes="step-buttons"):
                        yield Button(
                            "Back",
                            variant="default",
                            id="btn-step4-back",
                        )
                        yield Button(
                            "Finish Setup",
                            variant="success",
                            id="btn-finish",
                        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_mount(self) -> None:
        """Check hledger installation on mount."""
        self._check_hledger()

    # ------------------------------------------------------------------
    # hledger detection
    # ------------------------------------------------------------------

    def _check_hledger(self) -> None:
        """Quick synchronous check: is hledger on PATH?"""
        hledger_path = shutil.which("hledger")
        status_widget = self.query_one("#hledger-status", Static)
        guide_widget = self.query_one("#hledger-install-guide", Static)

        if hledger_path:
            self._hledger_found = True
            status_widget.update(f"hledger found: {hledger_path}")
            status_widget.add_class("status-ok")
            status_widget.remove_class("status-error")
            guide_widget.update("")
            # Also run async version check
            self.run_worker(self._async_version_check(), exclusive=True)
        else:
            self._hledger_found = False
            status_widget.update("hledger not found on PATH")
            status_widget.add_class("status-error")
            status_widget.remove_class("status-ok")
            guide_widget.update(_get_install_guide())

    async def _async_version_check(self) -> None:
        """Run async hledger version check for detailed info."""
        try:
            from ws_accounting.core.hledger import HLedgerGateway

            version = await HLedgerGateway.check_version()
            self._hledger_version = version
            status_widget = self.query_one("#hledger-status", Static)
            status_widget.update(f"hledger v{version} found")
        except Exception as exc:
            log.debug("hledger version check failed: %s", exc)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _go_to_step(self, step: int) -> None:
        """Switch to a wizard step by index."""
        if step < 0 or step >= len(STEP_IDS):
            return
        self._current_step = step
        switcher = self.query_one("#onboarding-switcher", ContentSwitcher)
        switcher.current = STEP_IDS[step]
        indicator = self.query_one("#step-indicator", Static)
        indicator.update(f"Step {step + 1} of {len(STEP_IDS)}")

    # ------------------------------------------------------------------
    # Button routing
    # ------------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Route all button presses."""
        bid = event.button.id

        # Step 1
        if bid == "btn-hledger-recheck":
            self._check_hledger()
        elif bid == "btn-step1-next":
            self._handle_step1_next()

        # Step 2
        elif bid == "btn-step2-back":
            self._go_to_step(0)
        elif bid == "btn-step2-skip":
            self._go_to_step(2)
        elif bid == "btn-step2-next":
            self._handle_step2_next()

        # Step 3
        elif bid == "btn-step3-back":
            self._go_to_step(1)
        elif bid == "btn-step3-skip":
            self._go_to_step(3)
        elif bid == "btn-step3-next":
            self._handle_step3_next()

        # Step 4
        elif bid == "btn-step4-back":
            self._go_to_step(2)
        elif bid == "btn-finish":
            self._handle_finish()

    # ------------------------------------------------------------------
    # Step handlers
    # ------------------------------------------------------------------

    def _handle_step1_next(self) -> None:
        """Validate step 1 and advance."""
        if not self._hledger_found:
            self.notify(
                "hledger not found. Some features will not work "
                "until it is installed.",
                severity="warning",
            )
        self._go_to_step(1)

    def _handle_step2_next(self) -> None:
        """Read currency + fiscal year and advance."""
        currency_input = self.query_one("#input-onb-currency", Input)
        val = currency_input.value.strip()
        if not val:
            self.notify("Currency cannot be empty.", severity="warning")
            return
        self._go_to_step(2)

    def _handle_step3_next(self) -> None:
        """Read API key and advance."""
        self._go_to_step(3)

    def _handle_finish(self) -> None:
        """Finalize onboarding: create journal dir, save config, dismiss."""
        try:
            # Gather values from widgets
            journal_dir_str = (
                self.query_one("#input-journal-dir", Input).value.strip()
            )
            currency = (
                self.query_one("#input-onb-currency", Input).value.strip()
                or DEFAULT_COMMODITY
            )
            fiscal_sel = self.query_one("#select-onb-fiscal", Select)
            fiscal_month = (
                int(fiscal_sel.value)
                if fiscal_sel.value is not Select.BLANK
                else 1
            )
            api_key = (
                self.query_one("#input-onb-api-key", Input).value.strip()
            )
            finish_sel = self.query_one("#select-finish-choice", Select)
            finish_choice = (
                str(finish_sel.value)
                if finish_sel.value is not Select.BLANK
                else "empty"
            )

            # Ensure journal directory exists
            journal_dir = Path(journal_dir_str).expanduser().resolve()
            journal_dir.mkdir(parents=True, exist_ok=True)

            # Create a minimal journal file if none exists
            main_journal = journal_dir / "main.journal"
            if not main_journal.exists():
                commodity_line = (
                    f"commodity {currency}1,000.00"
                    if currency == "$"
                    else f"commodity {currency}"
                )
                main_journal.write_text(
                    f"; ws-accounting main journal\n"
                    f"{commodity_line}\n\n"
                )

            # Save config
            config = AppConfig.load()
            config.journal_dir = journal_dir
            config.currency = currency
            config.fiscal_year_start = fiscal_month
            config.first_run = False
            if api_key:
                config.ai.api_key = api_key
            config.save()

            # Handle finish choice
            if finish_choice == "import":
                self.dismiss(True)
                # Switch to CSV import after dismiss
                self.app.call_later(
                    lambda: self.app.action_switch_to("csv_import")
                )
                return

            self.notify(
                "Setup complete! Welcome to ws-accounting.",
                severity="information",
            )
            self.dismiss(True)

        except Exception as exc:
            log.exception("Onboarding finish failed")
            self.notify(f"Setup error: {exc}", severity="error")
