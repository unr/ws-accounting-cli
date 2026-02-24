"""HLedger subprocess gateway -- async wrapper for all hledger CLI calls."""

from __future__ import annotations

import asyncio
import json
import re
import shutil
from pathlib import Path


MIN_VERSION = (1, 51)


class HledgerError(Exception):
    """Error from hledger subprocess."""


# Backward-compatible aliases
HLedgerError = HledgerError


class HLedgerNotFoundError(Exception):
    """hledger binary not found."""


class HLedgerGateway:
    """Async gateway to hledger CLI commands."""

    def __init__(
        self,
        journal_path: Path | None = None,
        hledger_path: str | None = None,
    ):
        self.journal_path = journal_path
        self.hledger_path = hledger_path or shutil.which("hledger") or "hledger"

    def _resolve_journal(self, journal_path: Path | None) -> Path:
        """Resolve journal path from argument or instance default."""
        path = journal_path or self.journal_path
        if path is None:
            raise ValueError("journal_path must be provided either to the method or constructor")
        return path

    @classmethod
    async def check_version(cls, hledger_path: str | None = None) -> str:
        """Verify hledger is installed and meets MIN_VERSION.

        Returns the version string on success.
        Raises RuntimeError if hledger is below MIN_VERSION or not found.
        """
        path = hledger_path or shutil.which("hledger") or "hledger"
        proc = await asyncio.create_subprocess_exec(
            path,
            "--version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(
                f"Failed to run hledger --version: {stderr.decode().strip()}"
            )

        version_str = stdout.decode().strip()
        # Parse "hledger 1.51.2, mac-aarch64" or "hledger 1.51"
        match = re.search(r"hledger\s+([\d.]+)", version_str)
        if not match:
            raise RuntimeError(f"Could not parse hledger version from: {version_str}")

        ver_str = match.group(1)
        ver_tuple = tuple(int(x) for x in ver_str.split("."))

        if ver_tuple < MIN_VERSION:
            min_str = ".".join(str(x) for x in MIN_VERSION)
            raise RuntimeError(
                f"hledger {ver_str} found, but >= {min_str} is required"
            )

        return ver_str

    async def check_installation(self) -> object:
        """Verify hledger is installed. Backward-compat wrapper around check_version."""
        ver = await self.check_version(self.hledger_path)

        class _Info:
            def __init__(self, version: str, path: str):
                self.version = version
                self.path = path

        return _Info(version=ver, path=self.hledger_path)

    async def _run(
        self,
        *args: str,
        journal_path: Path | None = None,
        json_output: bool = False,
    ) -> str:
        """Run an hledger command and return stdout."""
        jp = self._resolve_journal(journal_path)
        cmd: list[str] = [self.hledger_path, "-f", str(jp)]
        if json_output:
            cmd.append("--output-format=json")
        cmd.extend(args)

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise HledgerError(stderr.decode().strip())

        return stdout.decode()

    @staticmethod
    def _build_kwargs_args(
        *,
        period: str | None = None,
        depth: int | None = None,
        account: str | None = None,
        query: str | None = None,
    ) -> list[str]:
        """Convert common kwargs into hledger CLI flags."""
        args: list[str] = []
        if period:
            args.extend(["-p", period])
        if depth is not None:
            args.extend(["--depth", str(depth)])
        if account:
            args.append(f"acct:{account}")
        if query:
            args.append(query)
        return args

    async def accounts(
        self,
        journal_path: Path | None = None,
        *,
        tree: bool = False,
        **kwargs: object,
    ) -> list[str]:
        """List all accounts in the journal."""
        extra = self._build_kwargs_args(
            period=kwargs.get("period"),  # type: ignore[arg-type]
            depth=kwargs.get("depth"),  # type: ignore[arg-type]
            account=kwargs.get("account"),  # type: ignore[arg-type]
            query=kwargs.get("query"),  # type: ignore[arg-type]
        )
        args = ["accounts"]
        if tree:
            args.append("--tree")
        args.extend(extra)
        result = await self._run(*args, journal_path=journal_path)
        return [line.strip() for line in result.strip().split("\n") if line.strip()]

    async def balance(
        self,
        journal_path: Path | None = None,
        *,
        accounts: list[str] | None = None,
        period: str | None = None,
        budget: bool = False,
        tree: bool = False,
        depth: int | None = None,
        **kwargs: object,
    ) -> str | list[dict]:
        """Run hledger balance with JSON output."""
        extra = self._build_kwargs_args(
            period=period,
            depth=depth,
            account=kwargs.get("account"),  # type: ignore[arg-type]
            query=kwargs.get("query"),  # type: ignore[arg-type]
        )
        args = ["balance"]
        if budget:
            args.append("--budget")
        if tree:
            args.append("--tree")
        if accounts:
            args.extend(accounts)
        args.extend(extra)
        return await self._run(*args, journal_path=journal_path, json_output=True)

    async def register(
        self,
        journal_path: Path | None = None,
        *,
        query: str | None = None,
        period: str | None = None,
        limit: int | None = None,
        **kwargs: object,
    ) -> str | list[dict]:
        """Run hledger register with JSON output."""
        args = ["register"]
        if period:
            args.extend(["-p", period])
        if limit is not None:
            args.extend(["-n", str(limit)])
        if query:
            args.append(query)
        return await self._run(*args, journal_path=journal_path, json_output=True)

    async def balancesheet(
        self,
        journal_path: Path | None = None,
        **kwargs: object,
    ) -> str | dict:
        """Run hledger balancesheet with JSON output."""
        extra = self._build_kwargs_args(
            period=kwargs.get("period"),  # type: ignore[arg-type]
            depth=kwargs.get("depth"),  # type: ignore[arg-type]
            account=kwargs.get("account"),  # type: ignore[arg-type]
            query=kwargs.get("query"),  # type: ignore[arg-type]
        )
        return await self._run(
            "balancesheet", *extra, journal_path=journal_path, json_output=True
        )

    async def balance_sheet(self) -> str:
        """Run hledger balancesheet. Backward-compat alias."""
        return await self._run("balancesheet", json_output=True)

    async def income_statement(self, period: str | None = None) -> str:
        """Run hledger incomestatement with JSON output."""
        args = ["incomestatement"]
        if period:
            args.extend(["-p", period])
        return await self._run(*args, json_output=True)

    async def print_transactions(
        self,
        journal_path: Path | None = None,
        **kwargs: object,
    ) -> str:
        """Print journal entries as raw hledger output."""
        extra = self._build_kwargs_args(
            period=kwargs.get("period"),  # type: ignore[arg-type]
            depth=kwargs.get("depth"),  # type: ignore[arg-type]
            account=kwargs.get("account"),  # type: ignore[arg-type]
            query=kwargs.get("query"),  # type: ignore[arg-type]
        )
        return await self._run("print", *extra, journal_path=journal_path)

    async def print_journal(self, query: str | None = None) -> str:
        """Print journal entries. Backward-compat alias."""
        args = ["print"]
        if query:
            args.append(query)
        return await self._run(*args, json_output=False)

    async def check(self, journal_path: Path | None = None) -> bool:
        """Validate journal integrity. Returns True if valid."""
        try:
            await self._run("check", journal_path=journal_path)
            return True
        except HledgerError:
            return False

    async def import_csv(
        self,
        journal_path: Path | None = None,
        csv_path: Path | None = None,
        rules_path: Path | None = None,
    ) -> str:
        """Import a CSV file into the journal."""
        if csv_path is None:
            raise ValueError("csv_path is required")
        args = ["import", str(csv_path)]
        if rules_path is not None:
            args.extend(["--rules-file", str(rules_path)])
        return await self._run(*args, journal_path=journal_path)

    async def csv_import_dry_run(
        self, csv_path: Path, rules_path: Path
    ) -> str:
        """Preview CSV import without modifying journal. Backward-compat."""
        return await self._run(
            "import",
            str(csv_path),
            "--rules-file",
            str(rules_path),
            "--dry-run",
            json_output=False,
        )
