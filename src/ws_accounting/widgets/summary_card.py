"""Summary card widget for dashboard stat display."""

from decimal import Decimal

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Label, Sparkline

from ws_accounting.widgets.amount_display import AmountDisplay


class SummaryCard(Widget):
    """A card showing a title, large amount, and optional sparkline."""

    DEFAULT_CSS = """
    SummaryCard {
        height: auto;
        min-height: 5;
        border: round $primary;
        padding: 1 2;
        margin: 0 1;
    }
    SummaryCard .card-title {
        text-style: bold;
        color: $text-muted;
        margin-bottom: 0;
    }
    SummaryCard AmountDisplay {
        text-style: bold;
        width: 100%;
    }
    SummaryCard Sparkline {
        height: 1;
        margin-top: 1;
    }
    """

    def __init__(
        self,
        title: str,
        amount: Decimal | None = None,
        commodity: str = "$",
        show_sign: bool = True,
        sparkline_data: list[float] | None = None,
        **kwargs,
    ) -> None:
        self._card_title = title
        self._amount = amount or Decimal("0")
        self._commodity = commodity
        self._show_sign = show_sign
        self._sparkline_data = sparkline_data
        super().__init__(**kwargs)

    def compose(self) -> ComposeResult:
        yield Label(self._card_title, classes="card-title")
        yield AmountDisplay(
            amount=self._amount,
            commodity=self._commodity,
            show_sign=self._show_sign,
            id="card-amount",
        )
        if self._sparkline_data:
            yield Sparkline(
                self._sparkline_data,
                id="card-sparkline",
            )

    def update_amount(
        self,
        amount: Decimal,
        commodity: str | None = None,
    ) -> None:
        """Update the displayed amount."""
        self._amount = amount
        try:
            display = self.query_one("#card-amount", AmountDisplay)
            display.set_amount(amount, commodity)
        except Exception:
            pass
