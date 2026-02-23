"""Comprehensive tests for the SQLite sidecar database layer."""

from decimal import Decimal

import pytest

from ws_accounting.db.database import Database
from ws_accounting.db.models import (
    Budget,
    CategorizationCache,
    Goal,
    ImportProfile,
    InsightsCache,
    Reconciliation,
    RecurringTransaction,
)
from ws_accounting.db.queries import (
    advance_recurring,
    amount_to_bucket,
    cache_category,
    cache_insights,
    check_import_hash,
    create_goal,
    create_import_profile,
    create_recurring,
    delete_budget,
    delete_goal,
    delete_recurring,
    get_budgets,
    get_cached_insights,
    get_due_recurring,
    get_goals,
    get_import_profiles,
    get_last_reconciliation,
    get_recurring,
    get_setting,
    lookup_category,
    record_correction,
    get_corrections_count,
    record_import,
    record_reconciliation,
    set_setting,
    store_import_hashes,
    update_goal_progress,
    upsert_budget,
)


@pytest.fixture
def db() -> Database:
    """Create an in-memory Database with migrations applied."""
    database = Database(":memory:")
    database.migrate()
    yield database
    database.close()


# ---------------------------------------------------------------------------
# Database & migration tests
# ---------------------------------------------------------------------------


class TestDatabaseCore:
    def test_memory_database_creates(self):
        """Database with :memory: can be instantiated and connected."""
        with Database(":memory:") as database:
            assert database.conn is not None

    def test_current_version_before_migration(self):
        """Version is 0 before any migrations run."""
        with Database(":memory:") as database:
            assert database.current_version() == 0

    def test_migration_sets_version(self, db: Database):
        """After migration, version is 1."""
        assert db.current_version() == 1

    def test_migration_is_idempotent(self, db: Database):
        """Running migrate again does nothing (no error, same version)."""
        db.migrate()
        assert db.current_version() == 1

    def test_context_manager_closes(self):
        """Context manager closes the connection."""
        database = Database(":memory:")
        database.migrate()
        with database:
            assert database._conn is not None
        assert database._conn is None

    def test_wal_mode_enabled(self, db: Database):
        """WAL journal mode is set."""
        row = db.conn.execute("PRAGMA journal_mode").fetchone()
        # :memory: databases report "memory" for journal_mode
        assert row[0] in ("wal", "memory")

    def test_foreign_keys_enabled(self, db: Database):
        """Foreign keys pragma is on."""
        row = db.conn.execute("PRAGMA foreign_keys").fetchone()
        assert row[0] == 1


# ---------------------------------------------------------------------------
# Budget tests
# ---------------------------------------------------------------------------


class TestBudgets:
    def test_upsert_and_get(self, db: Database):
        """Insert a budget and retrieve it."""
        upsert_budget(db, "expenses:food", "2026-01", "600.00")
        budgets = get_budgets(db, "2026-01")
        assert len(budgets) == 1
        assert budgets[0].category == "expenses:food"
        assert budgets[0].amount == "600.00"
        assert budgets[0].rollover is False

    def test_upsert_updates_existing(self, db: Database):
        """Upserting same category+month updates the amount."""
        upsert_budget(db, "expenses:food", "2026-01", "600.00")
        upsert_budget(db, "expenses:food", "2026-01", "700.00", rollover=True)
        budgets = get_budgets(db, "2026-01")
        assert len(budgets) == 1
        assert budgets[0].amount == "700.00"
        assert budgets[0].rollover is True

    def test_get_budgets_filters_by_month(self, db: Database):
        """Only budgets for the requested month are returned."""
        upsert_budget(db, "expenses:food", "2026-01", "600.00")
        upsert_budget(db, "expenses:food", "2026-02", "650.00")
        assert len(get_budgets(db, "2026-01")) == 1
        assert len(get_budgets(db, "2026-02")) == 1
        assert len(get_budgets(db, "2026-03")) == 0

    def test_delete_budget(self, db: Database):
        """Delete removes the budget."""
        upsert_budget(db, "expenses:food", "2026-01", "600.00")
        budgets = get_budgets(db, "2026-01")
        delete_budget(db, budgets[0].id)
        assert len(get_budgets(db, "2026-01")) == 0


