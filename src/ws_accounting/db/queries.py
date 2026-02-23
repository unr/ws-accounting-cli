"""Named query functions for the sidecar database."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from ws_accounting.db.database import Database
from ws_accounting.db.models import (
    AppSetting,
    Budget,
    CategorizationCache,
    CategorizationCorrection,
    Goal,
    ImportHistory,
    ImportProfile,
    InsightsCache,
    Reconciliation,
    RecurringTransaction,
)


# ---------------------------------------------------------------------------
# Budget queries
# ---------------------------------------------------------------------------


def get_budgets(db: Database, month: str) -> list[Budget]:
    """Return all budgets for a given month (YYYY-MM)."""
    rows = db.conn.execute(
        "SELECT * FROM budgets WHERE month = ? ORDER BY category",
        (month,),
    ).fetchall()
    return [Budget.from_row(r) for r in rows]


def upsert_budget(
    db: Database,
    category: str,
    month: str,
    amount: str,
    rollover: bool = False,
    rollover_cap: str | None = None,
) -> None:
    """Insert or update a budget for category+month."""
    db.conn.execute(
        """INSERT INTO budgets (category, month, amount, rollover, rollover_cap)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(category, month) DO UPDATE SET
               amount = excluded.amount,
               rollover = excluded.rollover,
               rollover_cap = excluded.rollover_cap""",
        (category, month, amount, int(rollover), rollover_cap),
    )
    db.conn.commit()


def delete_budget(db: Database, budget_id: int) -> None:
    """Delete a budget by id."""
    db.conn.execute("DELETE FROM budgets WHERE id = ?", (budget_id,))
    db.conn.commit()


# ---------------------------------------------------------------------------
# Goal queries
# ---------------------------------------------------------------------------


def get_goals(db: Database) -> list[Goal]:
    """Return all goals."""
    rows = db.conn.execute(
        "SELECT * FROM goals ORDER BY created_at"
    ).fetchall()
    return [Goal.from_row(r) for r in rows]


def create_goal(
    db: Database,
    name: str,
    target_amount: str,
    type: str,
    target_date: str | None = None,
    linked_account: str | None = None,
) -> Goal:
    """Create a new goal and return it."""
    cursor = db.conn.execute(
        """INSERT INTO goals (name, target_amount, type, target_date, linked_account)
           VALUES (?, ?, ?, ?, ?)""",
        (name, target_amount, type, target_date, linked_account),
    )
    db.conn.commit()
    row = db.conn.execute(
        "SELECT * FROM goals WHERE id = ?", (cursor.lastrowid,)
    ).fetchone()
    return Goal.from_row(row)


def update_goal_progress(
    db: Database, goal_id: int, current_amount: str
) -> None:
    """Update the current_amount for a goal."""
    db.conn.execute(
        "UPDATE goals SET current_amount = ? WHERE id = ?",
        (current_amount, goal_id),
    )
    db.conn.commit()


def delete_goal(db: Database, goal_id: int) -> None:
    """Delete a goal by id."""
    db.conn.execute("DELETE FROM goals WHERE id = ?", (goal_id,))
    db.conn.commit()


# ---------------------------------------------------------------------------
# Recurring transaction queries
# ---------------------------------------------------------------------------


def get_recurring(db: Database) -> list[RecurringTransaction]:
    """Return all recurring transactions."""
    rows = db.conn.execute(
        "SELECT * FROM recurring_transactions ORDER BY next_due"
    ).fetchall()
    return [RecurringTransaction.from_row(r) for r in rows]


def get_due_recurring(
    db: Database, as_of: str
) -> list[RecurringTransaction]:
    """Return recurring transactions due on or before as_of date."""
    rows = db.conn.execute(
        """SELECT * FROM recurring_transactions
           WHERE next_due <= ? AND (end_date IS NULL OR end_date >= ?)
           ORDER BY next_due""",
        (as_of, as_of),
    ).fetchall()
    return [RecurringTransaction.from_row(r) for r in rows]


def create_recurring(
    db: Database,
    description: str,
    amount: str,
    from_account: str,
    to_account: str,
    frequency: str,
    next_due: str,
    end_date: str | None = None,
    auto_enter: bool = False,
) -> RecurringTransaction:
    """Create a recurring transaction and return it."""
    cursor = db.conn.execute(
        """INSERT INTO recurring_transactions
           (description, amount, from_account, to_account,
            frequency, next_due, end_date, auto_enter)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            description,
            amount,
            from_account,
            to_account,
            frequency,
            next_due,
            end_date,
            int(auto_enter),
        ),
    )
    db.conn.commit()
    row = db.conn.execute(
        "SELECT * FROM recurring_transactions WHERE id = ?",
        (cursor.lastrowid,),
    ).fetchone()
    return RecurringTransaction.from_row(row)


