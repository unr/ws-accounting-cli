"""Budget tracking math — category budgets with optional rollover."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


class BudgetStatus(Enum):
    """Budget health status."""

    UNDER = "under"
    NEAR = "near"        # 80-99%
    OVER = "over"
    NO_BUDGET = "none"


@dataclass
class BudgetResult:
    """Result of comparing spending to budget."""

    category: str
    budget_amount: Decimal
    spent_amount: Decimal
    remaining: Decimal
    percentage: int
    status: BudgetStatus
    rollover: Decimal = Decimal(0)


def calculate_budget_status(
    category: str,
    budget_amount: Decimal,
    spent_amount: Decimal,
    rollover: Decimal = Decimal(0),
) -> BudgetResult:
    """Calculate budget status for a category."""
    effective_budget = budget_amount + rollover
    remaining = effective_budget - spent_amount
    pct = int((spent_amount / effective_budget) * 100) if effective_budget > 0 else 0

    if pct >= 100:
        status = BudgetStatus.OVER
    elif pct >= 80:
        status = BudgetStatus.NEAR
    else:
        status = BudgetStatus.UNDER

    return BudgetResult(
        category=category,
        budget_amount=budget_amount,
        spent_amount=spent_amount,
        remaining=remaining,
        percentage=min(pct, 100),
        status=status,
        rollover=rollover,
    )


def calculate_rollover(
    budget_amount: Decimal,
    spent_amount: Decimal,
    previous_rollover: Decimal = Decimal(0),
) -> Decimal:
    """Calculate rollover amount from previous period."""
    effective = budget_amount + previous_rollover
    return max(Decimal(0), effective - spent_amount)
