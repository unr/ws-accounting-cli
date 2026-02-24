"""Budgets screen -- placeholder for Phase 2E."""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static


class BudgetsScreen(Screen):
    """Budget tracking and management -- coming soon."""

    BINDINGS = []

    def compose(self) -> ComposeResult:
        yield Static(
            "Budgets -- Coming Soon",
            id="placeholder",
            classes="screen-placeholder",
        )
