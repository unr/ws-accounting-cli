"""Comprehensive tests for the SQLite sidecar database layer."""

import sqlite3

import pytest

from ws_accounting.db.database import Database
from ws_accounting.db.models import (
    Budget,
    CategorizationEntry,
    Goal,
    ImportProfile,
    RecurringTransaction,
)
from ws_accounting.db import queries


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db(tmp_path) -> Database:
    """Create a Database with migrations applied, using tmp_path for file."""
    db_path = tmp_path / "test.db"
    database = Database(db_path)
    database.migrate()
    yield database
    database.close()


@pytest.fixture
def conn(db: Database) -> sqlite3.Connection:
    """Return the raw connection from the db fixture."""
    return db.connect()


# ---------------------------------------------------------------------------
# Database & migration tests
# ---------------------------------------------------------------------------


class TestDatabaseCore:
    def test_creates_file_and_schema_version(self, tmp_path):
        """Database creates the file and schema_version table on migrate()."""
        db_path = tmp_path / "new.db"
        database = Database(db_path)
        database.migrate()
        assert db_path.exists()
        # schema_version table should exist with version 1
        row = database.connect().execute(
            "SELECT MAX(version) FROM schema_version"
        ).fetchone()
        assert row[0] == 1
        database.close()

    def test_migration_001_creates_all_tables(self, conn: sqlite3.Connection):
        """Migration 001 creates all expected tables."""
        expected_tables = [
            "schema_version",
            "budgets",
            "goals",
            "recurring_transactions",
            "categorization_cache",
            "categorization_corrections",
            "reconciliations",
            "import_profiles",
            "import_history",
            "import_hashes",
            "insights_cache",
            "app_settings",
        ]
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        actual_tables = [r["name"] for r in rows]
        for table in expected_tables:
            assert table in actual_tables, f"Table {table} not found in schema"

    def test_migration_idempotent(self, db: Database):
        """Running migrate again does nothing (no error, same version)."""
        db.migrate()
        row = db.connect().execute(
            "SELECT MAX(version) FROM schema_version"
        ).fetchone()
        assert row[0] == 1

    def test_connection_reuse(self, db: Database):
        """Calling connect() twice returns the same connection object."""
        conn1 = db.connect()
        conn2 = db.connect()
        assert conn1 is conn2

    def test_context_manager(self, tmp_path):
        """Context manager opens and closes the connection."""
        db_path = tmp_path / "ctx.db"
        with Database(db_path) as database:
            database.migrate()
            assert database._conn is not None
        assert database._conn is None

    def test_wal_mode_enabled(self, conn: sqlite3.Connection):
        """WAL journal mode is set (file-based DBs)."""
        row = conn.execute("PRAGMA journal_mode").fetchone()
        assert row[0] == "wal"

    def test_foreign_keys_enabled(self, conn: sqlite3.Connection):
        """Foreign keys pragma is on."""
        row = conn.execute("PRAGMA foreign_keys").fetchone()
        assert row[0] == 1


# ---------------------------------------------------------------------------
# Budget CRUD tests
# ---------------------------------------------------------------------------


class TestBudgets:
    def test_insert_and_get(self, conn: sqlite3.Connection):
        """Insert a budget and retrieve it."""
        budget = Budget(category="expenses:food", amount="600.00", period="monthly")
        row_id = queries.upsert_budget(conn, budget)
        assert row_id is not None

        budgets = queries.get_budgets(conn)
        assert len(budgets) == 1
        assert budgets[0].category == "expenses:food"
        assert budgets[0].amount == "600.00"
        assert budgets[0].period == "monthly"

    def test_update_existing(self, conn: sqlite3.Connection):
        """Upserting with an id updates the existing row."""
        budget = Budget(category="expenses:food", amount="600.00", period="monthly")
        row_id = queries.upsert_budget(conn, budget)

        budget.id = row_id
        budget.amount = "700.00"
        budget.rollover = 1
        queries.upsert_budget(conn, budget)

        budgets = queries.get_budgets(conn)
        assert len(budgets) == 1
        assert budgets[0].amount == "700.00"
        assert budgets[0].rollover == 1

    def test_delete_budget(self, conn: sqlite3.Connection):
        """Delete removes the budget."""
        budget = Budget(category="expenses:food", amount="600.00", period="monthly")
        row_id = queries.upsert_budget(conn, budget)

        queries.delete_budget(conn, row_id)
        assert len(queries.get_budgets(conn)) == 0

    def test_multiple_budgets(self, conn: sqlite3.Connection):
        """Multiple budgets can coexist."""
        queries.upsert_budget(
            conn, Budget(category="expenses:food", amount="600.00", period="monthly")
        )
        queries.upsert_budget(
            conn, Budget(category="expenses:housing", amount="1500.00", period="monthly")
        )
        budgets = queries.get_budgets(conn)
        assert len(budgets) == 2


