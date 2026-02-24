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