# ---------------------------------------------------------------------------
# Goal tests
# ---------------------------------------------------------------------------


class TestGoals:
    def test_create_and_get(self, db: Database):
        """Create a goal and retrieve it."""
        goal = create_goal(
            db,
            name="Emergency Fund",
            target_amount="10000.00",
            type="savings",
            target_date="2026-12-31",
        )
        assert goal.id is not None
        assert goal.name == "Emergency Fund"
        assert goal.current_amount == "0"

        goals = get_goals(db)
        assert len(goals) == 1
        assert goals[0].name == "Emergency Fund"

    def test_update_goal_progress(self, db: Database):
        """Updating progress changes current_amount."""
        goal = create_goal(
            db,
            name="Vacation",
            target_amount="3000.00",
            type="savings",
        )
        update_goal_progress(db, goal.id, "1500.00")
        goals = get_goals(db)
        assert goals[0].current_amount == "1500.00"

    def test_delete_goal(self, db: Database):
        """Delete removes the goal."""
        goal = create_goal(
            db,
            name="Temp Goal",
            target_amount="100.00",
            type="savings",
        )
        delete_goal(db, goal.id)
        assert len(get_goals(db)) == 0


# ---------------------------------------------------------------------------
# Categorization tests
# ---------------------------------------------------------------------------


class TestCategorization:
    def test_lookup_miss(self, db: Database):
        """Cache miss returns None."""
        result = lookup_category(db, "WHOLE FOODS", "$25-100")
        assert result is None

    def test_cache_and_lookup_hit(self, db: Database):
        """Cache a category then look it up."""
        cache_category(
            db,
            description="WHOLE FOODS",
            amount_bucket="$25-100",
            account="expenses:food:groceries",
            confidence=0.95,
            source="ai",
        )
        result = lookup_category(db, "WHOLE FOODS", "$25-100")
        assert result is not None
        assert result.account == "expenses:food:groceries"
        assert result.confidence == 0.95
        assert result.source == "ai"

    def test_cache_upsert(self, db: Database):
        """Caching same desc+bucket updates the record."""
        cache_category(
            db, "STARBUCKS", "$0-25",
            "expenses:food:coffee", 0.8, "ai",
        )
        cache_category(
            db, "STARBUCKS", "$0-25",
            "expenses:food:dining", 0.99, "user",
        )
        result = lookup_category(db, "STARBUCKS", "$0-25")
        assert result.account == "expenses:food:dining"
        assert result.confidence == 0.99

    def test_record_correction_and_count(self, db: Database):
        """Record corrections and count them."""
        assert get_corrections_count(db, "AMZN") == 0
        record_correction(
            db, "AMZN", "expenses:shopping", "expenses:office"
        )
        record_correction(
            db, "AMZN", "expenses:shopping", "expenses:electronics"
        )
        assert get_corrections_count(db, "AMZN") == 2
        # Different description has 0
        assert get_corrections_count(db, "TARGET") == 0


class TestAmountToBucket:
    def test_zero(self):
        assert amount_to_bucket(Decimal("0")) == "$0-25"

    def test_small(self):
        assert amount_to_bucket(Decimal("10.50")) == "$0-25"

    def test_boundary_25(self):
        assert amount_to_bucket(Decimal("24.99")) == "$0-25"
        assert amount_to_bucket(Decimal("25.00")) == "$25-100"

    def test_medium(self):
        assert amount_to_bucket(Decimal("75.00")) == "$25-100"

    def test_boundary_100(self):
        assert amount_to_bucket(Decimal("99.99")) == "$25-100"
        assert amount_to_bucket(Decimal("100.00")) == "$100-500"

    def test_large(self):
        assert amount_to_bucket(Decimal("250.00")) == "$100-500"

    def test_boundary_500(self):
        assert amount_to_bucket(Decimal("499.99")) == "$100-500"
        assert amount_to_bucket(Decimal("500.00")) == "$500+"

    def test_very_large(self):
        assert amount_to_bucket(Decimal("9999.99")) == "$500+"

    def test_negative_uses_absolute(self):
        assert amount_to_bucket(Decimal("-50.00")) == "$25-100"


