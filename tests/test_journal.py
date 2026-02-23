"""Tests for journal file operations."""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from ws_accounting.core.journal import (
    JournalLock,
    atomic_write,
    create_backup,
    format_amount,
    format_transaction,
    update_includes,
    write_transactions,
)
from ws_accounting.core.models import (
    Amount,
    Posting,
    Transaction,
    TransactionStatus,
)


class TestFormatAmount:
    def test_positive(self) -> None:
        amt = Amount(Decimal("1234.56"), "$")
        assert format_amount(amt) == "$1,234.56"

    def test_negative(self) -> None:
        amt = Amount(Decimal("-50.00"), "$")
        assert format_amount(amt) == "-$50.00"

    def test_zero(self) -> None:
        amt = Amount(Decimal("0.00"), "$")
        assert format_amount(amt) == "$0.00"

    def test_large_number(self) -> None:
        amt = Amount(Decimal("1000000.00"), "$")
        assert format_amount(amt) == "$1,000,000.00"

    def test_eur_commodity(self) -> None:
        amt = Amount(Decimal("99.99"), "EUR")
        assert format_amount(amt) == "EUR99.99"

    def test_small_amount(self) -> None:
        amt = Amount(Decimal("0.01"), "$")
        assert format_amount(amt) == "$0.01"


class TestFormatTransaction:
    def test_basic_cleared(self) -> None:
        txn = Transaction(
            date=date(2026, 1, 15),
            status=TransactionStatus.CLEARED,
            description="Groceries",
            postings=(
                Posting(
                    account="expenses:food",
                    amount=Amount(Decimal("50.00"), "$"),
                ),
                Posting(
                    account="assets:bank:checking",
                    amount=None,
                ),
            ),
        )
        result = format_transaction(txn)
        assert "2026-01-15 * Groceries" in result
        assert "expenses:food" in result
        assert "$50.00" in result
        assert "assets:bank:checking" in result

    def test_pending_status(self) -> None:
        txn = Transaction(
            date=date(2026, 1, 16),
            status=TransactionStatus.PENDING,
            description="ATM",
            postings=(
                Posting(
                    account="expenses:cash",
                    amount=Amount(Decimal("100.00"), "$"),
                ),
                Posting(
                    account="assets:bank",
                    amount=Amount(Decimal("-100.00"), "$"),
                ),
            ),
        )
        result = format_transaction(txn)
        assert "2026-01-16 ! ATM" in result

    def test_unmarked_status(self) -> None:
        txn = Transaction(
            date=date(2026, 1, 17),
            status=TransactionStatus.UNMARKED,
            description="Transfer",
            postings=(
                Posting(
                    account="assets:savings",
                    amount=Amount(Decimal("200.00"), "$"),
                ),
                Posting(
                    account="assets:checking",
                    amount=None,
                ),
            ),
        )
        result = format_transaction(txn)
        # Unmarked has empty string status, so no marker
        assert "2026-01-17 Transfer" in result

    def test_with_payee(self) -> None:
        txn = Transaction(
            date=date(2026, 1, 15),
            status=TransactionStatus.CLEARED,
            description="Salary",
            payee="Employer",
            postings=(
                Posting(
                    account="assets:bank",
                    amount=Amount(Decimal("5000.00"), "$"),
                ),
                Posting(account="income:salary", amount=None),
            ),
        )
        result = format_transaction(txn)
        assert "Employer | Salary" in result

    def test_with_comment(self) -> None:
        txn = Transaction(
            date=date(2026, 1, 15),
            status=TransactionStatus.CLEARED,
            description="Food",
            comment="weekly groceries",
            postings=(
                Posting(
                    account="expenses:food",
                    amount=Amount(Decimal("80.00"), "$"),
                ),
                Posting(account="assets:bank", amount=None),
            ),
        )
        result = format_transaction(txn)
        assert "; weekly groceries" in result

    def test_with_tags(self) -> None:
        txn = Transaction(
            date=date(2026, 1, 15),
            status=TransactionStatus.CLEARED,
            description="Test",
            tags={"project": "home-reno"},
            postings=(
                Posting(
                    account="expenses:home",
                    amount=Amount(Decimal("500.00"), "$"),
                ),
                Posting(account="assets:bank", amount=None),
            ),
        )
        result = format_transaction(txn)
        assert "; project: home-reno" in result

    def test_with_date2(self) -> None:
        txn = Transaction(
            date=date(2026, 1, 15),
            date2=date(2026, 1, 20),
            status=TransactionStatus.CLEARED,
            description="Effective date test",
            postings=(
                Posting(
                    account="expenses:misc",
                    amount=Amount(Decimal("10.00"), "$"),
                ),
                Posting(account="assets:bank", amount=None),
            ),
        )
        result = format_transaction(txn)
        assert "2026-01-15=2026-01-20" in result

    def test_with_balance_assertion(self) -> None:
        txn = Transaction(
            date=date(2026, 1, 31),
            status=TransactionStatus.CLEARED,
            description="Balance check",
            postings=(
                Posting(
                    account="assets:bank:checking",
                    amount=Amount(Decimal("0.00"), "$"),
                    balance_assertion=Amount(
                        Decimal("1234.56"), "$"
                    ),
                ),
                Posting(
                    account="equity:adjustments",
                    amount=None,
                ),
            ),
        )
        result = format_transaction(txn)
        assert "= $1,234.56" in result

    def test_posting_comment(self) -> None:
        txn = Transaction(
            date=date(2026, 1, 15),
            status=TransactionStatus.CLEARED,
            description="Test",
            postings=(
                Posting(
                    account="expenses:food",
                    amount=Amount(Decimal("50.00"), "$"),
                    comment="organic section",
                ),
                Posting(account="assets:bank", amount=None),
            ),
        )
        result = format_transaction(txn)
        assert "; organic section" in result


