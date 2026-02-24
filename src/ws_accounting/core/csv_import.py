"""CSV import pipeline -- structure detection, rules, dedup, transfers."""

from __future__ import annotations

import csv
import hashlib
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

# Common header synonyms for auto-detection
_DATE_HEADERS = {
    "date", "posted", "posted date", "transaction date",
    "trans date", "posting date", "effective date", "value date",
}
_DESC_HEADERS = {
    "description", "memo", "payee", "merchant", "name",
    "narrative", "details", "particulars", "reference",
}
_AMOUNT_HEADERS = {
    "amount", "debit", "credit", "value", "sum",
    "transaction amount", "net amount",
}
_BALANCE_HEADERS = {
    "balance", "running balance", "running total",
    "available balance", "ledger balance",
}

# Date format candidates ordered by prevalence
_DATE_FORMATS = [
    "%Y-%m-%d",      # 2026-01-15
    "%m/%d/%Y",      # 01/15/2026
    "%d/%m/%Y",      # 15/01/2026
    "%m-%d-%Y",      # 01-15-2026
    "%d-%m-%Y",      # 15-01-2026
    "%Y/%m/%d",      # 2026/01/15
    "%m/%d/%y",      # 01/15/26
    "%d/%m/%y",      # 15/01/26
]


@dataclass
class CSVColumn:
    index: int
    header: str
    sample_values: list[str]


@dataclass
class CSVStructure:
    """Detected CSV structure."""

    columns: list[CSVColumn]
    date_column: int | None = None
    description_column: int | None = None
    amount_column: int | None = None
    balance_column: int | None = None
    date_format: str = "%Y-%m-%d"
    skip_lines: int = 1
    delimiter: str = ","


def _detect_delimiter(first_line: str) -> str:
    """Guess CSV delimiter from the first line."""
    for delim in [",", "\t", ";", "|"]:
        if delim in first_line:
            return delim
    return ","


def _match_header(header: str, candidates: set[str]) -> bool:
    """Check if a header (lowercased, stripped) matches any candidate."""
    h = header.strip().lower()
    return h in candidates


def _detect_date_format(samples: list[str]) -> str:
    """Try date format candidates against sample values."""
    from datetime import datetime

    for fmt in _DATE_FORMATS:
        matches = 0
        for sample in samples:
            s = sample.strip()
            if not s:
                continue
            try:
                datetime.strptime(s, fmt)
                matches += 1
            except ValueError:
                pass
        if matches > 0 and matches == sum(
            1 for s in samples if s.strip()
        ):
            return fmt
    return "%Y-%m-%d"


def detect_structure(
    csv_path: Path, max_sample: int = 5
) -> CSVStructure:
    """Auto-detect CSV column structure from headers and sample data."""
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        raw_first = f.readline()

    delimiter = _detect_delimiter(raw_first)

    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f, delimiter=delimiter)
        headers = next(reader, [])
        sample_rows: list[list[str]] = []
        for row in reader:
            if row and any(c.strip() for c in row):
                sample_rows.append(row)
                if len(sample_rows) >= max_sample:
                    break

    columns: list[CSVColumn] = []
    for i, header in enumerate(headers):
        samples = [
            row[i] if i < len(row) else ""
            for row in sample_rows
        ]
        columns.append(
            CSVColumn(index=i, header=header.strip(), sample_values=samples)
        )

    date_col: int | None = None
    desc_col: int | None = None
    amount_col: int | None = None
    balance_col: int | None = None

    for col in columns:
        h = col.header
        if date_col is None and _match_header(h, _DATE_HEADERS):
            date_col = col.index
        elif desc_col is None and _match_header(h, _DESC_HEADERS):
            desc_col = col.index
        elif amount_col is None and _match_header(h, _AMOUNT_HEADERS):
            amount_col = col.index
        elif balance_col is None and _match_header(h, _BALANCE_HEADERS):
            balance_col = col.index

    # Detect date format from samples
    date_fmt = "%Y-%m-%d"
    if date_col is not None:
        date_samples = [
            row[date_col] if date_col < len(row) else ""
            for row in sample_rows
        ]
        date_fmt = _detect_date_format(date_samples)

    return CSVStructure(
        columns=columns,
        date_column=date_col,
        description_column=desc_col,
        amount_column=amount_col,
        balance_column=balance_col,
        date_format=date_fmt,
        skip_lines=1,
        delimiter=delimiter,
    )


