"""Date period selector widget for filtering by time range."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Input, Select, Static


PERIOD_OPTIONS: list[tuple[str, str]] = [
    ("This Month", "thismonth"),
    ("Last Month", "lastmonth"),
    ("This Quarter", "thisquarter"),
    ("Last Quarter", "lastquarter"),
    ("This Year", "thisyear"),
    ("Last Year", "lastyear"),
    ("All Time", ""),
    ("Custom", "custom"),
]


class PeriodSelector(Widget):
    """Dropdown + optional custom date inputs for selecting a date period."""

    DEFAULT_CSS = """
    PeriodSelector {
        layout: horizontal;
        height: auto;
        width: auto;
    }
    PeriodSelector #period-select {
        width: 20;
    }
    PeriodSelector .date-input {
        width: 14;
        margin-left: 1;
    }
    PeriodSelector .date-separator {
        width: 4;
        content-align: center middle;
        padding: 0 1;
    }
    PeriodSelector .custom-range {
        display: none;
    }
    PeriodSelector .custom-range.visible {
        display: block;
    }
    """

    period: reactive[str] = reactive("thismonth")

    class PeriodChanged(Message):
        """Emitted when the selected period changes."""

        def __init__(self, period: str) -> None:
            self.period = period
            super().__init__()

    def compose(self) -> ComposeResult:
        yield Select(
            [(label, value) for label, value in PERIOD_OPTIONS],
            value="thismonth",
            id="period-select",
            allow_blank=False,
        )
        with Horizontal(classes="custom-range", id="custom-range"):
            yield Input(
                placeholder="YYYY-MM-DD",
                id="date-from",
                classes="date-input",
            )
            yield Static(" to ", classes="date-separator")
            yield Input(
                placeholder="YYYY-MM-DD",
                id="date-to",
                classes="date-input",
            )

    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle period dropdown selection."""
        value = str(event.value) if event.value is not None else ""
        custom_range = self.query_one("#custom-range")
        if value == "custom":
            custom_range.add_class("visible")
            self._emit_custom_period()
        else:
            custom_range.remove_class("visible")
            self.period = value
            self.post_message(self.PeriodChanged(value))

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle custom date input changes."""
        if event.input.id in ("date-from", "date-to"):
            self._emit_custom_period()

    def _emit_custom_period(self) -> None:
        """Build and emit a custom period string from date inputs."""
        try:
            date_from = self.query_one("#date-from", Input).value.strip()
            date_to = self.query_one("#date-to", Input).value.strip()
        except Exception:
            return

        if date_from and date_to:
            period = f"{date_from} to {date_to}"
            self.period = period
            self.post_message(self.PeriodChanged(period))
        elif date_from:
            self.period = date_from
            self.post_message(self.PeriodChanged(date_from))