# ---------------------------------------------------------------------------
# Import tests
# ---------------------------------------------------------------------------


class TestImports:
    def test_create_import_profile(self, db: Database):
        """Create and retrieve import profiles."""
        profile = create_import_profile(
            db,
            name="Chase Checking",
            rules_path="/rules/chase.rules",
            bank_name="Chase",
        )
        assert profile.id is not None
        assert profile.name == "Chase Checking"
        assert profile.bank_name == "Chase"
        assert profile.default_status == "*"

        profiles = get_import_profiles(db)
        assert len(profiles) == 1

    def test_record_import(self, db: Database):
        """Record an import event."""
        profile = create_import_profile(
            db, "Generic", "/rules/generic.rules"
        )
        history = record_import(
            db,
            csv_filename="jan2026.csv",
            profile_id=profile.id,
            txn_count=42,
            duplicate_count=3,
        )
        assert history.id is not None
        assert history.txn_count == 42
        assert history.duplicate_count == 3

    def test_store_and_check_hashes(self, db: Database):
        """Store hashes and detect duplicates."""
        profile = create_import_profile(
            db, "Test", "/rules/test.rules"
        )
        history = record_import(db, "test.csv", profile.id, 2)

        store_import_hashes(db, ["abc123", "def456"], history.id)

        assert check_import_hash(db, "abc123") is True
        assert check_import_hash(db, "def456") is True
        assert check_import_hash(db, "ghi789") is False

    def test_duplicate_hash_ignored(self, db: Database):
        """Storing an existing hash doesn't raise."""
        profile = create_import_profile(
            db, "Test", "/rules/test.rules"
        )
        history = record_import(db, "test.csv", profile.id, 1)
        store_import_hashes(db, ["abc123"], history.id)
        # Should not raise
        store_import_hashes(db, ["abc123"], history.id)
        assert check_import_hash(db, "abc123") is True


# ---------------------------------------------------------------------------
# Settings tests
# ---------------------------------------------------------------------------


class TestSettings:
    def test_get_missing_setting(self, db: Database):
        """Getting a non-existent key returns None."""
        assert get_setting(db, "nonexistent") is None

    def test_set_and_get(self, db: Database):
        """Set a setting and retrieve it."""
        set_setting(db, "theme", "dark")
        assert get_setting(db, "theme") == "dark"

    def test_set_overwrites(self, db: Database):
        """Setting an existing key overwrites the value."""
        set_setting(db, "theme", "dark")
        set_setting(db, "theme", "light")
        assert get_setting(db, "theme") == "light"


# ---------------------------------------------------------------------------
# Recurring transaction tests
# ---------------------------------------------------------------------------


