"""Journal file read/write with atomic writes and file locking."""

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


def write_transactions(
    path: Path,
    transactions: list[Transaction],
    append: bool = True,
) -> None:
    """Write transactions to a journal file with atomic writes."""
    content = "\n\n".join(
        format_transaction(txn) for txn in transactions
    )

    if append and path.exists():
        existing = path.read_text()
        if not existing.endswith("\n"):
            existing += "\n"
        content = existing + "\n" + content + "\n"
    else:
        content = content + "\n"

    atomic_write(path, content)


def update_includes(
    main_journal: Path, include_path: str
) -> None:
    """Add an include directive to the main journal if not present."""
    directive = f"include {include_path}"

    if main_journal.exists():
        content = main_journal.read_text()
        # Check if already included
        for line in content.split("\n"):
            if line.strip() == directive:
                return
        # Add include
        if not content.endswith("\n"):
            content += "\n"
        content += directive + "\n"
        atomic_write(main_journal, content)
    else:
        atomic_write(main_journal, directive + "\n")


def create_backup(path: Path) -> Path:
    """Create a .backup copy of a file. Returns backup path."""
    backup = path.with_suffix(path.suffix + ".backup")
    if path.exists():
        backup.write_text(path.read_text())
    return backup


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
        fd = None  # Mark as closed so we don't double-close
        os.replace(tmp_path, path)
        tmp_path = None  # Replaced successfully, no cleanup needed
    except Exception:
        if fd is not None:
            os.close(fd)
        if tmp_path is not None and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


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
            # Clean up lock file
            try:
                self._lock_path.unlink()
            except OSError:
                pass