def advance_recurring(db: Database, recurring_id: int) -> None:
    """Advance next_due based on frequency (weekly/monthly/yearly)."""
    row = db.conn.execute(
        "SELECT frequency, next_due FROM recurring_transactions WHERE id = ?",
        (recurring_id,),
    ).fetchone()
    if row is None:
        return

    frequency = row["frequency"]
    current_due = date.fromisoformat(row["next_due"])

    if frequency == "weekly":
        new_due = current_due + timedelta(weeks=1)
    elif frequency == "monthly":
        # Advance by one month, keeping the day (clamped to month end)
        month = current_due.month + 1
        year = current_due.year
        if month > 12:
            month = 1
            year += 1
        # Clamp day to valid range for the new month
        day = min(current_due.day, _days_in_month(year, month))
        new_due = date(year, month, day)
    elif frequency == "yearly":
        new_year = current_due.year + 1
        day = min(
            current_due.day,
            _days_in_month(new_year, current_due.month),
        )
        new_due = date(new_year, current_due.month, day)
    else:
        return

    db.conn.execute(
        "UPDATE recurring_transactions SET next_due = ? WHERE id = ?",
        (new_due.isoformat(), recurring_id),
    )
    db.conn.commit()


def delete_recurring(db: Database, recurring_id: int) -> None:
    """Delete a recurring transaction by id."""
    db.conn.execute(
        "DELETE FROM recurring_transactions WHERE id = ?",
        (recurring_id,),
    )
    db.conn.commit()


# ---------------------------------------------------------------------------
# Categorization queries
# ---------------------------------------------------------------------------


def amount_to_bucket(amount: Decimal) -> str:
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


def lookup_category(
    db: Database, description: str, amount_bucket: str
) -> CategorizationCache | None:
    """Look up a cached categorization. Returns None on miss."""
    row = db.conn.execute(
        """SELECT * FROM categorization_cache
           WHERE description = ? AND amount_bucket = ?""",
        (description, amount_bucket),
    ).fetchone()
    return CategorizationCache.from_row(row) if row else None


def cache_category(
    db: Database,
    description: str,
    amount_bucket: str,
    account: str,
    confidence: float,
    source: str,
) -> None:
    """Cache a categorization result (upsert on description+bucket)."""
    db.conn.execute(
        """INSERT INTO categorization_cache
           (description, amount_bucket, account, confidence, source)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(description, amount_bucket) DO UPDATE SET
               account = excluded.account,
               confidence = excluded.confidence,
               source = excluded.source""",
        (description, amount_bucket, account, confidence, source),
    )
    db.conn.commit()


def record_correction(
    db: Database,
    description: str,
    original_account: str,
    corrected_account: str,
) -> None:
    """Record a user correction to a categorization."""
    db.conn.execute(
        """INSERT INTO categorization_corrections
           (description, original_account, corrected_account)
           VALUES (?, ?, ?)""",
        (description, original_account, corrected_account),
    )
    db.conn.commit()


def get_corrections_count(db: Database, description: str) -> int:
    """Return number of corrections for a given description."""
    row = db.conn.execute(
        """SELECT COUNT(*) FROM categorization_corrections
           WHERE description = ?""",
        (description,),
    ).fetchone()
    return row[0]


# ---------------------------------------------------------------------------
# Import queries
# ---------------------------------------------------------------------------


def create_import_profile(
    db: Database,
    name: str,
    rules_path: str,
    bank_name: str | None = None,
    default_status: str = "*",
) -> ImportProfile:
    """Create an import profile and return it."""
    cursor = db.conn.execute(
        """INSERT INTO import_profiles
           (name, rules_path, bank_name, default_status)
           VALUES (?, ?, ?, ?)""",
        (name, rules_path, bank_name, default_status),
    )
    db.conn.commit()
    row = db.conn.execute(
        "SELECT * FROM import_profiles WHERE id = ?",
        (cursor.lastrowid,),
    ).fetchone()
    return ImportProfile.from_row(row)