def generate_rules(
    structure: CSVStructure, account: str, output_path: Path
) -> Path:
    """Generate an hledger .rules file from detected structure."""
    field_names: list[str] = []
    for col in structure.columns:
        name = col.header.lower().replace(" ", "_")
        if not name:
            name = f"field{col.index}"
        # Sanitize: keep only alphanumeric and underscore
        name = re.sub(r"[^a-z0-9_]", "_", name)
        field_names.append(name)

    lines = [
        f"skip {structure.skip_lines}",
        "",
        "fields " + ", ".join(field_names),
        "",
        f"date-format {structure.date_format}",
        "currency $",
        f"account1 {account}",
        "",
    ]
    output_path.write_text("\n".join(lines) + "\n")
    return output_path


def compute_import_hash(
    date_str: str, amount: str, description: str
) -> str:
    """SHA256 hash for duplicate detection."""
    normalized = re.sub(r"\s+", " ", description.strip().lower())
    data = f"{date_str}|{amount}|{normalized}"
    return hashlib.sha256(data.encode()).hexdigest()


@dataclass
class DuplicateResult:
    hash: str
    is_duplicate: bool
    row_index: int


def check_duplicates(
    rows: list[dict],  # [{"date": str, "amount": str, "description": str}]
    existing_hashes: set[str],
) -> list[DuplicateResult]:
    """Check each row against existing import hashes."""
    results: list[DuplicateResult] = []
    for i, row in enumerate(rows):
        h = compute_import_hash(
            row["date"], row["amount"], row["description"]
        )
        results.append(
            DuplicateResult(
                hash=h,
                is_duplicate=h in existing_hashes,
                row_index=i,
            )
        )
    return results


@dataclass
class TransferCandidate:
    """A pair of transactions that look like a transfer."""

    row_index_a: int
    row_index_b: int
    amount: Decimal
    date_a: str
    date_b: str


def detect_transfers(
    rows: list[dict],  # Must have "date", "amount", "description"
    window_days: int = 3,
) -> list[TransferCandidate]:
    """Detect potential transfers: matching opposite amounts within window."""
    candidates: list[TransferCandidate] = []
    for i, row_a in enumerate(rows):
        try:
            amt_a = Decimal(
                row_a["amount"]
                .replace(",", "")
                .replace("$", "")
            )
        except (InvalidOperation, ValueError):
            continue

        for j, row_b in enumerate(rows):
            if j <= i:
                continue
            try:
                amt_b = Decimal(
                    row_b["amount"]
                    .replace(",", "")
                    .replace("$", "")
                )
            except (InvalidOperation, ValueError):
                continue

            # Check opposite signs and same absolute amount
            if amt_a + amt_b == Decimal("0"):
                # Check date proximity
                try:
                    date_a = date.fromisoformat(row_a["date"])
                    date_b = date.fromisoformat(row_b["date"])
                    if abs((date_b - date_a).days) <= window_days:
                        candidates.append(
                            TransferCandidate(
                                row_index_a=i,
                                row_index_b=j,
                                amount=abs(amt_a),
                                date_a=row_a["date"],
                                date_b=row_b["date"],
                            )
                        )
                except ValueError:
                    continue

    return candidates


def parse_csv_rows(
    csv_path: Path, structure: CSVStructure
) -> list[dict]:
    """Parse CSV into list of dicts with date, amount, description keys."""
    rows: list[dict] = []
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f, delimiter=structure.delimiter)
        for _ in range(structure.skip_lines):
            next(reader, None)
        for row_data in reader:
            if not row_data or all(
                c.strip() == "" for c in row_data
            ):
                continue
            entry: dict[str, str] = {}
            if (
                structure.date_column is not None
                and structure.date_column < len(row_data)
            ):
                entry["date"] = row_data[
                    structure.date_column
                ].strip()
            if (
                structure.description_column is not None
                and structure.description_column < len(row_data)
            ):
                entry["description"] = row_data[
                    structure.description_column
                ].strip()
            if (
                structure.amount_column is not None
                and structure.amount_column < len(row_data)
            ):
                entry["amount"] = row_data[
                    structure.amount_column
                ].strip()
            if (
                structure.balance_column is not None
                and structure.balance_column < len(row_data)
            ):
                entry["balance"] = row_data[
                    structure.balance_column
                ].strip()
            rows.append(entry)
    return rows
