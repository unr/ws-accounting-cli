"""Budget progress bar with gradient coloring."""

from decimal import Decimal

from textual.widgets import Static


class BudgetBar(Static):
    """Progress bar showing budget spent vs allocated with gradient."""

    DEFAULT_CSS = """
    BudgetBar {
        height: 1;
        padding: 0 1;
    }
    """

    def __init__(
        self,
        category: str = "",
        spent: Decimal = Decimal(0),
        budget: Decimal = Decimal(0),
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._category = category
        self._spent = spent
        self._budget = budget

    def on_mount(self) -> None:
        self._render()

    def update_values(
        self, category: str, spent: Decimal, budget: Decimal
    ) -> None:
        self._category = category
        self._spent = spent
        self._budget = budget
        self._render()

    def _render(self) -> None:
        if self._budget <= 0:
            pct = 0
        else:
            pct = min(int((self._spent / self._budget) * 100), 100)

        bar_width = 10
        filled = int(bar_width * pct / 100)
        empty = bar_width - filled

        bar = "\u2588" * filled + "\u2591" * empty

        warn = "\u26a0" if pct >= 90 else " "
        name = self._category.split(":")[-1] if ":" in self._category else self._category
        self.update(
            f"{name:<12} {bar} {pct:>3}%  ${self._spent:>8,.2f}/${self._budget:,.2f} {warn}"
        )
