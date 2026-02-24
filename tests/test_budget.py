"""Tests for core/budget.py -- budget math, rollover, and journal formatting."""

from decimal import Decimal

import pytest

from ws_accounting.core.budget import (
    BudgetStatus,
    calculate_budget_status,
    calculate_rollover,
    format_budget_journal,
)


# ---------------------------------------------------------------------------
# calculate_budget_status
# ---------------------------------------------------------------------------


class TestCalculateBudgetStatus:
    def test_normal_spending(self) -> None:
        """Under-budget produces correct remaining and percentage."""
        status = calculate_budget_status(
            category="expenses:food:groceries",
            budgeted=Decimal("600.00"),
            spent=Decimal("450.00"),
        )
        assert status.category == "expenses:food:groceries"
        assert status.budgeted == Decimal("600.00")
        assert status.spent == Decimal("450.00")
        assert status.remaining == Decimal("150.00")
        assert status.percentage == pytest.approx(0.75, rel=1e-6)
        assert status.rollover_amount == Decimal("0")
        assert status.is_over is False

    def test_over_budget(self) -> None:
        """Spending more than budgeted sets is_over=True."""
        status = calculate_budget_status(
            category="expenses:dining",
            budgeted=Decimal("300.00"),
            spent=Decimal("350.00"),
        )
        assert status.remaining == Decimal("-50.00")
        assert status.is_over is True
        assert status.percentage > 1.0

    def test_at_limit_exactly(self) -> None:
        """Spending exactly the budget: remaining=0, not over."""
        status = calculate_budget_status(
            category="expenses:transport",
            budgeted=Decimal("250.00"),
            spent=Decimal("250.00"),
        )
        assert status.remaining == Decimal("0.00")
        assert status.percentage == pytest.approx(1.0, rel=1e-6)
        assert status.is_over is False

    def test_zero_budget_zero_spent(self) -> None:
        """Zero budget and zero spending produces 0% and not over."""
        status = calculate_budget_status(
            category="expenses:misc",
            budgeted=Decimal("0"),
            spent=Decimal("0"),
        )
        assert status.percentage == 0.0
        assert status.remaining == Decimal("0")
        assert status.is_over is False

    def test_zero_budget_with_spending(self) -> None:
        """Zero budget but spending: 0% (avoids div-by-zero), is_over."""
        status = calculate_budget_status(
            category="expenses:misc",
            budgeted=Decimal("0"),
            spent=Decimal("50.00"),
        )
        assert status.percentage == 0.0
        assert status.remaining == Decimal("-50.00")
        assert status.is_over is True

    def test_with_rollover(self) -> None:
        """Rollover adds to effective budget."""
        status = calculate_budget_status(
            category="expenses:food",
            budgeted=Decimal("600.00"),
            spent=Decimal("700.00"),
            rollover=Decimal("150.00"),
        )
        # Effective budget = 600 + 150 = 750
        assert status.budgeted == Decimal("750.00")
        assert status.remaining == Decimal("50.00")
        assert status.is_over is False
        assert status.rollover_amount == Decimal("150.00")

    def test_with_rollover_cap(self) -> None:
        """Rollover is capped when cap is specified."""
        status = calculate_budget_status(
            category="expenses:food",
            budgeted=Decimal("600.00"),
            spent=Decimal("500.00"),
            rollover=Decimal("300.00"),
            rollover_cap=Decimal("100.00"),
        )
        # Effective rollover capped at 100, budget = 600 + 100 = 700
        assert status.budgeted == Decimal("700.00")
        assert status.rollover_amount == Decimal("100.00")
        assert status.remaining == Decimal("200.00")

    def test_rollover_below_cap_unchanged(self) -> None:
        """Rollover below cap is not modified."""
        status = calculate_budget_status(
            category="expenses:food",
            budgeted=Decimal("600.00"),
            spent=Decimal("500.00"),
            rollover=Decimal("50.00"),
            rollover_cap=Decimal("200.00"),
        )
        assert status.rollover_amount == Decimal("50.00")
        assert status.budgeted == Decimal("650.00")

    def test_rollover_cap_none_means_no_cap(self) -> None:
        """rollover_cap=None means full rollover passes through."""
        status = calculate_budget_status(
            category="expenses:food",
            budgeted=Decimal("600.00"),
            spent=Decimal("0"),
            rollover=Decimal("999.99"),
            rollover_cap=None,
        )
        assert status.rollover_amount == Decimal("999.99")
        assert status.budgeted == Decimal("1599.99")


# ---------------------------------------------------------------------------
# calculate_rollover
# ---------------------------------------------------------------------------


class TestCalculateRollover:
    def test_underspend_rolls_over(self) -> None:
        """Unspent budget rolls forward."""
        result = calculate_rollover(
            budgeted=Decimal("600.00"),
            spent=Decimal("450.00"),
        )
        assert result == Decimal("150.00")

    def test_overspend_returns_zero(self) -> None:
        """Overspending produces zero rollover (no deficit carry)."""
        result = calculate_rollover(
            budgeted=Decimal("300.00"),
            spent=Decimal("350.00"),
        )
        assert result == Decimal("0")

    def test_exact_spend_returns_zero(self) -> None:
        """Spending exactly the budget produces zero rollover."""
        result = calculate_rollover(
            budgeted=Decimal("500.00"),
            spent=Decimal("500.00"),
        )
        assert result == Decimal("0")

    def test_with_cap(self) -> None:
        """Rollover is limited to the cap."""
        result = calculate_rollover(
            budgeted=Decimal("600.00"),
            spent=Decimal("200.00"),
            cap=Decimal("100.00"),
        )
        # Underspend = 400, but cap = 100
        assert result == Decimal("100.00")

    def test_cap_above_rollover_no_effect(self) -> None:
        """Cap above actual rollover does not change the value."""
        result = calculate_rollover(
            budgeted=Decimal("600.00"),
            spent=Decimal("550.00"),
            cap=Decimal("200.00"),
        )
        assert result == Decimal("50.00")

    def test_cap_none_means_no_limit(self) -> None:
        """cap=None means no limit on rollover."""
        result = calculate_rollover(
            budgeted=Decimal("1000.00"),
            spent=Decimal("0"),
            cap=None,
        )
        assert result == Decimal("1000.00")

    def test_zero_budget_zero_spent(self) -> None:
        """Both zero: rollover is zero."""
        result = calculate_rollover(
            budgeted=Decimal("0"),
            spent=Decimal("0"),
        )
        assert result == Decimal("0")


