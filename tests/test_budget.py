"""Tests for budget math, DB CRUD, and recurring queries."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ws_accounting.core.budget import (
    BudgetResult,
    BudgetStatus,
    calculate_budget_status,
    calculate_rollover,
)
from ws_accounting.db.database import Database
from ws_accounting.db.models import Budget, Goal, RecurringTransaction
from ws_accounting.db.queries import (
    delete_budget,
    get_budgets,
    get_due_recurring,
    get_goals,
    get_recurring,
    upsert_budget,
    upsert_goal,
    upsert_recurring,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db(tmp_path):
    """Create a Database with all tables migrated."""
    db_path = tmp_path / "test.db"
    database = Database(db_path)
    database.migrate()
    return database


# ---------------------------------------------------------------------------
# calculate_budget_status tests
# ---------------------------------------------------------------------------


class TestCalculateBudgetStatus:
    """Test budget status computation."""

    def test_under_budget(self):
        result = calculate_budget_status(
            category="expenses:food",
            budget_amount=Decimal("500"),
            spent_amount=Decimal("200"),
        )
        assert isinstance(result, BudgetResult)
        assert result.status == BudgetStatus.UNDER
        assert result.percentage == 40
        assert result.remaining == Decimal("300")
        assert result.category == "expenses:food"
        assert result.budget_amount == Decimal("500")
        assert result.spent_amount == Decimal("200")

    def test_near_budget_at_80_percent(self):
        result = calculate_budget_status(
            category="expenses:dining",
            budget_amount=Decimal("100"),
            spent_amount=Decimal("80"),
        )
        assert result.status == BudgetStatus.NEAR
        assert result.percentage == 80

    def test_near_budget_at_99_percent(self):
        result = calculate_budget_status(
            category="expenses:dining",
            budget_amount=Decimal("100"),
            spent_amount=Decimal("99"),
        )
        assert result.status == BudgetStatus.NEAR
        assert result.percentage == 99

    def test_over_budget(self):
        result = calculate_budget_status(
            category="expenses:shopping",
            budget_amount=Decimal("300"),
            spent_amount=Decimal("350"),
        )
        assert result.status == BudgetStatus.OVER
        assert result.percentage == 100  # clamped to 100
        assert result.remaining == Decimal("-50")

    def test_exactly_at_budget(self):
        result = calculate_budget_status(
            category="expenses:transport",
            budget_amount=Decimal("200"),
            spent_amount=Decimal("200"),
        )
        assert result.status == BudgetStatus.OVER
        assert result.percentage == 100
        assert result.remaining == Decimal("0")

    def test_zero_budget(self):
        result = calculate_budget_status(
            category="expenses:misc",
            budget_amount=Decimal("0"),
            spent_amount=Decimal("50"),
        )
        assert result.status == BudgetStatus.UNDER
        assert result.percentage == 0

    def test_no_spending(self):
        result = calculate_budget_status(
            category="expenses:food",
            budget_amount=Decimal("500"),
            spent_amount=Decimal("0"),
        )
        assert result.status == BudgetStatus.UNDER
        assert result.percentage == 0
        assert result.remaining == Decimal("500")

    def test_with_rollover(self):
        """Rollover increases effective budget."""
        result = calculate_budget_status(
            category="expenses:food",
            budget_amount=Decimal("500"),
            spent_amount=Decimal("400"),
            rollover=Decimal("100"),
        )
        # Effective budget = 500 + 100 = 600
        # Percentage = 400/600 = 66%
        assert result.status == BudgetStatus.UNDER
        assert result.percentage == 66
        assert result.remaining == Decimal("200")
        assert result.rollover == Decimal("100")

    def test_rollover_prevents_over(self):
        """Rollover can prevent going over budget."""
        result = calculate_budget_status(
            category="expenses:food",
            budget_amount=Decimal("500"),
            spent_amount=Decimal("550"),
            rollover=Decimal("100"),
        )
        # Effective budget = 600, spent = 550
        # Percentage = 550/600 = 91%
        assert result.status == BudgetStatus.NEAR
        assert result.remaining == Decimal("50")


# ---------------------------------------------------------------------------
# calculate_rollover tests
# ---------------------------------------------------------------------------


class TestCalculateRollover:
    """Test rollover computation."""

    def test_basic_rollover(self):
        """Unspent amount rolls over."""
        result = calculate_rollover(
            budget_amount=Decimal("500"),
            spent_amount=Decimal("300"),
        )
        assert result == Decimal("200")

    def test_no_rollover_when_overspent(self):
        """No rollover when spent exceeds budget."""
        result = calculate_rollover(
            budget_amount=Decimal("500"),
            spent_amount=Decimal("600"),
        )
        assert result == Decimal("0")

    def test_zero_spent(self):
        """Full budget rolls over when nothing spent."""
        result = calculate_rollover(
            budget_amount=Decimal("500"),
            spent_amount=Decimal("0"),
        )
        assert result == Decimal("500")

    def test_exactly_spent(self):
        """Zero rollover when exactly spent."""
        result = calculate_rollover(
            budget_amount=Decimal("500"),
            spent_amount=Decimal("500"),
        )
        assert result == Decimal("0")

    def test_with_previous_rollover(self):
        """Previous rollover adds to effective budget."""
        result = calculate_rollover(
            budget_amount=Decimal("500"),
            spent_amount=Decimal("400"),
            previous_rollover=Decimal("100"),
        )
        # Effective = 500 + 100 = 600; rollover = 600 - 400 = 200
        assert result == Decimal("200")

    def test_previous_rollover_consumed(self):
        """Spending can consume previous rollover."""
        result = calculate_rollover(
            budget_amount=Decimal("500"),
            spent_amount=Decimal("550"),
            previous_rollover=Decimal("100"),
        )
        # Effective = 600; rollover = 600 - 550 = 50
        assert result == Decimal("50")

    def test_previous_rollover_fully_consumed(self):
        """No rollover when all including previous is consumed."""
        result = calculate_rollover(
            budget_amount=Decimal("500"),
            spent_amount=Decimal("700"),
            previous_rollover=Decimal("100"),
        )
        assert result == Decimal("0")


# ---------------------------------------------------------------------------
# Database CRUD: budgets
# ---------------------------------------------------------------------------


class TestBudgetCRUD:
    """Test budget DB operations using Database objects."""

    def test_get_budgets_empty(self, db):
        """Empty DB returns empty list."""
        budgets = get_budgets(db)
        assert budgets == []

    def test_upsert_and_get_budget(self, db):
        """Insert a budget then retrieve it."""
        budget = Budget(
            category="expenses:food:groceries",
            amount="500.00",
            period="monthly",
            rollover=0,
        )
        row_id = upsert_budget(db, budget)
        assert row_id is not None and row_id > 0

        budgets = get_budgets(db)
        assert len(budgets) == 1
        assert budgets[0].category == "expenses:food:groceries"
        assert budgets[0].amount == "500.00"
        assert budgets[0].rollover == 0
        assert budgets[0].id == row_id

    def test_upsert_update_existing(self, db):
        """Update an existing budget."""
        budget = Budget(
            category="expenses:food",
            amount="500.00",
            period="monthly",
        )
        row_id = upsert_budget(db, budget)

        # Update it
        budget.id = row_id
        budget.amount = "600.00"
        budget.rollover = 1
        upsert_budget(db, budget)

        budgets = get_budgets(db)
        assert len(budgets) == 1
        assert budgets[0].amount == "600.00"
        assert budgets[0].rollover == 1

    def test_multiple_budgets_ordered(self, db):
        """Multiple budgets return ordered by category."""
        upsert_budget(db, Budget(category="expenses:food", amount="500"))
        upsert_budget(db, Budget(category="expenses:dining", amount="200"))
        upsert_budget(db, Budget(category="expenses:transport", amount="300"))

        budgets = get_budgets(db)
        assert len(budgets) == 3
        categories = [b.category for b in budgets]
        assert categories == sorted(categories)

    def test_delete_budget(self, db):
        """Delete a budget by id."""
        budget = Budget(category="expenses:food", amount="500")
        row_id = upsert_budget(db, budget)

        delete_budget(db, row_id)
        budgets = get_budgets(db)
        assert len(budgets) == 0

    def test_delete_nonexistent(self, db):
        """Deleting a nonexistent budget doesn't raise."""
        delete_budget(db, 9999)  # Should not raise

    def test_get_budgets_with_month_param(self, db):
        """get_budgets accepts month param (currently ignored, returns all)."""
        upsert_budget(db, Budget(category="expenses:food", amount="500"))
        budgets = get_budgets(db, month="2026-01")
        assert len(budgets) == 1

    def test_get_budgets_with_connection(self, db):
        """get_budgets works with raw sqlite3.Connection too."""
        conn = db.connect()
        upsert_budget(conn, Budget(category="expenses:food", amount="500"))
        budgets = get_budgets(conn)
        assert len(budgets) == 1


