"""Budget tracking math -- category tracking mode with rollover."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class BudgetStatus:
    """Status of a single budget category for a given period."""

    category: str
    budgeted: Decimal
    spent: Decimal
    remaining: Decimal
    percentage: float  # 0.0 to 1.0+
    rollover_amount: Decimal
    is_over: bool

    @property
    def display_percentage(self) -> int:
        """Percentage clamped to 0-999 for display."""
        return min(999, max(0, int(self.percentage * 100)))


def calculate_budget_status(
    category: str,
    budgeted: Decimal,
    spent: Decimal,
    rollover: Decimal = Decimal("0"),
    rollover_cap: Decimal | None = None,
) -> BudgetStatus:
    """Calculate budget status for a category.

    Args:
        category: Account name (e.g. "expenses:food:groceries").
        budgeted: Base budget amount for the period.
        spent: Amount spent so far in the period.
        rollover: Unspent amount carried from the previous period.
        rollover_cap: Maximum rollover allowed. None means no cap.

    Returns:
        BudgetStatus with computed remaining, percentage, etc.
    """
    effective_rollover = rollover
    if rollover_cap is not None and rollover > rollover_cap:
        effective_rollover = rollover_cap

    effective_budget = budgeted + effective_rollover
    remaining = effective_budget - spent
    percentage = (
        float(spent / effective_budget) if effective_budget > 0 else 0.0
    )

    return BudgetStatus(
        category=category,
        budgeted=effective_budget,
        spent=spent,
        remaining=remaining,
        percentage=percentage,
        rollover_amount=effective_rollover,
        is_over=remaining < 0,
    )


def calculate_rollover(
    budgeted: Decimal,
    spent: Decimal,
    cap: Decimal | None = None,
) -> Decimal:
    """Calculate rollover amount from previous period.

    Only positive (underspent) amounts roll over.  Overspending
    produces a zero rollover -- deficits are not carried forward.

    Args:
        budgeted: Budget amount for the period.
        spent: Actual spending in the period.
        cap: Maximum rollover allowed. None means no cap.

    Returns:
        Non-negative Decimal representing the rollover.
    """
    rollover = budgeted - spent
    if rollover < 0:
        return Decimal("0")  # Don't roll over negative
    if cap is not None and rollover > cap:
        return cap
    return rollover


def format_budget_journal(
    budgets: list[dict],  # [{"category": str, "amount": Decimal}]
) -> str:
    """Generate hledger periodic transaction for budgets.

    Output format::

        ~ monthly
            expenses:food:groceries    $600.00
            expenses:dining            $300.00
            ...

    Args:
        budgets: List of dicts with ``category`` and ``amount`` keys.

    Returns:
        String suitable for appending to a journal file.
    """
    lines = ["~ monthly"]
    for b in budgets:
        amount_str = f"${b['amount']:,.2f}"
        padding = max(2, 40 - len(b["category"]) - 4)
        lines.append(
            f"    {b['category']}" + " " * padding + amount_str
        )
    return "\n".join(lines) + "\n"
