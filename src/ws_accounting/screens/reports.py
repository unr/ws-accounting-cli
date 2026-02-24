"""Reports screen -- placeholder for Phase 2E."""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static


class ReportsScreen(Screen):
    """Financial reports and charts -- coming soon."""

    BINDINGS = []

    def compose(self) -> ComposeResult:
        yield Static(
            "Reports -- Coming Soon",
            id="placeholder",
            classes="screen-placeholder",
        )