# ---------------------------------------------------------------------------
# Goal CRUD tests
# ---------------------------------------------------------------------------


class TestGoals:
    def test_insert_and_get(self, conn: sqlite3.Connection):
        """Insert a goal and retrieve it."""
        goal = Goal(
            name="Emergency Fund",
            target_amount="10000.00",
            current_amount="0",
            target_date="2026-12-31",
        )
        row_id = queries.upsert_goal(conn, goal)
        assert row_id is not None

        goals = queries.get_goals(conn)
        assert len(goals) == 1
        assert goals[0].name == "Emergency Fund"
        assert goals[0].target_amount == "10000.00"
        assert goals[0].current_amount == "0"

    def test_update_existing(self, conn: sqlite3.Connection):
        """Upserting with an id updates the goal."""
        goal = Goal(name="Vacation", target_amount="3000.00")
        row_id = queries.upsert_goal(conn, goal)

        goal.id = row_id
        goal.current_amount = "1500.00"
        queries.upsert_goal(conn, goal)

        goals = queries.get_goals(conn)
        assert len(goals) == 1
        assert goals[0].current_amount == "1500.00"


# ---------------------------------------------------------------------------
# Categorization cache tests
# ---------------------------------------------------------------------------


class TestCategorizationCache:
    def test_cache_miss(self, conn: sqlite3.Connection):
        """Cache miss returns None."""
        result = queries.get_cached_category(conn, "nonexistent_hash")
        assert result is None

    def test_store_and_retrieve(self, conn: sqlite3.Connection):
        """Store a categorization and retrieve it by hash."""
        entry = CategorizationEntry(
            description_hash="abc123",
            description="WHOLE FOODS",
            amount_bucket="$25-100",
            suggested_account="expenses:food:groceries",
            confidence=0.95,
            source="ai",
        )
        queries.cache_category(conn, entry)

        result = queries.get_cached_category(conn, "abc123")
        assert result is not None
        assert result.description == "WHOLE FOODS"
        assert result.suggested_account == "expenses:food:groceries"
        assert result.confidence == 0.95
        assert result.source == "ai"

    def test_upsert_updates_on_conflict(self, conn: sqlite3.Connection):
        """Caching the same hash updates the record."""
        entry1 = CategorizationEntry(
            description_hash="abc123",
            description="STARBUCKS",
            suggested_account="expenses:food:coffee",
            confidence=0.8,
            source="ai",
        )
        queries.cache_category(conn, entry1)

        entry2 = CategorizationEntry(
            description_hash="abc123",
            description="STARBUCKS",
            suggested_account="expenses:food:dining",
            confidence=0.99,
            source="user",
        )
        queries.cache_category(conn, entry2)

        result = queries.get_cached_category(conn, "abc123")
        assert result.suggested_account == "expenses:food:dining"
        assert result.confidence == 0.99
        assert result.source == "user"

    def test_record_correction(self, conn: sqlite3.Connection):
        """Record a correction and verify it was stored."""
        queries.record_correction(
            conn, "AMZN", "expenses:shopping", "expenses:office"
        )
        row = conn.execute(
            "SELECT * FROM categorization_corrections WHERE original_description = ?",
            ("AMZN",),
        ).fetchone()
        assert row is not None
        assert row["original_account"] == "expenses:shopping"
        assert row["corrected_account"] == "expenses:office"


# ---------------------------------------------------------------------------
# Import hash dedup tests
# ---------------------------------------------------------------------------


