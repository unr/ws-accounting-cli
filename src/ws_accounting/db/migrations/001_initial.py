"""Initial database schema -- migration 001.

All monetary amounts are stored as TEXT, never REAL.
"""

import sqlite3


def upgrade(conn: sqlite3.Connection) -> None:
    """Apply migration 001: create all initial tables."""
    conn.executescript("""
        -- Budget periods
        CREATE TABLE IF NOT EXISTS budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            amount TEXT NOT NULL,
            period TEXT NOT NULL,
            start_date TEXT,
            end_date TEXT,
            rollover INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        -- Savings goals
        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            target_amount TEXT NOT NULL,
            current_amount TEXT DEFAULT '0',
            account TEXT,
            target_date TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        -- Recurring transactions
        CREATE TABLE IF NOT EXISTS recurring_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            description TEXT NOT NULL,
            amount TEXT NOT NULL,
            from_account TEXT NOT NULL,
            to_account TEXT NOT NULL,
            frequency TEXT NOT NULL,
            next_due TEXT NOT NULL,
            last_generated TEXT,
            active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now'))
        );

        -- AI categorization cache
        CREATE TABLE IF NOT EXISTS categorization_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            description_hash TEXT UNIQUE NOT NULL,
            description TEXT NOT NULL,
            amount_bucket TEXT,
            suggested_account TEXT NOT NULL,
            confidence REAL NOT NULL,
            source TEXT DEFAULT 'ai',
            created_at TEXT DEFAULT (datetime('now')),
            used_count INTEGER DEFAULT 1
        );

        -- User corrections to AI categorization
        CREATE TABLE IF NOT EXISTS categorization_corrections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_description TEXT NOT NULL,
            original_account TEXT NOT NULL,
            corrected_account TEXT NOT NULL,
            correction_count INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        -- Reconciliation records
        CREATE TABLE IF NOT EXISTS reconciliations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account TEXT NOT NULL,
            statement_date TEXT NOT NULL,
            statement_balance TEXT NOT NULL,
            reconciled_at TEXT DEFAULT (datetime('now')),
            status TEXT DEFAULT 'completed'
        );

        -- Import profiles (bank-specific settings)
        CREATE TABLE IF NOT EXISTS import_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            bank_name TEXT,
            account TEXT NOT NULL,
            rules_file TEXT,
            date_format TEXT,
            csv_delimiter TEXT DEFAULT ',',
            skip_rows INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now'))
        );

        -- Import history
        CREATE TABLE IF NOT EXISTS import_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_id INTEGER REFERENCES import_profiles(id),
            file_path TEXT NOT NULL,
            imported_count INTEGER NOT NULL,
            duplicate_count INTEGER DEFAULT 0,
            imported_at TEXT DEFAULT (datetime('now'))
        );

        -- Hash-based duplicate detection
        CREATE TABLE IF NOT EXISTS import_hashes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hash TEXT UNIQUE NOT NULL,
            source_file TEXT,
            imported_at TEXT DEFAULT (datetime('now'))
        );

        -- AI insights cache
        CREATE TABLE IF NOT EXISTS insights_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query_hash TEXT UNIQUE NOT NULL,
            query TEXT NOT NULL,
            response TEXT NOT NULL,
            period TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            expires_at TEXT
        );

        -- App settings (key-value store)
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT DEFAULT (datetime('now'))
        );
    """)