# ---------------------------------------------------------------------------
# Database CRUD: goals
# ---------------------------------------------------------------------------


class TestGoalCRUD:
    """Test goal DB operations."""

    def test_get_goals_empty(self, db):
        """Empty DB returns empty list."""
        goals = get_goals(db)
        assert goals == []

    def test_upsert_and_get_goal(self, db):
        """Insert a goal then retrieve it."""
        goal = Goal(
            name="Emergency Fund",
            target_amount="10000.00",
            current_amount="2500.00",
            account="assets:savings",
            target_date="2026-12-31",
        )
        row_id = upsert_goal(db, goal)
        assert row_id is not None and row_id > 0

        goals = get_goals(db)
        assert len(goals) == 1
        assert goals[0].name == "Emergency Fund"
        assert goals[0].target_amount == "10000.00"
        assert goals[0].current_amount == "2500.00"
        assert goals[0].account == "assets:savings"
        assert goals[0].target_date == "2026-12-31"

    def test_upsert_update_goal(self, db):
        """Update an existing goal's progress."""
        goal = Goal(
            name="Vacation",
            target_amount="5000.00",
            current_amount="1000.00",
        )
        row_id = upsert_goal(db, goal)

        goal.id = row_id
        goal.current_amount = "2000.00"
        upsert_goal(db, goal)

        goals = get_goals(db)
        assert len(goals) == 1
        assert goals[0].current_amount == "2000.00"

    def test_multiple_goals(self, db):
        """Multiple goals can be stored and retrieved."""
        upsert_goal(db, Goal(name="Goal A", target_amount="1000"))
        upsert_goal(db, Goal(name="Goal B", target_amount="2000"))

        goals = get_goals(db)
        assert len(goals) == 2


