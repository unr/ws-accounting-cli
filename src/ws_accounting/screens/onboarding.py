"""Onboarding screen -- first-run wizard for initial setup."""

from __future__ import annotations

import logging
import platform
import shutil
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import (
    Button,
    Checkbox,
    ContentSwitcher,
    Footer,
    Input,
    Label,
    Static,
)

from ws_accounting.config.defaults import DEFAULT_COMMODITY
from ws_accounting.config.paths import default_journal_dir, package_data_dir
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
# Step IDs
# ---------------------------------------------------------------------------

STEP_IDS = [
    "step-hledger",
    "step-journal",
    "step-currency",
    "step-api-key",
    "step-sample-data",
]


# ---------------------------------------------------------------------------
# OnboardingScreen
# ---------------------------------------------------------------------------


class OnboardingScreen(Screen):
    """First-run onboarding wizard -- 5-step linear flow."""

    CSS_PATH = "../styles/onboarding.tcss"
    BINDINGS = []

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._current_step: int = 0
        self._hledger_found: bool = False
        self._journal_choice: str = "new"  # "new" or "existing"
        self._journal_path: str = ""
        self._currency: str = DEFAULT_COMMODITY
        self._api_key: str = ""
        self._load_sample: bool = False

    def compose(self) -> ComposeResult:
        with Vertical(id="onboarding-outer"):
            yield Static(
                "ws-accounting Setup Wizard",
                id="onboarding-title",
            )
            yield Static(
                "Step 1 of 5",
                id="step-indicator",
            )

            with ContentSwitcher(
                id="onboarding-switcher", initial="step-hledger"
            ):
                # --- Step 1: hledger check ---
                with Vertical(id="step-hledger"):
                    yield Label(
                        "Step 1: Check hledger Installation",
                        classes="step-title",
                    )
                    yield Label(
                        "ws-accounting uses hledger as its accounting engine. "
                        "Let's verify it is installed.",
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
                    with Horizontal(classes="step-buttons"):
                        yield Button(
                            "Re-check",
                            variant="default",
                            id="btn-hledger-recheck",
                        )
                        yield Button(
                            "Next",
                            variant="primary",
                            id="btn-hledger-next",
                        )

                # --- Step 2: Journal setup ---
                with Vertical(id="step-journal"):
                    yield Label(
                        "Step 2: Journal Setup",
                        classes="step-title",
                    )
                    yield Label(
                        "Choose how to set up your journal file.",
                        classes="step-description",
                    )
                    with Horizontal(id="journal-choice-row"):
                        yield Button(
                            "Create New Journal",
                            variant="primary",
                            id="btn-journal-new",
                            classes="choice-btn",
                        )
                        yield Button(
                            "Use Existing Journal",
                            variant="default",
                            id="btn-journal-existing",
                            classes="choice-btn",
                        )
                    yield Static(
                        "",
                        id="journal-choice-info",
                        classes="info-text",
                    )
                    yield Input(
                        placeholder="Path to existing journal file...",
                        id="journal-path-input",
                        classes="hidden-field",
                    )
                    yield Static("", id="journal-error", classes="error-text")
                    with Horizontal(classes="step-buttons"):
                        yield Button(
                            "Back",
                            variant="default",
                            id="btn-journal-back",
                        )
                        yield Button(
                            "Next",
                            variant="primary",
                            id="btn-journal-next",
                        )

                # --- Step 3: Currency ---
                with Vertical(id="step-currency"):
                    yield Label(
                        "Step 3: Primary Currency",
                        classes="step-title",
                    )
                    yield Label(
                        "Enter your primary currency/commodity symbol.",
                        classes="step-description",
                    )
                    yield Label(
                        "Currency symbol:",
                        classes="field-label",
                    )
                    yield Input(
                        value=DEFAULT_COMMODITY,
                        placeholder="$",
                        id="currency-input",
                    )
                    with Horizontal(classes="step-buttons"):
                        yield Button(
                            "Back",
                            variant="default",
                            id="btn-currency-back",
                        )
                        yield Button(
                            "Next",
                            variant="primary",
                            id="btn-currency-next",
                        )

                # --- Step 4: API Key ---
                with Vertical(id="step-api-key"):
                    yield Label(
                        "Step 4: AI Features (Optional)",
                        classes="step-title",
                    )
                    yield Label(
                        "Enter your Claude API key to enable AI-powered "
                        "categorization and insights. You can skip this "
                        "and add it later in Settings.",
                        classes="step-description",
                    )
                    yield Label(
                        "Claude API key:",
                        classes="field-label",
                    )
                    yield Input(
                        placeholder="sk-ant-...",
                        id="api-key-input",
                        password=True,
                    )
                    with Horizontal(classes="step-buttons"):
                        yield Button(
                            "Back",
                            variant="default",
                            id="btn-api-back",
                        )
                        yield Button(
                            "Skip",
                            variant="default",
                            id="btn-api-skip",
                        )
                        yield Button(
                            "Next",
                            variant="primary",
                            id="btn-api-next",
                        )

                # --- Step 5: Sample data ---
                with Vertical(id="step-sample-data"):
                    yield Label(
                        "Step 5: Sample Data (Optional)",
                        classes="step-title",
                    )
                    yield Label(
                        "Load sample transactions to explore the app "
                        "before adding your own data. This creates 3 months "
                        "of realistic demo transactions.",
                        classes="step-description",
                    )
                    with Horizontal(id="sample-checkbox-row"):
                        yield Checkbox(
                            "Load sample data",
                            id="sample-data-checkbox",
                            value=False,
                        )
                    with Horizontal(classes="step-buttons"):
                        yield Button(
                            "Back",
                            variant="default",
                            id="btn-sample-back",
                        )
                        yield Button(
                            "Finish",
                            variant="success",
                            id="btn-finish",
                        )

        yield Footer()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_mount(self) -> None:
        """Check hledger on mount."""
        self._check_hledger()

    # ------------------------------------------------------------------
    # hledger detection
    # ------------------------------------------------------------------

    def _check_hledger(self) -> None:
        """Check whether hledger is on PATH."""
        hledger_path = shutil.which("hledger")
        status_widget = self.query_one("#hledger-status", Static)
        guide_widget = self.query_one("#hledger-install-guide", Static)

        if hledger_path:
            self._hledger_found = True
            status_widget.update(f"hledger found: {hledger_path}")
            status_widget.add_class("status-ok")
            status_widget.remove_class("status-error")
            guide_widget.update("")
        else:
            self._hledger_found = False
            status_widget.update(
                "hledger not found on PATH"
            )
            status_widget.add_class("status-error")
            status_widget.remove_class("status-ok")
            guide_widget.update(_get_install_guide())

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

    def on_button_pressed(self, event: Button.Pressed) -> None:  # noqa: C901
        """Route button presses to handlers."""
        bid = event.button.id

        # Step 1: hledger
        if bid == "btn-hledger-recheck":
            self._check_hledger()
        elif bid == "btn-hledger-next":
            self._handle_hledger_next()

        # Step 2: Journal
        elif bid == "btn-journal-new":
            self._select_journal_choice("new")
        elif bid == "btn-journal-existing":
            self._select_journal_choice("existing")
        elif bid == "btn-journal-back":
            self._go_to_step(0)
        elif bid == "btn-journal-next":
            self._handle_journal_next()

        # Step 3: Currency
        elif bid == "btn-currency-back":
            self._go_to_step(1)
        elif bid == "btn-currency-next":
            self._handle_currency_next()

        # Step 4: API Key
        elif bid == "btn-api-back":
            self._go_to_step(2)
        elif bid == "btn-api-skip":
            self._api_key = ""
            self._go_to_step(4)
        elif bid == "btn-api-next":
            self._handle_api_next()

        # Step 5: Sample data / Finish
        elif bid == "btn-sample-back":
            self._go_to_step(3)
        elif bid == "btn-finish":
            self._handle_finish()

    # ------------------------------------------------------------------
    # Step 1 handler
    # ------------------------------------------------------------------

    def _handle_hledger_next(self) -> None:
        """Advance past hledger check (warn if not found)."""
        if not self._hledger_found:
            self.notify(
                "hledger not found. Some features will not work "
                "until it is installed.",
                severity="warning",
            )
        self._go_to_step(1)

    # ------------------------------------------------------------------
    # Step 2 handler
    # ------------------------------------------------------------------

    def _select_journal_choice(self, choice: str) -> None:
        """Toggle between 'new' and 'existing' journal modes."""
        self._journal_choice = choice
        info_widget = self.query_one("#journal-choice-info", Static)
        path_input = self.query_one("#journal-path-input", Input)
        new_btn = self.query_one("#btn-journal-new", Button)
        existing_btn = self.query_one("#btn-journal-existing", Button)

        if choice == "new":
            journal_dir = default_journal_dir()
            info_widget.update(
                f"A new journal will be created at:\n{journal_dir / 'main.journal'}"
            )
            path_input.add_class("hidden-field")
            new_btn.variant = "primary"
            existing_btn.variant = "default"
        else:
            info_widget.update("Enter the path to your existing journal file:")
            path_input.remove_class("hidden-field")
            path_input.focus()
            new_btn.variant = "default"
            existing_btn.variant = "primary"

    def _handle_journal_next(self) -> None:
        """Validate journal choice and advance."""
        error_widget = self.query_one("#journal-error", Static)
        error_widget.update("")

        if self._journal_choice == "existing":
            path_input = self.query_one("#journal-path-input", Input)
            raw = path_input.value.strip()
            if not raw:
                error_widget.update("Please enter a journal file path.")
                return
            p = Path(raw).expanduser().resolve()
            if not p.exists():
                error_widget.update(f"File not found: {p}")
                return
            self._journal_path = str(p)
        else:
            # Will be created on finish
            journal_dir = default_journal_dir()
            self._journal_path = str(journal_dir / "main.journal")

        self._go_to_step(2)

    # ------------------------------------------------------------------
    # Step 3 handler
    # ------------------------------------------------------------------

    def _handle_currency_next(self) -> None:
        """Read currency value and advance."""
        currency_input = self.query_one("#currency-input", Input)
        val = currency_input.value.strip()
        if not val:
            self.notify("Currency cannot be empty.", severity="warning")
            return
        self._currency = val
        self._go_to_step(3)

    # ------------------------------------------------------------------
    # Step 4 handler
    # ------------------------------------------------------------------

    def _handle_api_next(self) -> None:
        """Read API key and advance."""
        api_input = self.query_one("#api-key-input", Input)
        self._api_key = api_input.value.strip()
        self._go_to_step(4)

    # ------------------------------------------------------------------
    # Step 5 / Finish
    # ------------------------------------------------------------------

    def _handle_finish(self) -> None:
        """Finalize onboarding: create files, save config."""
        checkbox = self.query_one("#sample-data-checkbox", Checkbox)
        self._load_sample = checkbox.value

        try:
            self._create_journal_structure()
            self._save_config()
            self.notify(
                "Setup complete! Welcome to ws-accounting.",
                severity="information",
            )
            self.app.pop_screen()
        except Exception as exc:
            log.exception("Onboarding finish failed")
            self.notify(
                f"Setup error: {exc}",
                severity="error",
            )

    def _create_journal_structure(self) -> None:
        """Create journal directory and files if using 'new' mode."""
        if self._journal_choice != "new":
            return

        journal_path = Path(self._journal_path)
        journal_dir = journal_path.parent
        journal_dir.mkdir(parents=True, exist_ok=True)

        # Copy default accounts journal
        data_dir = package_data_dir()
        default_accounts_src = data_dir / "default_accounts.journal"
        accounts_dest = journal_dir / "accounts.journal"

        if default_accounts_src.exists() and not accounts_dest.exists():
            shutil.copy2(default_accounts_src, accounts_dest)

        # Create main journal if it doesn't exist
        if not journal_path.exists():
            commodity_line = (
                f"commodity {self._currency}1,000.00"
                if self._currency == "$"
                else f"commodity {self._currency}"
            )
            journal_path.write_text(
                f"; ws-accounting main journal\n"
                f"{commodity_line}\n\n"
                f"include accounts.journal\n"
            )

        # Optionally copy sample data
        if self._load_sample:
            sample_src = data_dir / "sample_journal.journal"
            sample_dest = journal_dir / "sample_journal.journal"
            if sample_src.exists() and not sample_dest.exists():
                shutil.copy2(sample_src, sample_dest)
                # Add include to main journal
                main_text = journal_path.read_text()
                if "sample_journal.journal" not in main_text:
                    journal_path.write_text(
                        main_text.rstrip() + "\n\ninclude sample_journal.journal\n"
                    )

    def _save_config(self) -> None:
        """Persist configuration to TOML."""
        config = AppConfig.load()
        config.first_run = False
        config.journal_path = self._journal_path
        config.currency = self._currency
        if self._api_key:
            config.ai.api_key = self._api_key
        config.save()
