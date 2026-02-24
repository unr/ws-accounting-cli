"""AI Insights screen -- placeholder for Phase 2E."""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static


class InsightsScreen(Screen):
    """AI-powered financial insights -- coming soon."""

    BINDINGS = []

    def compose(self) -> ComposeResult:
        yield Static(
            "AI Insights -- Coming Soon",
            id="placeholder",
            classes="screen-placeholder",
        )
