"""CSV Import screen -- placeholder for Phase 2E."""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static


class CSVImportScreen(Screen):
    """CSV import wizard -- coming soon."""

    BINDINGS = []

    def compose(self) -> ComposeResult:
        yield Static(
            "CSV Import -- Coming Soon",
            id="placeholder",
            classes="screen-placeholder",
        )
