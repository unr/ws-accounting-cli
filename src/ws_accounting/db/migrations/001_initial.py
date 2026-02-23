"""Initial database schema — v1."""

import sqlite3

VERSION = 1

SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE budgets (
    id INTEGER PRIMARY KEY,
    category TEXT NOT NULL,
    month TEXT NOT NULL,
    amount TEXT NOT NULL,
    rollover INTEGER DEFAULT 0,
    rollover_cap TEXT,
    UNIQUE(category, month)
);

CREATE TABLE goals (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    target_amount TEXT NOT NULL,
    current_amount TEXT NOT NULL DEFAULT '0',
    target_date TEXT,
    linked_account TEXT,
    type TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE recurring_transactions (
    id INTEGER PRIMARY KEY,
    description TEXT NOT NULL,
    amount TEXT NOT NULL,
    from_account TEXT NOT NULL,
    to_account TEXT NOT NULL,
    frequency TEXT NOT NULL,
    next_due TEXT NOT NULL,
    end_date TEXT,
    auto_enter INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE categorization_cache (
    id INTEGER PRIMARY KEY,
    description TEXT NOT NULL,
    amount_bucket TEXT NOT NULL,
    account TEXT NOT NULL,
    confidence REAL NOT NULL,
    source TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(description, amount_bucket)
);

CREATE TABLE categorization_corrections (
    id INTEGER PRIMARY KEY,
    description TEXT NOT NULL,
    original_account TEXT NOT NULL,
    corrected_account TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE reconciliations (
    id INTEGER PRIMARY KEY,
    account TEXT NOT NULL,
    statement_date TEXT NOT NULL,
    statement_balance TEXT NOT NULL,
    reconciled_at TEXT DEFAULT (datetime('now')),
    status TEXT NOT NULL DEFAULT 'complete'
);

CREATE TABLE import_profiles (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    bank_name TEXT,
    rules_path TEXT NOT NULL,
    default_status TEXT DEFAULT '*',
    last_used TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE import_history (
    id INTEGER PRIMARY KEY,
    csv_filename TEXT NOT NULL,
    profile_id INTEGER REFERENCES import_profiles(id),
    txn_count INTEGER NOT NULL,
    duplicate_count INTEGER DEFAULT 0,
    imported_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE insights_cache (
    id INTEGER PRIMARY KEY,
    period TEXT NOT NULL,
    content TEXT NOT NULL,
    model TEXT NOT NULL,
    generated_at TEXT DEFAULT (datetime('now')),
    UNIQUE(period, generated_at)
);

CREATE TABLE import_hashes (
    id INTEGER PRIMARY KEY,
    hash TEXT NOT NULL UNIQUE,
    import_history_id INTEGER REFERENCES import_history(id),
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT DEFAULT (datetime('now'))
);
"""


def upgrade(conn: sqlite3.Connection) -> None:
    """Apply migration 001."""
    conn.executescript(SQL)