class TestWriteTransactions:
    def _make_txn(self) -> Transaction:
        return Transaction(
            date=date(2026, 1, 15),
            status=TransactionStatus.CLEARED,
            description="Test",
            postings=(
                Posting(
                    account="expenses:food",
                    amount=Amount(Decimal("50.00"), "$"),
                ),
                Posting(account="assets:bank", amount=None),
            ),
        )

    def test_append_to_existing(self, tmp_path: Path) -> None:
        journal = tmp_path / "test.journal"
        journal.write_text("commodity $1,000.00\n")

        txn = self._make_txn()
        write_transactions(journal, [txn], append=True)

        content = journal.read_text()
        assert "commodity $1,000.00" in content
        assert "2026-01-15 * Test" in content

    def test_write_new_file(self, tmp_path: Path) -> None:
        journal = tmp_path / "new.journal"
        txn = self._make_txn()
        write_transactions(journal, [txn], append=False)

        content = journal.read_text()
        assert "2026-01-15 * Test" in content
        assert content.endswith("\n")

    def test_multiple_transactions(self, tmp_path: Path) -> None:
        journal = tmp_path / "test.journal"
        txn1 = self._make_txn()
        txn2 = Transaction(
            date=date(2026, 1, 16),
            status=TransactionStatus.CLEARED,
            description="Second",
            postings=(
                Posting(
                    account="expenses:transport",
                    amount=Amount(Decimal("30.00"), "$"),
                ),
                Posting(account="assets:bank", amount=None),
            ),
        )
        write_transactions(journal, [txn1, txn2], append=False)

        content = journal.read_text()
        assert "2026-01-15 * Test" in content
        assert "2026-01-16 * Second" in content
        # Two transactions separated by blank line
        assert "\n\n" in content


class TestUpdateIncludes:
    def test_adds_new_include(self, tmp_path: Path) -> None:
        journal = tmp_path / "main.journal"
        journal.write_text("commodity $1,000.00\n")

        update_includes(journal, "2026/january.journal")

        content = journal.read_text()
        assert "include 2026/january.journal" in content

    def test_skips_existing_include(self, tmp_path: Path) -> None:
        journal = tmp_path / "main.journal"
        journal.write_text(
            "commodity $1,000.00\n"
            "include 2026/january.journal\n"
        )

        update_includes(journal, "2026/january.journal")

        content = journal.read_text()
        # Should appear exactly once
        count = content.count("include 2026/january.journal")
        assert count == 1

    def test_creates_file_if_missing(self, tmp_path: Path) -> None:
        journal = tmp_path / "new_main.journal"
        assert not journal.exists()

        update_includes(journal, "2026/january.journal")

        assert journal.exists()
        content = journal.read_text()
        assert "include 2026/january.journal" in content

    def test_handles_no_trailing_newline(
        self, tmp_path: Path
    ) -> None:
        journal = tmp_path / "main.journal"
        journal.write_text("commodity $1,000.00")  # No trailing \n

        update_includes(journal, "2026/jan.journal")

        content = journal.read_text()
        assert "include 2026/jan.journal" in content
        # Should have newline before include
        assert "commodity $1,000.00\n" in content


class TestAtomicWrite:
    def test_creates_file(self, tmp_path: Path) -> None:
        target = tmp_path / "output.txt"
        atomic_write(target, "hello world\n")
        assert target.read_text() == "hello world\n"

    def test_overwrites_existing(self, tmp_path: Path) -> None:
        target = tmp_path / "output.txt"
        target.write_text("old content")
        atomic_write(target, "new content\n")
        assert target.read_text() == "new content\n"

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        target = tmp_path / "sub" / "dir" / "output.txt"
        atomic_write(target, "nested\n")
        assert target.read_text() == "nested\n"


class TestCreateBackup:
    def test_creates_backup_file(self, tmp_path: Path) -> None:
        original = tmp_path / "test.journal"
        original.write_text("original content\n")

        backup = create_backup(original)

        assert backup.exists()
        assert backup.name == "test.journal.backup"
        assert backup.read_text() == "original content\n"

    def test_returns_backup_path(self, tmp_path: Path) -> None:
        original = tmp_path / "test.journal"
        original.write_text("content")

        backup_path = create_backup(original)

        assert backup_path == original.with_suffix(".journal.backup")

    def test_nonexistent_file(self, tmp_path: Path) -> None:
        original = tmp_path / "missing.journal"
        backup = create_backup(original)
        # Returns path but does not create file since source missing
        assert not backup.exists()


class TestJournalLock:
    def test_lock_and_unlock(self, tmp_path: Path) -> None:
        journal = tmp_path / "test.journal"
        journal.write_text("content")

        with JournalLock(journal) as lock:
            assert lock._lock_fd is not None

        # After exiting, fd should be None
        assert lock._lock_fd is None

    def test_lock_file_cleaned_up(self, tmp_path: Path) -> None:
        journal = tmp_path / "test.journal"
        journal.write_text("content")
        lock_path = journal.with_suffix(".journal.lock")

        with JournalLock(journal):
            assert lock_path.exists()

        assert not lock_path.exists()