def get_import_profiles(db: Database) -> list[ImportProfile]:
    """Return all import profiles."""
    rows = db.conn.execute(
        "SELECT * FROM import_profiles ORDER BY name"
    ).fetchall()
    return [ImportProfile.from_row(r) for r in rows]


def record_import(
    db: Database,
    csv_filename: str,
    profile_id: int,
    txn_count: int,
    duplicate_count: int = 0,
) -> ImportHistory:
    """Record an import event and return it."""
    cursor = db.conn.execute(
        """INSERT INTO import_history
           (csv_filename, profile_id, txn_count, duplicate_count)
           VALUES (?, ?, ?, ?)""",
        (csv_filename, profile_id, txn_count, duplicate_count),
    )
    db.conn.commit()
    row = db.conn.execute(
        "SELECT * FROM import_history WHERE id = ?",
        (cursor.lastrowid,),
    ).fetchone()
    return ImportHistory.from_row(row)


def store_import_hashes(
    db: Database, hashes: list[str], import_history_id: int
) -> None:
    """Store a list of transaction hashes for duplicate detection."""
    db.conn.executemany(
        """INSERT OR IGNORE INTO import_hashes (hash, import_history_id)
           VALUES (?, ?)""",
        [(h, import_history_id) for h in hashes],
    )
    db.conn.commit()


def check_import_hash(db: Database, hash: str) -> bool:
    """Return True if the hash already exists (duplicate)."""
    row = db.conn.execute(
        "SELECT 1 FROM import_hashes WHERE hash = ?", (hash,)
    ).fetchone()
    return row is not None


# ---------------------------------------------------------------------------
# Reconciliation queries
# ---------------------------------------------------------------------------


def record_reconciliation(
    db: Database,
    account: str,
    statement_date: str,
    statement_balance: str,
) -> None:
    """Record a completed reconciliation."""
    db.conn.execute(
        """INSERT INTO reconciliations
           (account, statement_date, statement_balance)
           VALUES (?, ?, ?)""",
        (account, statement_date, statement_balance),
    )
    db.conn.commit()


def get_last_reconciliation(
    db: Database, account: str
) -> Reconciliation | None:
    """Return the most recent reconciliation for an account."""
    row = db.conn.execute(
        """SELECT * FROM reconciliations
           WHERE account = ?
           ORDER BY statement_date DESC, reconciled_at DESC
           LIMIT 1""",
        (account,),
    ).fetchone()
    return Reconciliation.from_row(row) if row else None


# ---------------------------------------------------------------------------
# Insights queries
# ---------------------------------------------------------------------------


def cache_insights(
    db: Database, period: str, content: str, model: str
) -> None:
    """Cache AI-generated insights for a period."""
    db.conn.execute(
        """INSERT INTO insights_cache (period, content, model)
           VALUES (?, ?, ?)""",
        (period, content, model),
    )
    db.conn.commit()


def get_cached_insights(
    db: Database, period: str
) -> InsightsCache | None:
    """Return the most recent cached insight for a period."""
    row = db.conn.execute(
        """SELECT * FROM insights_cache
           WHERE period = ?
           ORDER BY generated_at DESC
           LIMIT 1""",
        (period,),
    ).fetchone()
    return InsightsCache.from_row(row) if row else None


# ---------------------------------------------------------------------------
# Settings queries
# ---------------------------------------------------------------------------


def get_setting(db: Database, key: str) -> str | None:
    """Get an app setting value. Returns None if not set."""
    row = db.conn.execute(
        "SELECT value FROM app_settings WHERE key = ?", (key,)
    ).fetchone()
    return row["value"] if row else None


def set_setting(db: Database, key: str, value: str) -> None:
    """Set an app setting (upsert)."""
    db.conn.execute(
        """INSERT INTO app_settings (key, value, updated_at)
           VALUES (?, ?, datetime('now'))
           ON CONFLICT(key) DO UPDATE SET
               value = excluded.value,
               updated_at = excluded.updated_at""",
        (key, value),
    )
    db.conn.commit()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _days_in_month(year: int, month: int) -> int:
    """Return the number of days in a given month."""
    if month == 12:
        return (date(year + 1, 1, 1) - date(year, 12, 1)).days
    return (date(year, month + 1, 1) - date(year, month, 1)).days