# ---------------------------------------------------------------------------
# Database: recurring transactions / get_due_recurring
# ---------------------------------------------------------------------------


class TestRecurringQueries:
    """Test recurring transaction queries."""

    def test_get_due_recurring_empty(self, db):
        """Empty DB returns empty list."""
        result = get_due_recurring(db, "2026-03-01")
        assert result == []

    def test_get_due_recurring_returns_due_items(self, db):
        """Returns items with next_due on or before the given date."""
        rec1 = RecurringTransaction(
            description="Rent",
            amount="1500.00",
            from_account="assets:checking",
            to_account="expenses:housing:rent",
            frequency="monthly",
            next_due="2026-02-25",
            active=1,
        )
        rec2 = RecurringTransaction(
            description="Netflix",
            amount="15.99",
            from_account="assets:checking",
            to_account="expenses:entertainment",
            frequency="monthly",
            next_due="2026-02-28",
            active=1,
        )
        rec3 = RecurringTransaction(
            description="Car Insurance",
            amount="200.00",
            from_account="assets:checking",
            to_account="expenses:insurance",
            frequency="monthly",
            next_due="2026-03-15",  # After window
            active=1,
        )
        upsert_recurring(db, rec1)
        upsert_recurring(db, rec2)
        upsert_recurring(db, rec3)

        # Query for items due on or before March 1
        due = get_due_recurring(db, "2026-03-01")
        assert len(due) == 2
        descriptions = [r.description for r in due]
        assert "Rent" in descriptions
        assert "Netflix" in descriptions
        assert "Car Insurance" not in descriptions

    def test_get_due_recurring_excludes_inactive(self, db):
        """Inactive recurring transactions are excluded."""
        rec = RecurringTransaction(
            description="Old Subscription",
            amount="10.00",
            from_account="assets:checking",
            to_account="expenses:subscriptions",
            frequency="monthly",
            next_due="2026-02-20",
            active=0,
        )
        upsert_recurring(db, rec)

        due = get_due_recurring(db, "2026-03-01")
        assert len(due) == 0

    def test_get_due_recurring_no_date_returns_all_active(self, db):
        """When no date is given, returns all active items."""
        rec1 = RecurringTransaction(
            description="Rent",
            amount="1500.00",
            from_account="assets:checking",
            to_account="expenses:housing",
            frequency="monthly",
            next_due="2026-02-25",
            active=1,
        )
        rec2 = RecurringTransaction(
            description="Inactive",
            amount="10.00",
            from_account="assets:checking",
            to_account="expenses:other",
            frequency="monthly",
            next_due="2026-02-20",
            active=0,
        )
        upsert_recurring(db, rec1)
        upsert_recurring(db, rec2)

        due = get_due_recurring(db)
        assert len(due) == 1
        assert due[0].description == "Rent"

    def test_get_due_recurring_ordered_by_next_due(self, db):
        """Results are ordered by next_due ascending."""
        upsert_recurring(db, RecurringTransaction(
            description="Later",
            amount="100",
            from_account="a",
            to_account="b",
            frequency="monthly",
            next_due="2026-02-28",
            active=1,
        ))
        upsert_recurring(db, RecurringTransaction(
            description="Earlier",
            amount="50",
            from_account="a",
            to_account="b",
            frequency="monthly",
            next_due="2026-02-20",
            active=1,
        ))

        due = get_due_recurring(db, "2026-03-01")
        assert due[0].description == "Earlier"
        assert due[1].description == "Later"
