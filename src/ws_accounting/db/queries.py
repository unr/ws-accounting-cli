"""Named query functions for the sidecar database.

All functions take a sqlite3.Connection or Database object as the first argument
and perform CRUD operations using the dataclass models.
"""

from __future__ import annotations

import sqlite3

from ws_accounting.db.models import (
    Budget,
    CategorizationEntry,
    Goal,
    ImportHistory,
    ImportProfile,
    InsightsCacheEntry,
    RecurringTransaction,
)


# ---------------------------------------------------------------------------
# Budget queries
# ---------------------------------------------------------------------------


def get_budgets(db_or_conn, month: str | None = None) -> list[Budget]:
    """Return all budgets ordered by category.

    Args:
        db_or_conn: A Database object or sqlite3.Connection.
        month: Optional YYYY-MM filter (currently returns all budgets).
    """
    conn = _resolve_conn(db_or_conn)
    rows = conn.execute(
        "SELECT * FROM budgets ORDER BY category"
    ).fetchall()
    return [Budget.from_row(r) for r in rows]


def upsert_budget(db_or_conn, budget: Budget) -> int:
    """Insert or update a budget. Returns the row id."""
    conn = _resolve_conn(db_or_conn)
    if budget.id is not None:
        conn.execute(
            """UPDATE budgets
               SET category = ?, amount = ?, period = ?,
                   start_date = ?, end_date = ?, rollover = ?,
                   updated_at = datetime('now')
               WHERE id = ?""",
            (
                budget.category,
                budget.amount,
                budget.period,
                budget.start_date,
                budget.end_date,
                budget.rollover,
                budget.id,
            ),
        )
        conn.commit()
        return budget.id
    else:
        cursor = conn.execute(
            """INSERT INTO budgets (category, amount, period, start_date, end_date, rollover)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                budget.category,
                budget.amount,
                budget.period,
                budget.start_date,
                budget.end_date,
                budget.rollover,
            ),
        )
        conn.commit()
        return cursor.lastrowid


def delete_budget(db_or_conn, budget_id: int) -> None:
    """Delete a budget by id."""
    conn = _resolve_conn(db_or_conn)
    conn.execute("DELETE FROM budgets WHERE id = ?", (budget_id,))
    conn.commit()


# ---------------------------------------------------------------------------
# Goal queries
# ---------------------------------------------------------------------------


def get_goals(db_or_conn) -> list[Goal]:
    """Return all goals ordered by creation time."""
    conn = _resolve_conn(db_or_conn)
    rows = conn.execute(
        "SELECT * FROM goals ORDER BY created_at"
    ).fetchall()
    return [Goal.from_row(r) for r in rows]


def upsert_goal(db_or_conn, goal: Goal) -> int:
    """Insert or update a goal. Returns the row id."""
    conn = _resolve_conn(db_or_conn)
    if goal.id is not None:
        conn.execute(
            """UPDATE goals
               SET name = ?, target_amount = ?, current_amount = ?,
                   account = ?, target_date = ?,
                   updated_at = datetime('now')
               WHERE id = ?""",
            (
                goal.name,
                goal.target_amount,
                goal.current_amount,
                goal.account,
                goal.target_date,
                goal.id,
            ),
        )
        conn.commit()
        return goal.id
    else:
        cursor = conn.execute(
            """INSERT INTO goals (name, target_amount, current_amount, account, target_date)
               VALUES (?, ?, ?, ?, ?)""",
            (
                goal.name,
                goal.target_amount,
                goal.current_amount,
                goal.account,
                goal.target_date,
            ),
        )
        conn.commit()
        return cursor.lastrowid


# ---------------------------------------------------------------------------
# Recurring transaction queries
# ---------------------------------------------------------------------------


def get_recurring(db_or_conn) -> list[RecurringTransaction]:
    """Return all recurring transactions ordered by next_due."""
    conn = _resolve_conn(db_or_conn)
    rows = conn.execute(
        "SELECT * FROM recurring_transactions ORDER BY next_due"
    ).fetchall()
    return [RecurringTransaction.from_row(r) for r in rows]


def upsert_recurring(db_or_conn, rec: RecurringTransaction) -> int:
    """Insert or update a recurring transaction. Returns the row id."""
    conn = _resolve_conn(db_or_conn)
    if rec.id is not None:
        conn.execute(
            """UPDATE recurring_transactions
               SET description = ?, amount = ?, from_account = ?,
                   to_account = ?, frequency = ?, next_due = ?,
                   last_generated = ?, active = ?
               WHERE id = ?""",
            (
                rec.description,
                rec.amount,
                rec.from_account,
                rec.to_account,
                rec.frequency,
                rec.next_due,
                rec.last_generated,
                rec.active,
                rec.id,
            ),
        )
        conn.commit()
        return rec.id
    else:
        cursor = conn.execute(
            """INSERT INTO recurring_transactions
               (description, amount, from_account, to_account,
                frequency, next_due, last_generated, active)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                rec.description,
                rec.amount,
                rec.from_account,
                rec.to_account,
                rec.frequency,
                rec.next_due,
                rec.last_generated,
                rec.active,
            ),
        )
        conn.commit()
        return cursor.lastrowid