# ---------------------------------------------------------------------------
# format_budget_journal
# ---------------------------------------------------------------------------


class TestFormatBudgetJournal:
    def test_single_category(self) -> None:
        """Single category produces a valid periodic transaction."""
        result = format_budget_journal([
            {"category": "expenses:food:groceries", "amount": Decimal("600.00")}
        ])
        assert result.startswith("~ monthly\n")
        assert "expenses:food:groceries" in result
        assert "$600.00" in result
        assert result.endswith("\n")

    def test_multiple_categories(self) -> None:
        """Multiple categories each get their own line."""
        budgets = [
            {"category": "expenses:food:groceries", "amount": Decimal("600.00")},
            {"category": "expenses:dining", "amount": Decimal("300.00")},
            {"category": "expenses:transport", "amount": Decimal("250.00")},
        ]
        result = format_budget_journal(budgets)
        lines = result.strip().split("\n")
        assert lines[0] == "~ monthly"
        assert len(lines) == 4  # header + 3 categories
        assert "expenses:food:groceries" in lines[1]
        assert "expenses:dining" in lines[2]
        assert "expenses:transport" in lines[3]

    def test_proper_indentation(self) -> None:
        """Each category line starts with 4 spaces."""
        result = format_budget_journal([
            {"category": "expenses:food", "amount": Decimal("100.00")}
        ])
        lines = result.strip().split("\n")
        for line in lines[1:]:
            assert line.startswith("    ")

    def test_large_amount_formatting(self) -> None:
        """Amounts >= 1000 get comma formatting."""
        result = format_budget_journal([
            {"category": "expenses:housing:rent", "amount": Decimal("2500.00")}
        ])
        assert "$2,500.00" in result

    def test_empty_list(self) -> None:
        """Empty budget list produces just the header."""
        result = format_budget_journal([])
        assert result.strip() == "~ monthly"


# ---------------------------------------------------------------------------
# BudgetStatus.display_percentage
# ---------------------------------------------------------------------------


class TestDisplayPercentage:
    def test_normal_percentage(self) -> None:
        """75% spent displays as 75."""
        status = BudgetStatus(
            category="test",
            budgeted=Decimal("100"),
            spent=Decimal("75"),
            remaining=Decimal("25"),
            percentage=0.75,
            rollover_amount=Decimal("0"),
            is_over=False,
        )
        assert status.display_percentage == 75

    def test_zero_percentage(self) -> None:
        """0% displays as 0."""
        status = BudgetStatus(
            category="test",
            budgeted=Decimal("100"),
            spent=Decimal("0"),
            remaining=Decimal("100"),
            percentage=0.0,
            rollover_amount=Decimal("0"),
            is_over=False,
        )
        assert status.display_percentage == 0

    def test_over_100_percent(self) -> None:
        """150% spent displays as 150."""
        status = BudgetStatus(
            category="test",
            budgeted=Decimal("100"),
            spent=Decimal("150"),
            remaining=Decimal("-50"),
            percentage=1.5,
            rollover_amount=Decimal("0"),
            is_over=True,
        )
        assert status.display_percentage == 150

    def test_clamped_at_999(self) -> None:
        """Extreme overspend is clamped to 999."""
        status = BudgetStatus(
            category="test",
            budgeted=Decimal("10"),
            spent=Decimal("1500"),
            remaining=Decimal("-1490"),
            percentage=150.0,
            rollover_amount=Decimal("0"),
            is_over=True,
        )
        assert status.display_percentage == 999

    def test_clamped_at_zero(self) -> None:
        """Negative percentage (shouldn't happen) clamps to 0."""
        status = BudgetStatus(
            category="test",
            budgeted=Decimal("100"),
            spent=Decimal("0"),
            remaining=Decimal("100"),
            percentage=-0.5,
            rollover_amount=Decimal("0"),
            is_over=False,
        )
        assert status.display_percentage == 0

    def test_fractional_rounds_down(self) -> None:
        """33.3% truncates to 33 (int conversion)."""
        status = BudgetStatus(
            category="test",
            budgeted=Decimal("300"),
            spent=Decimal("100"),
            remaining=Decimal("200"),
            percentage=1 / 3,
            rollover_amount=Decimal("0"),
            is_over=False,
        )
        assert status.display_percentage == 33

    def test_just_under_100(self) -> None:
        """99.9% truncates to 99."""
        status = BudgetStatus(
            category="test",
            budgeted=Decimal("1000"),
            spent=Decimal("999"),
            remaining=Decimal("1"),
            percentage=0.999,
            rollover_amount=Decimal("0"),
            is_over=False,
        )
        assert status.display_percentage == 99
