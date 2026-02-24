"""Summary card widget for dashboard."""

from decimal import Decimal

from textual.widgets import Static

from ws_accounting.widgets.amount_display import AmountDisplay


class SummaryCard(Static):
    """Dashboard summary card showing a title and amount."""

    DEFAULT_CSS = """
    SummaryCard {
        height: auto;
        min-height: 3;
        padding: 0 1;
        border: solid $panel;
    }
    SummaryCard .card-title {
        color: $text-muted;
        text-style: bold;
    }
    """

    def __init__(self, title: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self._title = title
        self._value = Decimal(0)

    def compose(self):
        yield Static(self._title, classes="card-title")
        yield AmountDisplay(self._value)

    def update_value(self, value: Decimal) -> None:
        self._value = value
        try:
            amount_display = self.query_one(AmountDisplay)
            amount_display.update_amount(value)
        except Exception:
            pass

    def show_error(self, message: str) -> None:
        try:
            amount_display = self.query_one(AmountDisplay)
            amount_display.update(message)
        except Exception:
            pass
