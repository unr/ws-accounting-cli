"""Onboarding screen -- placeholder for Phase 2E."""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Button, Static


class OnboardingScreen(Screen):
    """First-run onboarding wizard -- coming soon."""

    BINDINGS = []

    def compose(self) -> ComposeResult:
        yield Static(
            "Welcome to ws-accounting!\n\n"
            "This onboarding wizard will help you get started.\n\n"
            "Coming soon -- press the button below to continue.",
            id="onboarding-welcome",
            classes="screen-placeholder",
        )
        yield Button(
            "Get Started",
            id="btn-get-started",
            variant="primary",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Close onboarding and go to dashboard."""
        if event.button.id == "btn-get-started":
            self.app.pop_screen()
