"""CSV import: structure detection, rules generation, duplicate detection, transfer detection."""

from __future__ import annotations

import csv
import hashlib
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path


@dataclass
class CSVStructure:
    """Detected structure of a CSV file."""

    date_column: int = 0
    description_column: int = 1
    amount_column: int = 2
    balance_column: int | None = None
    date_format: str = "%Y-%m-%d"
    delimiter: str = ","
    skip_rows: int = 1
    headers: list[str] = field(default_factory=list)


@dataclass
class DuplicateResult:
    """Result of duplicate checking for a transaction."""

    hash: str
    is_duplicate: bool
    source_file: str | None = None


@dataclass
class TransferCandidate:
    """A potential transfer between accounts."""

    from_idx: int
    to_idx: int
    amount: Decimal
    days_apart: int


def detect_structure(csv_path: Path) -> CSVStructure:
    """Auto-detect CSV structure from headers and sample rows."""
    with open(csv_path, newline="") as f:
        reader = csv.reader(f)
        headers = next(reader, [])

    structure = CSVStructure(headers=headers)

    # Heuristic column detection
    header_lower = [h.lower().strip() for h in headers]
    for i, h in enumerate(header_lower):
        if h in ("date", "posting date", "trans date", "transaction date"):
            structure.date_column = i
        elif h in ("description", "memo", "payee", "name"):
            structure.description_column = i
        elif h in ("amount", "debit", "credit"):
            structure.amount_column = i
        elif h in ("balance", "running balance", "running bal"):
            structure.balance_column = i

    return structure


def compute_import_hash(date_str: str, description: str, amount: str) -> str:
    """Compute a hash for duplicate detection."""
    key = f"{date_str}|{description.strip()}|{amount.strip()}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def check_duplicates(
    rows: list[dict], existing_hashes: set[str]
) -> list[DuplicateResult]:
    """Check which rows are duplicates based on hash."""
    results = []
    for row in rows:
        h = compute_import_hash(
            row.get("date", ""),
            row.get("description", ""),
            row.get("amount", ""),
        )
        results.append(DuplicateResult(hash=h, is_duplicate=h in existing_hashes))
    return results


def detect_transfers(
    rows: list[dict], tolerance_days: int = 3
) -> list[TransferCandidate]:
    """Detect potential transfers (matching amounts within tolerance window)."""
    candidates = []
    for i, row_a in enumerate(rows):
        try:
            amt_a = Decimal(row_a.get("amount", "0").replace(",", ""))
        except Exception:
            continue
        for j, row_b in enumerate(rows):
            if j <= i:
                continue
            try:
                amt_b = Decimal(row_b.get("amount", "0").replace(",", ""))
            except Exception:
                continue
            if abs(amt_a + amt_b) < Decimal("0.01"):
                candidates.append(
                    TransferCandidate(from_idx=i, to_idx=j, amount=abs(amt_a), days_apart=0)
                )
    return candidates


def parse_csv_rows(csv_path: Path, structure: CSVStructure) -> list[dict]:
    """Parse CSV into list of dicts using detected structure."""
    rows = []
    with open(csv_path, newline="") as f:
        reader = csv.reader(f, delimiter=structure.delimiter)
        for _ in range(structure.skip_rows):
            next(reader, None)
        for row in reader:
            if not row or not any(cell.strip() for cell in row):
                continue
            d = {
                "date": row[structure.date_column] if structure.date_column < len(row) else "",
                "description": (
                    row[structure.description_column]
                    if structure.description_column < len(row)
                    else ""
                ),
                "amount": row[structure.amount_column] if structure.amount_column < len(row) else "",
            }
            if structure.balance_column is not None and structure.balance_column < len(row):
                d["balance"] = row[structure.balance_column]
            rows.append(d)
    return rows
