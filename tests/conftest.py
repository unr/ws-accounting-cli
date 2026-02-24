"""Shared test fixtures for ws-accounting."""

import sqlite3
from pathlib import Path

import pytest


@pytest.fixture
def sample_journal_dir(tmp_path: Path) -> Path:
    """Create a temporary journal directory with sample data."""
    journal_dir = tmp_path / "finances"
    journal_dir.mkdir()
    return journal_dir


# Alias for tests that use the old name
tmp_journal_dir = sample_journal_dir


@pytest.fixture
def sample_journal(sample_journal_dir: Path) -> Path:
    """Create a minimal journal file for testing."""
    journal = sample_journal_dir / "main.journal"
    journal.write_text(
        """\
; Test journal
commodity $1,000.00

2026-01-01 * Opening Balances
    assets:checking                    $1,000.00
    equity:opening balances

2026-01-15 * Grocery Store
    expenses:food:groceries              $50.00
    assets:checking

2026-01-20 * Employer | Salary
    assets:checking                    $3,000.00
    income:salary
"""
    )
    return journal


@pytest.fixture
def data_dir() -> Path:
    """Return the path to the package data directory."""
    return Path(__file__).parent.parent / "src" / "ws_accounting" / "data"


@pytest.fixture
def empty_journal(sample_journal_dir: Path) -> Path:
    """Create an empty journal with just the commodity directive."""
    journal = sample_journal_dir / "empty.journal"
    journal.write_text("commodity $1,000.00\n")
    return journal


@pytest.fixture
def in_memory_db() -> sqlite3.Connection:
    """Create an in-memory SQLite database with the app schema."""
    from ws_accounting.db.database import Database

    database = Database(":memory:")
    database.migrate()
    conn = database.connect()
    conn.row_factory = sqlite3.Row
    yield conn
    database.close()


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
