"""Accessible amount display widget with +/- prefix and color."""

from decimal import Decimal

from textual.widgets import Static


class AmountDisplay(Static):
    """Display a monetary amount with accessible color and sign prefix."""

    DEFAULT_CSS = """
    AmountDisplay {
        width: auto;
        height: 1;
    }
    AmountDisplay.positive {
        color: $success;
    }
    AmountDisplay.negative {
        color: $error;
    }
    AmountDisplay.zero {
        color: $text-muted;
    }
    """

    def __init__(
        self,
        amount: Decimal | None = None,
        commodity: str = "$",
        show_sign: bool = True,
        **kwargs,
    ) -> None:
        self._amount = amount or Decimal("0")
        self._commodity = commodity
        self._show_sign = show_sign
        super().__init__(**kwargs)

    def on_mount(self) -> None:
        self._update_display()

    def _update_display(self) -> None:
        """Re-render the amount text and apply the correct CSS class."""
        abs_amount = abs(self._amount)
        formatted = f"{abs_amount:,.2f}"

        if self._amount > 0:
            prefix = "+" if self._show_sign else ""
            text = f"{prefix}{self._commodity}{formatted}"
            self.remove_class("negative", "zero")
            self.add_class("positive")
        elif self._amount < 0:
            text = f"-{self._commodity}{formatted}"
            self.remove_class("positive", "zero")
            self.add_class("negative")
        else:
            text = f"{self._commodity}{formatted}"
            self.remove_class("positive", "negative")
            self.add_class("zero")

        self.update(text)

    def set_amount(
        self, amount: Decimal, commodity: str | None = None
    ) -> None:
        """Update the displayed amount and optionally the commodity."""
        self._amount = amount
        if commodity is not None:
            self._commodity = commodity
        self._update_display()

    # Alias for API compatibility
    update_amount = set_amount
