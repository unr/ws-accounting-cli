"""Shared test fixtures for ws-accounting."""

from pathlib import Path

import pytest


@pytest.fixture
def sample_journal_dir(tmp_path: Path) -> Path:
    """Create a temporary journal directory with sample data."""
    journal_dir = tmp_path / "finances"
    journal_dir.mkdir()
    return journal_dir


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
