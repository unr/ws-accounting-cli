"""Tests for HLedger subprocess gateway."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from ws_accounting.core.hledger import (
    HLedgerError,
    HLedgerGateway,
    HLedgerNotFoundError,
    _parse_ver,
)


class TestHLedgerGatewayConstruction:
    def test_default_path(self, tmp_path: Path) -> None:
        journal = tmp_path / "test.journal"
        gw = HLedgerGateway(journal_path=journal)
        assert gw.journal_path == journal
        # hledger_path is either found via which or falls back to "hledger"
        assert isinstance(gw.hledger_path, str)

    def test_custom_hledger_path(self, tmp_path: Path) -> None:
        journal = tmp_path / "test.journal"
        gw = HLedgerGateway(
            journal_path=journal, hledger_path="/usr/local/bin/hledger"
        )
        assert gw.hledger_path == "/usr/local/bin/hledger"

    def test_journal_path_stored(self, tmp_path: Path) -> None:
        journal = tmp_path / "finances" / "main.journal"
        gw = HLedgerGateway(journal_path=journal)
        assert gw.journal_path == journal


class TestParseVer:
    def test_simple_version(self) -> None:
        assert _parse_ver("1.30") == (1, 30)

    def test_three_part_version(self) -> None:
        assert _parse_ver("1.34.1") == (1, 34, 1)

    def test_comparison(self) -> None:
        assert _parse_ver("1.34") > _parse_ver("1.30")
        assert _parse_ver("1.29") < _parse_ver("1.30")
        assert _parse_ver("2.0") > _parse_ver("1.99")


class TestCheckInstallation:
    @pytest.mark.asyncio
    async def test_not_found_raises(self, tmp_path: Path) -> None:
        journal = tmp_path / "test.journal"
        gw = HLedgerGateway(
            journal_path=journal, hledger_path="hledger"
        )
        with patch("ws_accounting.core.hledger.shutil.which", return_value=None):
            with pytest.raises(HLedgerNotFoundError, match="not found"):
                await gw.check_installation()

    @pytest.mark.asyncio
    async def test_version_too_old(self, tmp_path: Path) -> None:
        journal = tmp_path / "test.journal"
        gw = HLedgerGateway(
            journal_path=journal, hledger_path="/usr/bin/hledger"
        )

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(
            return_value=(b"hledger 1.20, linux-x86_64\n", b"")
        )

        with (
            patch(
                "ws_accounting.core.hledger.shutil.which",
                return_value="/usr/bin/hledger",
            ),
            patch(
                "asyncio.create_subprocess_exec",
                return_value=mock_proc,
            ),
        ):
            with pytest.raises(HLedgerError, match="1.30"):
                await gw.check_installation()

    @pytest.mark.asyncio
    async def test_valid_version(self, tmp_path: Path) -> None:
        journal = tmp_path / "test.journal"
        gw = HLedgerGateway(
            journal_path=journal, hledger_path="/usr/bin/hledger"
        )

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(
            return_value=(b"hledger 1.34, linux-x86_64\n", b"")
        )

        with (
            patch(
                "ws_accounting.core.hledger.shutil.which",
                return_value="/usr/bin/hledger",
            ),
            patch(
                "asyncio.create_subprocess_exec",
                return_value=mock_proc,
            ),
        ):
            info = await gw.check_installation()
            assert info.version == "1.34"
            assert info.path == "/usr/bin/hledger"

    @pytest.mark.asyncio
    async def test_exact_minimum_version(self, tmp_path: Path) -> None:
        journal = tmp_path / "test.journal"
        gw = HLedgerGateway(
            journal_path=journal, hledger_path="/usr/bin/hledger"
        )

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(
            return_value=(b"hledger 1.30\n", b"")
        )

        with (
            patch(
                "ws_accounting.core.hledger.shutil.which",
                return_value="/usr/bin/hledger",
            ),
            patch(
                "asyncio.create_subprocess_exec",
                return_value=mock_proc,
            ),
        ):
            info = await gw.check_installation()
            assert info.version == "1.30"


class TestRunCommand:
    @pytest.mark.asyncio
    async def test_hledger_error_raised(self, tmp_path: Path) -> None:
        journal = tmp_path / "test.journal"
        gw = HLedgerGateway(
            journal_path=journal, hledger_path="/usr/bin/hledger"
        )

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(
            return_value=(b"", b"hledger: error parsing journal\n")
        )
        mock_proc.returncode = 1

        with patch(
            "asyncio.create_subprocess_exec",
            return_value=mock_proc,
        ):
            with pytest.raises(HLedgerError, match="error parsing"):
                await gw._run("balance")

    @pytest.mark.asyncio
    async def test_successful_run(self, tmp_path: Path) -> None:
        journal = tmp_path / "test.journal"
        gw = HLedgerGateway(
            journal_path=journal, hledger_path="/usr/bin/hledger"
        )

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(
            return_value=(b'[["$100","assets:bank"]]', b"")
        )
        mock_proc.returncode = 0

        with patch(
            "asyncio.create_subprocess_exec",
            return_value=mock_proc,
        ):
            result = await gw._run("balance")
            assert result == '[["$100","assets:bank"]]'