class TestImportHashes:
    def test_store_and_check_exists(self, conn: sqlite3.Connection):
        """Store a hash and verify it exists."""
        queries.store_import_hash(conn, "txn_hash_001", "jan2026.csv")
        assert queries.check_import_hash(conn, "txn_hash_001") is True

    def test_check_nonexistent_returns_false(self, conn: sqlite3.Connection):
        """Checking a nonexistent hash returns False."""
        assert queries.check_import_hash(conn, "does_not_exist") is False

    def test_duplicate_store_no_error(self, conn: sqlite3.Connection):
        """Storing the same hash twice does not raise."""
        queries.store_import_hash(conn, "txn_hash_001", "jan2026.csv")
        queries.store_import_hash(conn, "txn_hash_001", "jan2026.csv")
        assert queries.check_import_hash(conn, "txn_hash_001") is True


# ---------------------------------------------------------------------------
# Settings tests
# ---------------------------------------------------------------------------


class TestSettings:
    def test_get_missing_returns_none(self, conn: sqlite3.Connection):
        """Getting a non-existent key returns None."""
        assert queries.get_setting(conn, "nonexistent") is None

    def test_set_and_get(self, conn: sqlite3.Connection):
        """Set a setting and retrieve it."""
        queries.set_setting(conn, "theme", "dark")
        assert queries.get_setting(conn, "theme") == "dark"

    def test_overwrite_existing(self, conn: sqlite3.Connection):
        """Setting an existing key overwrites the value."""
        queries.set_setting(conn, "theme", "dark")
        queries.set_setting(conn, "theme", "light")
        assert queries.get_setting(conn, "theme") == "light"


# ---------------------------------------------------------------------------
# Import profiles tests
# ---------------------------------------------------------------------------


class TestImportProfiles:
    def test_get_empty(self, conn: sqlite3.Connection):
        """No profiles returns empty list."""
        profiles = queries.get_import_profiles(conn)
        assert profiles == []

    def test_insert_and_get(self, conn: sqlite3.Connection):
        """Insert an import profile and retrieve it."""
        conn.execute(
            """INSERT INTO import_profiles (name, bank_name, account)
               VALUES (?, ?, ?)""",
            ("Chase Checking", "Chase", "assets:bank:checking"),
        )
        conn.commit()
        profiles = queries.get_import_profiles(conn)
        assert len(profiles) == 1
        assert profiles[0].name == "Chase Checking"
        assert profiles[0].bank_name == "Chase"
        assert profiles[0].account == "assets:bank:checking"


# ---------------------------------------------------------------------------
# Monetary values stored as TEXT (critical constraint)
# ---------------------------------------------------------------------------


class TestMonetaryTextStorage:
    """Verify that all monetary columns use TEXT, never REAL/FLOAT."""

    MONETARY_TABLES_AND_COLUMNS = [
        ("budgets", "amount"),
        ("goals", "target_amount"),
        ("goals", "current_amount"),
        ("recurring_transactions", "amount"),
        ("reconciliations", "statement_balance"),
    ]

    def test_monetary_columns_are_text(self, conn: sqlite3.Connection):
        """All monetary columns must be declared as TEXT."""
        for table, column in self.MONETARY_TABLES_AND_COLUMNS:
            rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
            col_info = {r["name"]: r["type"] for r in rows}
            assert column in col_info, f"Column {column} not found in {table}"
            assert col_info[column] == "TEXT", (
                f"{table}.{column} should be TEXT, got {col_info[column]}"
            )

    def test_budget_amount_roundtrips_as_text(self, conn: sqlite3.Connection):
        """Budget amount round-trips as exact text."""
        queries.upsert_budget(
            conn, Budget(category="expenses:food", amount="600.00", period="monthly")
        )
        row = conn.execute(
            "SELECT amount, typeof(amount) FROM budgets LIMIT 1"
        ).fetchone()
        assert row[0] == "600.00"
        assert row[1] == "text"

    def test_goal_amounts_roundtrip_as_text(self, conn: sqlite3.Connection):
        """Goal amounts round-trip as exact text."""
        goal = Goal(name="Test", target_amount="10000.00")
        row_id = queries.upsert_goal(conn, goal)

        goal.id = row_id
        goal.current_amount = "2500.50"
        queries.upsert_goal(conn, goal)

        row = conn.execute(
            "SELECT target_amount, typeof(target_amount), "
            "current_amount, typeof(current_amount) "
            "FROM goals WHERE id = ?",
            (row_id,),
        ).fetchone()
        assert row[0] == "10000.00"
        assert row[1] == "text"
        assert row[2] == "2500.50"
        assert row[3] == "text"
