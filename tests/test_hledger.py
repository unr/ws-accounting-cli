"""Tests for HLedger subprocess gateway."""

from pathlib import Path

import pytest

from ws_accounting.core.hledger import (
    HLedgerGateway,
    HledgerError,
    MIN_VERSION,
)


@pytest.mark.hledger
class TestCheckVersion:
    @pytest.mark.asyncio
    async def test_check_version_succeeds(self) -> None:
        """hledger is installed on this machine at >= 1.51."""
        version = await HLedgerGateway.check_version()
        parts = tuple(int(x) for x in version.split("."))
        assert parts >= MIN_VERSION

    @pytest.mark.asyncio
    async def test_check_version_returns_string(self) -> None:
        version = await HLedgerGateway.check_version()
        assert isinstance(version, str)
        assert "." in version


@pytest.mark.hledger
class TestAccounts:
    @pytest.mark.asyncio
    async def test_accounts_returns_list_of_strings(
        self, sample_journal: Path
    ) -> None:
        gw = HLedgerGateway()
        accounts = await gw.accounts(sample_journal)
        assert isinstance(accounts, list)
        assert all(isinstance(a, str) for a in accounts)

    @pytest.mark.asyncio
    async def test_accounts_contains_expected(
        self, sample_journal: Path
    ) -> None:
        gw = HLedgerGateway()
        accounts = await gw.accounts(sample_journal)
        assert "assets:bank:checking" in accounts
        assert "expenses:food:groceries" in accounts
        assert "income:salary" in accounts


@pytest.mark.hledger
class TestBalance:
    @pytest.mark.asyncio
    async def test_balance_returns_parsed_data(
        self, sample_journal: Path
    ) -> None:
        import json

        gw = HLedgerGateway()
        result = await gw.balance(sample_journal)
        # balance returns JSON string from hledger
        assert isinstance(result, str)
        data = json.loads(result)
        assert isinstance(data, list)
        assert len(data) > 0


@pytest.mark.hledger
class TestCheck:
    @pytest.mark.asyncio
    async def test_check_valid_journal(self, sample_journal: Path) -> None:
        gw = HLedgerGateway()
        assert await gw.check(sample_journal) is True


@pytest.mark.hledger
class TestPrintTransactions:
    @pytest.mark.asyncio
    async def test_print_returns_string(self, sample_journal: Path) -> None:
        gw = HLedgerGateway()
        result = await gw.print_transactions(sample_journal)
        assert isinstance(result, str)
        assert "Salary" in result or "Groceries" in result


@pytest.mark.hledger
class TestHledgerError:
    @pytest.mark.asyncio
    async def test_invalid_journal_path_raises(self, tmp_path: Path) -> None:
        gw = HLedgerGateway()
        bad_journal = tmp_path / "nonexistent" / "missing.journal"
        with pytest.raises(HledgerError):
            await gw.accounts(bad_journal)

    @pytest.mark.asyncio
    async def test_malformed_journal_raises(self, tmp_path: Path) -> None:
        bad_journal = tmp_path / "bad.journal"
        bad_journal.write_text("this is not valid journal syntax 2026-99-99\n")
        gw = HLedgerGateway()
        with pytest.raises(HledgerError):
            await gw.balance(bad_journal)
