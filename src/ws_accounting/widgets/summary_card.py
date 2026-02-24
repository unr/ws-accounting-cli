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

    def __init__(self, title: str = "", show_sign: bool = True, **kwargs) -> None:
        super().__init__(**kwargs)
        self._title = title
        self._value = Decimal(0)
        self._show_sign = show_sign

    def compose(self):
        yield Static(self._title, classes="card-title")
        yield AmountDisplay(self._value, show_sign=self._show_sign)

    def update_value(self, value: Decimal, commodity: str | None = None) -> None:
        self._value = value
        try:
            amount_display = self.query_one(AmountDisplay)
            amount_display.set_amount(value, commodity)
        except Exception:
            pass

    def update_amount(self, value: Decimal, commodity: str | None = None) -> None:
        """Alias for update_value, matching the dashboard API."""
        self.update_value(value, commodity)

    def show_error(self, message: str) -> None:
        try:
            amount_display = self.query_one(AmountDisplay)
            amount_display.update(message)
        except Exception:
            pass
