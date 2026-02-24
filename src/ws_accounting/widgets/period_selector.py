"""Reusable period selector widget."""

from datetime import date

from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Button, Static


class PeriodSelector(Widget):
    """Compound widget for selecting time periods."""

    DEFAULT_CSS = """
    PeriodSelector {
        height: 1;
        layout: horizontal;
    }
    PeriodSelector Button {
        min-width: 3;
        width: 3;
    }
    PeriodSelector #period-label {
        width: auto;
        min-width: 12;
        text-align: center;
        padding: 0 1;
    }
    """

    period = reactive("")

    class PeriodChanged(Message):
        def __init__(self, period: str) -> None:
            super().__init__()
            self.period = period

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        today = date.today()
        self.period = f"{today.year}-{today.month:02d}"
        self._year = today.year
        self._month = today.month
        self._mode = "month"

    def compose(self):
        yield Button("<", id="period-prev")
        yield Static(self._format_label(), id="period-label")
        yield Button(">", id="period-next")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "period-prev":
            self._move(-1)
        elif event.button.id == "period-next":
            self._move(1)

    def _move(self, direction: int) -> None:
        if self._mode == "month":
            self._month += direction
            if self._month > 12:
                self._month = 1
                self._year += 1
            elif self._month < 1:
                self._month = 12
                self._year -= 1
        elif self._mode == "year":
            self._year += direction

        self.period = f"{self._year}-{self._month:02d}"
        try:
            self.query_one("#period-label").update(self._format_label())
        except Exception:
            pass
        self.post_message(self.PeriodChanged(self.period))

    def _format_label(self) -> str:
        months = [
            "Jan", "Feb", "Mar", "Apr", "May", "Jun",
            "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
        ]
        if self._mode == "month":
            return f"{months[self._month - 1]} {self._year}"
        elif self._mode == "year":
            return str(self._year)
        return self.period
