"""Journal file read/write with atomic writes and file locking."""

from __future__ import annotations

import fcntl
import os
import tempfile
from pathlib import Path

from ws_accounting.core.models import Amount, Transaction


def format_amount(amount: Amount) -> str:
    """Format an Amount for journal output.

    Produces strings like ``$1,234.56`` or ``-$1,234.56``.
    """
    abs_qty = abs(amount.quantity)
    formatted = f"{abs_qty:,.2f}"
    if amount.quantity < 0:
        return f"-{amount.commodity}{formatted}"
    return f"{amount.commodity}{formatted}"


def format_transaction(txn: Transaction) -> str:
    """Convert a Transaction to hledger journal format."""
    parts: list[str] = []

    # Date line
    date_str = txn.date.isoformat()
    if txn.date2:
        date_str += f"={txn.date2.isoformat()}"

    status = f" {txn.status.value}" if txn.status.value else ""

    # Description with optional payee
    desc = txn.description
    if txn.payee:
        desc = f"{txn.payee} | {txn.description}"

    header = f"{date_str}{status} {desc}"
    if txn.comment:
        header += f"  ; {txn.comment}"
    parts.append(header)

    # Tags
    if txn.tags:
        for key, value in txn.tags.items():
            parts.append(f"    ; {key}: {value}")

    # Postings
    for posting in txn.postings:
        line = f"    {posting.account}"
        if posting.amount is not None:
            amount_str = format_amount(posting.amount)
            # Right-align amount to column 40
            padding = max(2, 40 - len(posting.account) - 4)
            line += " " * padding + amount_str
        if posting.balance_assertion is not None:
            line += f" = {format_amount(posting.balance_assertion)}"
        if posting.comment:
            line += f"  ; {posting.comment}"
        parts.append(line)

    return "\n".join(parts)


def atomic_write(path: Path, content: str) -> None:
    """Write content atomically: write to temp file, then os.replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = None
    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
        )
        os.write(fd, content.encode())
        os.close(fd)
        fd = None
        os.replace(tmp_path, path)
        tmp_path = None
    except Exception:
        if fd is not None:
            os.close(fd)
        if tmp_path is not None and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def _locked_op(path: Path, operation: callable) -> None:
    """Execute an operation under an advisory file lock."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        operation()
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)
        try:
            lock_path.unlink()
        except OSError:
            pass


def write_transactions(
    path: Path,
    transactions: list[Transaction],
    append: bool = False,
) -> None:
    """Atomic write of transactions to a journal file with file locking.

    If append=True and file exists, appends to existing content.
    """
    content = "\n\n".join(format_transaction(txn) for txn in transactions)

    def _do_write() -> None:
        nonlocal content
        if append and path.exists():
            existing = path.read_text()
            if not existing.endswith("\n"):
                existing += "\n"
            final = existing + "\n" + content + "\n"
        else:
            final = content + "\n"
        atomic_write(path, final)

    _locked_op(path, _do_write)


def append_transaction(path: Path, txn: Transaction) -> None:
    """Append a single transaction to a journal file with locking."""

    def _do_append() -> None:
        existing = ""
        if path.exists():
            existing = path.read_text()
        if existing and not existing.endswith("\n"):
            existing += "\n"
        new_content = existing + "\n" + format_transaction(txn) + "\n"
        atomic_write(path, new_content)

    _locked_op(path, _do_append)


def ensure_includes(main_journal: Path, include_path: str) -> None:
    """Add an ``include`` directive to the main journal if missing."""
    directive = f"include {include_path}"

    if main_journal.exists():
        content = main_journal.read_text()
        for line in content.split("\n"):
            if line.strip() == directive:
                return
        if not content.endswith("\n"):
            content += "\n"
        content += directive + "\n"
        atomic_write(main_journal, content)
    else:
        atomic_write(main_journal, directive + "\n")


# Backward-compatible alias
update_includes = ensure_includes


def create_journal_structure(root: Path) -> None:
    """Create the standard journal directory structure.

    Creates:
        root/
            main.journal      (with include directives)
            accounts.journal   (empty, for account declarations)
            budgets.journal    (empty, for budget/periodic txns)
    """
    root.mkdir(parents=True, exist_ok=True)

    # Create sub-journals
    accounts_journal = root / "accounts.journal"
    if not accounts_journal.exists():
        accounts_journal.write_text("; Account declarations\n")

    budgets_journal = root / "budgets.journal"
    if not budgets_journal.exists():
        budgets_journal.write_text("; Budget and periodic transactions\n")

    # Create main journal with includes
    main_journal = root / "main.journal"
    if not main_journal.exists():
        main_journal.write_text(
            "; ws-accounting main journal\n"
            "commodity $1,000.00\n"
            "\n"
            "include accounts.journal\n"
            "include budgets.journal\n"
        )


def create_backup(path: Path) -> Path:
    """Create a .backup copy of a file. Returns backup path."""
    backup = path.with_suffix(path.suffix + ".backup")
    if path.exists():
        backup.write_text(path.read_text())
    return backup


class JournalLock:
    """Context manager for file locking on journal operations."""

    def __init__(self, path: Path):
        self.path = path
        self._lock_path = path.with_suffix(path.suffix + ".lock")
        self._lock_fd: int | None = None

    def __enter__(self) -> "JournalLock":
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock_fd = os.open(
            str(self._lock_path),
            os.O_CREAT | os.O_RDWR,
        )
        fcntl.flock(self._lock_fd, fcntl.LOCK_EX)
        return self

    def __exit__(self, *_: object) -> None:
        if self._lock_fd is not None:
            fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
            os.close(self._lock_fd)
            self._lock_fd = None
            try:
                self._lock_path.unlink()
            except OSError:
                pass