# ---------------------------------------------------------------------------
# Categorization queries
# ---------------------------------------------------------------------------


def get_cached_category(
    conn: sqlite3.Connection, description_hash: str
) -> CategorizationEntry | None:
    """Look up a cached categorization by description hash. Returns None on miss."""
    row = conn.execute(
        "SELECT * FROM categorization_cache WHERE description_hash = ?",
        (description_hash,),
    ).fetchone()
    if row is None:
        return None
    # Increment used_count on hit
    conn.execute(
        "UPDATE categorization_cache SET used_count = used_count + 1 WHERE description_hash = ?",
        (description_hash,),
    )
    conn.commit()
    return CategorizationEntry.from_row(row)


def cache_category(conn_or_db, entry_or_desc=None, bucket=None, account=None, confidence=None, source=None) -> None:
    """Cache a categorization result (upsert on description_hash).

    Accepts two call forms:
      cache_category(conn, CategorizationEntry)
      cache_category(db, description, bucket, account, confidence, source)
    """
    if isinstance(entry_or_desc, CategorizationEntry):
        # Form 1: (conn, entry)
        conn = conn_or_db if isinstance(conn_or_db, sqlite3.Connection) else conn_or_db
        entry = entry_or_desc
    else:
        # Form 2: (db, desc, bucket, account, confidence, source)
        conn = _resolve_conn(conn_or_db)
        desc = entry_or_desc
        entry = CategorizationEntry(
            description_hash=_desc_hash(desc, bucket or ""),
            description=desc,
            amount_bucket=bucket,
            suggested_account=account or "expenses:other",
            confidence=confidence or 0.0,
            source=source or "ai",
        )

    if isinstance(conn, sqlite3.Connection):
        real_conn = conn
    else:
        real_conn = conn.connect() if hasattr(conn, 'connect') else conn

    real_conn.execute(
        """INSERT INTO categorization_cache
           (description_hash, description, amount_bucket, suggested_account,
            confidence, source, used_count)
           VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(description_hash) DO UPDATE SET
               description = excluded.description,
               amount_bucket = excluded.amount_bucket,
               suggested_account = excluded.suggested_account,
               confidence = excluded.confidence,
               source = excluded.source,
               used_count = used_count + 1""",
        (
            entry.description_hash,
            entry.description,
            entry.amount_bucket,
            entry.suggested_account,
            entry.confidence,
            entry.source,
            entry.used_count if hasattr(entry, 'used_count') and entry.used_count else 1,
        ),
    )
    real_conn.commit()


def record_correction(
    conn_or_db,
    original_desc: str,
    original_acct: str,
    corrected_acct: str,
) -> None:
    """Record a user correction to a categorization."""
    conn = _resolve_conn(conn_or_db)
    # Upsert: increment count if same correction exists
    existing = conn.execute(
        "SELECT id, correction_count FROM categorization_corrections WHERE original_description = ? AND corrected_account = ?",
        (original_desc, corrected_acct),
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE categorization_corrections SET correction_count = correction_count + 1, updated_at = datetime('now') WHERE id = ?",
            (existing[0],),
        )
    else:
        conn.execute(
            """INSERT INTO categorization_corrections
               (original_description, original_account, corrected_account, correction_count)
               VALUES (?, ?, ?, 1)""",
            (original_desc, original_acct, corrected_acct),
        )
    conn.commit()


# ---------------------------------------------------------------------------
# Settings queries
# ---------------------------------------------------------------------------


def get_setting(db_or_conn, key: str) -> str | None:
    """Get an app setting value. Returns None if not set."""
    conn = _resolve_conn(db_or_conn)
    row = conn.execute(
        "SELECT value FROM app_settings WHERE key = ?", (key,)
    ).fetchone()
    return row["value"] if row else None


