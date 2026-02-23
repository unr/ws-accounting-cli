"""Shared test fixtures for ws-accounting tests."""

import os
import sqlite3
import tempfile
from decimal import Decimal
from pathlib import Path

import pytest


@pytest.fixture
def tmp_journal_dir(tmp_path: Path) -> Path:
    """Create a temporary directory for journal files."""
    journal_dir = tmp_path / "finances"
    journal_dir.mkdir()
    return journal_dir


@pytest.fixture
def sample_journal(tmp_journal_dir: Path) -> Path:
    """Create a minimal valid journal file for testing."""
    journal = tmp_journal_dir / "test.journal"
    journal.write_text(
        "commodity $1,000.00\n"
        "\n"
        "account assets:bank:checking\n"
        "account expenses:food:groceries\n"
        "account income:salary\n"
        "\n"
        "2026-01-15 * Employer | Salary\n"
        "    assets:bank:checking              $5,000.00\n"
        "    income:salary\n"
        "\n"
        "2026-01-16 * Whole Foods | Groceries\n"
        "    expenses:food:groceries              $85.42\n"
        "    assets:bank:checking\n"
    )
    return journal


@pytest.fixture
def empty_journal(tmp_journal_dir: Path) -> Path:
    """Create an empty journal with just the commodity directive."""
    journal = tmp_journal_dir / "empty.journal"
    journal.write_text("commodity $1,000.00\n")
    return journal


@pytest.fixture
def in_memory_db() -> sqlite3.Connection:
    """Create an in-memory SQLite database with the app schema."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    conn.executescript("""
        CREATE TABLE schema_version (
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

        INSERT INTO schema_version (version) VALUES (1);
    """)

    yield conn
    conn.close()


@pytest.fixture
def mock_hledger_path(tmp_path: Path) -> Path:
    """Create a mock hledger script for testing without real hledger."""
    mock = tmp_path / "hledger"
    mock.write_text(
        '#!/bin/bash\n'
        'echo "hledger mock"\n'
    )
    mock.chmod(0o755)
    return mock


@pytest.fixture(autouse=True)
def isolate_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure tests don't touch real user data."""
    monkeypatch.setenv("WS_ACCOUNTING_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("WS_ACCOUNTING_DATA_DIR", str(tmp_path / "data"))