class TestRecurring:
    def test_create_and_get(self, db: Database):
        """Create and list recurring transactions."""
        rec = create_recurring(
            db,
            description="Rent",
            amount="1500.00",
            from_account="assets:bank:checking",
            to_account="expenses:housing:rent",
            frequency="monthly",
            next_due="2026-03-01",
        )
        assert rec.id is not None
        assert rec.description == "Rent"
        assert rec.frequency == "monthly"

        all_rec = get_recurring(db)
        assert len(all_rec) == 1

    def test_delete_recurring(self, db: Database):
        """Delete removes the recurring transaction."""
        rec = create_recurring(
            db, "Spotify", "9.99",
            "assets:bank:checking", "expenses:subscriptions",
            "monthly", "2026-03-15",
        )
        delete_recurring(db, rec.id)
        assert len(get_recurring(db)) == 0

    def test_advance_weekly(self, db: Database):
        """Advancing weekly adds 7 days."""
        rec = create_recurring(
            db, "Gym", "50.00",
            "assets:bank:checking", "expenses:health",
            "weekly", "2026-01-07",
        )
        advance_recurring(db, rec.id)
        updated = get_recurring(db)
        assert updated[0].next_due == "2026-01-14"

    def test_advance_monthly(self, db: Database):
        """Advancing monthly adds one month."""
        rec = create_recurring(
            db, "Rent", "1500.00",
            "assets:bank:checking", "expenses:housing",
            "monthly", "2026-01-15",
        )
        advance_recurring(db, rec.id)
        updated = get_recurring(db)
        assert updated[0].next_due == "2026-02-15"

    def test_advance_monthly_end_of_month(self, db: Database):
        """Advancing from Jan 31 clamps to Feb 28."""
        rec = create_recurring(
            db, "Inv", "100.00",
            "assets:bank:checking", "assets:investments",
            "monthly", "2026-01-31",
        )
        advance_recurring(db, rec.id)
        updated = get_recurring(db)
        assert updated[0].next_due == "2026-02-28"

    def test_advance_monthly_december(self, db: Database):
        """Advancing from December goes to January next year."""
        rec = create_recurring(
            db, "Year End", "200.00",
            "assets:bank:checking", "expenses:misc",
            "monthly", "2025-12-15",
        )
        advance_recurring(db, rec.id)
        updated = get_recurring(db)
        assert updated[0].next_due == "2026-01-15"

    def test_advance_yearly(self, db: Database):
        """Advancing yearly adds one year."""
        rec = create_recurring(
            db, "Insurance", "1200.00",
            "assets:bank:checking", "expenses:insurance",
            "yearly", "2026-03-01",
        )
        advance_recurring(db, rec.id)
        updated = get_recurring(db)
        assert updated[0].next_due == "2027-03-01"

    def test_advance_yearly_leap_day(self, db: Database):
        """Advancing from Feb 29 leap year clamps to Feb 28."""
        rec = create_recurring(
            db, "Leap", "100.00",
            "assets:bank:checking", "expenses:misc",
            "yearly", "2024-02-29",
        )
        advance_recurring(db, rec.id)
        updated = get_recurring(db)
        assert updated[0].next_due == "2025-02-28"

    def test_get_due_recurring(self, db: Database):
        """Only due transactions are returned."""
        create_recurring(
            db, "Past Due", "10.00",
            "assets:checking", "expenses:misc",
            "monthly", "2026-01-01",
        )
        create_recurring(
            db, "Due Today", "20.00",
            "assets:checking", "expenses:misc",
            "monthly", "2026-02-15",
        )
        create_recurring(
            db, "Future", "30.00",
            "assets:checking", "expenses:misc",
            "monthly", "2026-03-01",
        )

        due = get_due_recurring(db, "2026-02-15")
        descriptions = [r.description for r in due]
        assert "Past Due" in descriptions
        assert "Due Today" in descriptions
        assert "Future" not in descriptions

    def test_get_due_respects_end_date(self, db: Database):
        """Expired recurring transactions are excluded."""
        create_recurring(
            db, "Expired", "10.00",
            "assets:checking", "expenses:misc",
            "monthly", "2026-01-01",
            end_date="2026-01-31",
        )
        due = get_due_recurring(db, "2026-02-15")
        assert len(due) == 0


# ---------------------------------------------------------------------------
# Reconciliation tests
# ---------------------------------------------------------------------------


class TestReconciliation:
    def test_record_and_get(self, db: Database):
        """Record a reconciliation and retrieve it."""
        record_reconciliation(
            db,
            account="assets:bank:checking",
            statement_date="2026-01-31",
            statement_balance="5234.56",
        )
        rec = get_last_reconciliation(db, "assets:bank:checking")
        assert rec is not None
        assert rec.account == "assets:bank:checking"
        assert rec.statement_balance == "5234.56"
        assert rec.status == "complete"

    def test_get_last_returns_most_recent(self, db: Database):
        """Most recent reconciliation is returned."""
        record_reconciliation(
            db, "assets:bank:checking", "2026-01-31", "5000.00"
        )
        record_reconciliation(
            db, "assets:bank:checking", "2026-02-28", "5500.00"
        )
        rec = get_last_reconciliation(db, "assets:bank:checking")
        assert rec.statement_date == "2026-02-28"
        assert rec.statement_balance == "5500.00"

    def test_get_last_no_records(self, db: Database):
        """Returns None when no reconciliations exist."""
        rec = get_last_reconciliation(db, "assets:bank:checking")
        assert rec is None