def set_setting(db_or_conn, key: str, value: str) -> None:
    """Set an app setting (upsert)."""
    conn = _resolve_conn(db_or_conn)
    conn.execute(
        """INSERT INTO app_settings (key, value, updated_at)
           VALUES (?, ?, datetime('now'))
           ON CONFLICT(key) DO UPDATE SET
               value = excluded.value,
               updated_at = excluded.updated_at""",
        (key, value),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Import hash queries
# ---------------------------------------------------------------------------


def check_import_hash(db_or_conn, hash: str) -> bool:
    """Return True if the hash already exists (duplicate)."""
    conn = _resolve_conn(db_or_conn)
    row = conn.execute(
        "SELECT 1 FROM import_hashes WHERE hash = ?", (hash,)
    ).fetchone()
    return row is not None


def store_import_hash(db_or_conn, hash: str, source: str) -> None:
    """Store a transaction hash for duplicate detection."""
    conn = _resolve_conn(db_or_conn)
    conn.execute(
        """INSERT OR IGNORE INTO import_hashes (hash, source_file)
           VALUES (?, ?)""",
        (hash, source),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Import profile queries
# ---------------------------------------------------------------------------


def get_import_profiles(conn: sqlite3.Connection) -> list[ImportProfile]:
    """Return all import profiles ordered by name."""
    rows = conn.execute(
        "SELECT * FROM import_profiles ORDER BY name"
    ).fetchall()
    return [ImportProfile.from_row(r) for r in rows]


# ---------------------------------------------------------------------------
# Import history queries
# ---------------------------------------------------------------------------


def record_import(
    db_or_conn,
    csv_filename: str,
    profile_id: int | None = None,
    txn_count: int = 0,
    duplicate_count: int = 0,
) -> ImportHistory:
    """Record a CSV import event in import_history.

    Args:
        db_or_conn: A Database object or sqlite3.Connection.
        csv_filename: The name/path of the imported CSV file.
        profile_id: Optional import profile id.
        txn_count: Number of transactions imported.
        duplicate_count: Number of duplicates skipped.

    Returns:
        ImportHistory dataclass with the new row's id populated.
    """
    conn = _resolve_conn(db_or_conn)
    cursor = conn.execute(
        """INSERT INTO import_history (profile_id, file_path, imported_count, duplicate_count)
           VALUES (?, ?, ?, ?)""",
        (profile_id if profile_id else None, csv_filename, txn_count, duplicate_count),
    )
    conn.commit()
    row_id = cursor.lastrowid
    # Fetch the full row to populate imported_at
    row = conn.execute(
        "SELECT * FROM import_history WHERE id = ?", (row_id,)
    ).fetchone()
    return ImportHistory.from_row(row)


def store_import_hashes(
    db_or_conn,
    hashes: list[str],
    source: str | int,
) -> None:
    """Bulk insert transaction hashes for duplicate detection.

    Args:
        db_or_conn: A Database object or sqlite3.Connection.
        hashes: List of hash strings to store.
        source: Source identifier (file name or import history id).
    """
    conn = _resolve_conn(db_or_conn)
    source_str = str(source)
    for h in hashes:
        conn.execute(
            """INSERT OR IGNORE INTO import_hashes (hash, source_file)
               VALUES (?, ?)""",
            (h, source_str),
        )
    conn.commit()


# ---------------------------------------------------------------------------
# Lookup and utility helpers
# ---------------------------------------------------------------------------

from decimal import Decimal as _Decimal
import hashlib as _hashlib


def _resolve_conn(db_or_conn):
    """Accept either a Database object or sqlite3.Connection."""
    if isinstance(db_or_conn, sqlite3.Connection):
        return db_or_conn
    # Assume it's a Database wrapper with .connect()
    return db_or_conn.connect()


def amount_to_bucket(amount: _Decimal) -> str:
    """Convert a decimal amount to a bucket string for cache lookups."""
    abs_amount = abs(amount)
    if abs_amount < 25:
        return "$0-25"
    elif abs_amount < 100:
        return "$25-100"
    elif abs_amount < 500:
        return "$100-500"
    else:
        return "$500+"


def _desc_hash(description: str, bucket: str) -> str:
    key = f"{description.lower().strip()}|{bucket}"
    return _hashlib.sha256(key.encode()).hexdigest()[:16]


class _CacheResult:
    """Lightweight result from cache lookup."""

    def __init__(self, account: str, confidence: float, source: str = "ai"):
        self.account = account
        self.confidence = confidence
        self.source = source


def lookup_category(db_or_conn, description: str, bucket: str = ""):
    """Look up a cached categorization. Returns object with .account/.confidence/.source or None."""
    conn = _resolve_conn(db_or_conn)
    dhash = _desc_hash(description, bucket)
    row = conn.execute(
        "SELECT suggested_account, confidence, source FROM categorization_cache WHERE description_hash = ?",
        (dhash,),
    ).fetchone()
    if row:
        conn.execute(
            "UPDATE categorization_cache SET used_count = used_count + 1 WHERE description_hash = ?",
            (dhash,),
        )
        conn.commit()
        return _CacheResult(row[0], row[1], row[2] if len(row) > 2 else "ai")
    return None


def get_corrections_count(db_or_conn, description: str) -> int:
    """Get total correction count for a description."""
    conn = _resolve_conn(db_or_conn)
    row = conn.execute(
        "SELECT SUM(correction_count) FROM categorization_corrections WHERE original_description = ?",
        (description,),
    ).fetchone()
    return row[0] or 0 if row else 0


def get_due_recurring(db_or_conn, due_before: str | None = None) -> list[RecurringTransaction]:
    """Return active recurring transactions due before the given date.

    Args:
        db_or_conn: A Database object or sqlite3.Connection.
        due_before: ISO date string (YYYY-MM-DD). If None, returns all active.
    """
    conn = _resolve_conn(db_or_conn)
    if due_before:
        rows = conn.execute(
            "SELECT * FROM recurring_transactions WHERE active = 1 AND next_due <= ? ORDER BY next_due",
            (due_before,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM recurring_transactions WHERE active = 1 ORDER BY next_due"
        ).fetchall()
    return [RecurringTransaction.from_row(r) for r in rows]


# ---------------------------------------------------------------------------
# Legacy compatibility stubs
# ---------------------------------------------------------------------------


def create_goal(*args, **kwargs):
    """Legacy stub -- will be replaced in a later phase."""
    return None


def update_goal_progress(*args, **kwargs):
    """Legacy stub -- will be replaced in a later phase."""
    pass


def delete_goal(*args, **kwargs):
    """Legacy stub -- will be replaced in a later phase."""
    pass


def create_recurring(*args, **kwargs):
    """Legacy stub -- will be replaced in a later phase."""
    return None


def advance_recurring(*args, **kwargs):
    """Legacy stub -- will be replaced in a later phase."""
    pass


def delete_recurring(*args, **kwargs):
    """Legacy stub -- will be replaced in a later phase."""
    pass


def create_import_profile(*args, **kwargs):
    """Legacy stub -- will be replaced in a later phase."""
    return None


def record_reconciliation(*args, **kwargs):
    """Legacy stub -- will be replaced in a later phase."""
    pass


def get_last_reconciliation(*args, **kwargs):
    """Legacy stub -- will be replaced in a later phase."""
    return None


def cache_insights(db_or_conn, period: str, content: str, source: str = "ai") -> None:
    """Cache an AI insights result for a period.

    Upserts into insights_cache, using a SHA-256 hash of the period
    as the query_hash for uniqueness.
    """
    conn = _resolve_conn(db_or_conn)
    query_hash = _hashlib.sha256(period.encode()).hexdigest()[:16]
    conn.execute(
        """INSERT INTO insights_cache (query_hash, query, response, period)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(query_hash) DO UPDATE SET
               query = excluded.query,
               response = excluded.response,
               period = excluded.period,
               created_at = datetime('now')""",
        (query_hash, period, content, period),
    )
    conn.commit()


def get_cached_insights(db_or_conn, period: str) -> InsightsCacheEntry | None:
    """Retrieve the most recent cached insights for a period.

    Returns an InsightsCacheEntry with .content and .generated_at,
    or None if no cached entry exists.
    """
    conn = _resolve_conn(db_or_conn)
    row = conn.execute(
        "SELECT response, created_at, period FROM insights_cache WHERE period = ? ORDER BY created_at DESC LIMIT 1",
        (period,),
    ).fetchone()
    if row is None:
        return None
    return InsightsCacheEntry(
        content=row["response"],
        generated_at=row["created_at"],
        period=row["period"],
    )
