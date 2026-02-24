"""HLedger subprocess gateway -- async wrapper for all hledger CLI calls."""

import asyncio
import shutil
from dataclasses import dataclass
from pathlib import Path


MIN_VERSION = "1.30"


@dataclass
class HLedgerInfo:
    version: str
    path: str


class HLedgerError(Exception):
    """Error from hledger subprocess."""


class HLedgerNotFoundError(Exception):
    """hledger binary not found."""


def _parse_ver(v: str) -> tuple[int, ...]:
    """Parse a dotted version string into a comparable tuple."""
    return tuple(int(x) for x in v.split("."))


class HLedgerGateway:
    """Async gateway to hledger CLI commands."""

    def __init__(
        self,
        journal_path: Path,
        hledger_path: str | None = None,
    ):
        self.journal_path = journal_path
        self.hledger_path = (
            hledger_path or shutil.which("hledger") or "hledger"
        )

    async def _run(
        self, *args: str, json_output: bool = True
    ) -> str:
        """Run hledger command and return stdout."""
        cmd = [self.hledger_path, "-f", str(self.journal_path)]
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
            raise HLedgerError(stderr.decode().strip())

        return stdout.decode()

    async def check_installation(self) -> HLedgerInfo:
        """Verify hledger is installed and meets minimum version."""
        path = shutil.which(self.hledger_path)
        if not path and self.hledger_path == "hledger":
            raise HLedgerNotFoundError(
                "hledger not found. Install it from"
                " https://hledger.org/install.html"
            )

        proc = await asyncio.create_subprocess_exec(
            self.hledger_path, "--version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        version_str = stdout.decode().strip()
        # Parse "hledger 1.34, ..." or "hledger 1.34"
        parts = version_str.split()
        if len(parts) >= 2:
            ver = parts[1].rstrip(",")
        else:
            ver = "0.0"

        if _parse_ver(ver) < _parse_ver(MIN_VERSION):
            raise HLedgerError(
                f"hledger {ver} found, but {MIN_VERSION}+ required"
            )

        return HLedgerInfo(
            version=ver, path=path or self.hledger_path
        )

    async def balance(
        self,
        accounts: list[str] | None = None,
        period: str | None = None,
        budget: bool = False,
        tree: bool = False,
        depth: int | None = None,
    ) -> str:
        """Run hledger balance and return JSON string."""
        args = ["balance"]
        if period:
            args.extend(["-p", period])
        if budget:
            args.append("--budget")
        if tree:
            args.append("--tree")
        if depth is not None:
            args.extend(["--depth", str(depth)])
        if accounts:
            args.extend(accounts)
        return await self._run(*args)

    async def register(
        self,
        query: str | None = None,
        period: str | None = None,
    ) -> str:
        """Run hledger register and return JSON string."""
        args = ["register"]
        if period:
            args.extend(["-p", period])
        if query:
            args.append(query)
        return await self._run(*args)

    async def income_statement(
        self, period: str | None = None
    ) -> str:
        """Run hledger incomestatement and return JSON string."""
        args = ["incomestatement"]
        if period:
            args.extend(["-p", period])
        return await self._run(*args)

    async def balance_sheet(self) -> str:
        """Run hledger balancesheet and return JSON string."""
        return await self._run("balancesheet")

    async def accounts(self, tree: bool = False) -> list[str]:
        """List all accounts."""
        args = ["accounts"]
        if tree:
            args.append("--tree")
        result = await self._run(*args, json_output=False)
        return [
            line.strip()
            for line in result.strip().split("\n")
            if line.strip()
        ]

    async def print_journal(
        self,
        query: str | None = None,
        period: str | None = None,
        json_format: bool = False,
    ) -> str:
        """Print journal entries."""
        args = ["print"]
        if period:
            args.extend(["-p", period])
        if query:
            args.append(query)
        return await self._run(*args, json_output=json_format)

    async def check(self) -> bool:
        """Validate journal integrity. Returns True if valid."""
        try:
            await self._run("check", json_output=False)
            return True
        except HLedgerError:
            return False

    async def csv_import_dry_run(
        self, csv_path: Path, rules_path: Path
    ) -> str:
        """Preview CSV import without modifying journal."""
        return await self._run(
            "import", str(csv_path),
            "--rules-file", str(rules_path),
            "--dry-run",
            json_output=False,
        )