# ---------------------------------------------------------------------------
# Insights cache tests
# ---------------------------------------------------------------------------


class TestInsights:
    def test_cache_and_get(self, db: Database):
        """Cache insights and retrieve them."""
        cache_insights(
            db,
            period="2026-01",
            content="You spent more on groceries this month.",
            model="claude-opus-4-20250514",
        )
        result = get_cached_insights(db, "2026-01")
        assert result is not None
        assert result.period == "2026-01"
        assert "groceries" in result.content
        assert result.model == "claude-opus-4-20250514"

    def test_get_returns_most_recent(self, db: Database):
        """Most recent insight for a period is returned."""
        # Insert old insight with an explicit earlier timestamp to avoid
        # UNIQUE(period, generated_at) collision within the same second.
        db.conn.execute(
            "INSERT INTO insights_cache (period, content, model, generated_at) "
            "VALUES (?, ?, ?, ?)",
            ("2026-01", "Old insight", "claude-3-haiku", "2026-01-01 00:00:00"),
        )
        db.conn.commit()
        cache_insights(db, "2026-01", "New insight", "claude-opus-4-20250514")
        result = get_cached_insights(db, "2026-01")
        assert result.content == "New insight"

    def test_get_miss(self, db: Database):
        """Returns None for uncached period."""
        assert get_cached_insights(db, "2099-01") is None


# ---------------------------------------------------------------------------
# Monetary values stored as TEXT (critical constraint)
# ---------------------------------------------------------------------------


class TestMonetaryTextStorage:
    """Verify that all monetary columns use TEXT, never REAL/FLOAT."""

    MONETARY_TABLES_AND_COLUMNS = [
        ("budgets", "amount"),
        ("budgets", "rollover_cap"),
        ("goals", "target_amount"),
        ("goals", "current_amount"),
        ("recurring_transactions", "amount"),
        ("reconciliations", "statement_balance"),
    ]

    def test_monetary_columns_are_text(self, db: Database):
        """All monetary columns must be declared as TEXT."""
        for table, column in self.MONETARY_TABLES_AND_COLUMNS:
            rows = db.conn.execute(
                f"PRAGMA table_info({table})"
            ).fetchall()
            col_info = {r["name"]: r["type"] for r in rows}
            assert column in col_info, (
                f"Column {column} not found in {table}"
            )
            assert col_info[column] == "TEXT", (
                f"{table}.{column} should be TEXT, got {col_info[column]}"
            )

    def test_budget_amount_stored_as_text(self, db: Database):
        """Budget amount round-trips as exact text."""
        upsert_budget(db, "expenses:food", "2026-01", "600.00")
        # Query with raw SQL to check the actual stored value
        row = db.conn.execute(
            "SELECT amount, typeof(amount) FROM budgets LIMIT 1"
        ).fetchone()
        assert row[0] == "600.00"
        assert row[1] == "text"

    def test_goal_amounts_stored_as_text(self, db: Database):
        """Goal amounts round-trip as exact text."""
        goal = create_goal(
            db, "Test", "10000.00", "savings"
        )
        update_goal_progress(db, goal.id, "2500.50")
        row = db.conn.execute(
            "SELECT target_amount, typeof(target_amount), "
            "current_amount, typeof(current_amount) "
            "FROM goals WHERE id = ?",
            (goal.id,),
        ).fetchone()
        assert row[0] == "10000.00"
        assert row[1] == "text"
        assert row[2] == "2500.50"
        assert row[3] == "text"

    def test_reconciliation_balance_stored_as_text(self, db: Database):
        """Reconciliation balance round-trips as exact text."""
        record_reconciliation(
            db, "assets:checking", "2026-01-31", "12345.67"
        )
        row = db.conn.execute(
            "SELECT statement_balance, typeof(statement_balance) "
            "FROM reconciliations LIMIT 1"
        ).fetchone()
        assert row[0] == "12345.67"
        assert row[1] == "text"
