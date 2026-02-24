"""Tests for core/csv_import -- structure detection, rules, dedup, transfers."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ws_accounting.core.csv_import import (
    CSVColumn,
    CSVStructure,
    check_duplicates,
    compute_import_hash,
    detect_structure,
    detect_transfers,
    generate_rules,
    parse_csv_rows,
)


# -----------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------


@pytest.fixture
def sample_csv(tmp_path: Path) -> Path:
    """Create a sample CSV file with typical bank format."""
    csv_file = tmp_path / "bank_export.csv"
    csv_file.write_text(
        "Date,Description,Amount,Balance\n"
        "2026-01-15,Whole Foods,-85.42,1914.58\n"
        "2026-01-16,Employer Salary,5000.00,6914.58\n"
        "2026-01-17,Gas Station,-45.00,6869.58\n"
        "2026-01-18,Transfer Out,-500.00,6369.58\n"
        "2026-01-19,Transfer In,500.00,6869.58\n"
    )
    return csv_file


@pytest.fixture
def semicolon_csv(tmp_path: Path) -> Path:
    """Create a CSV file with semicolon delimiter."""
    csv_file = tmp_path / "euro_bank.csv"
    csv_file.write_text(
        "Date;Payee;Amount\n"
        "2026-01-15;Lidl;-25.50\n"
        "2026-01-16;Salary;3000.00\n"
    )
    return csv_file


@pytest.fixture
def us_date_csv(tmp_path: Path) -> Path:
    """Create a CSV file with US date format."""
    csv_file = tmp_path / "us_bank.csv"
    csv_file.write_text(
        "Posted Date,Memo,Amount\n"
        "01/15/2026,WHOLE FOODS,-85.42\n"
        "01/16/2026,DIRECT DEP EMPLOYER,5000.00\n"
    )
    return csv_file


# -----------------------------------------------------------------------
# compute_import_hash tests
# -----------------------------------------------------------------------


class TestComputeImportHash:
    def test_deterministic(self):
        """Same inputs always produce the same hash."""
        h1 = compute_import_hash(
            "2026-01-15", "-85.42", "Whole Foods"
        )
        h2 = compute_import_hash(
            "2026-01-15", "-85.42", "Whole Foods"
        )
        assert h1 == h2

    def test_different_inputs_different_hash(self):
        """Different inputs produce different hashes."""
        h1 = compute_import_hash(
            "2026-01-15", "-85.42", "Whole Foods"
        )
        h2 = compute_import_hash(
            "2026-01-16", "-85.42", "Whole Foods"
        )
        assert h1 != h2

    def test_normalized_whitespace(self):
        """Extra whitespace in description is normalized."""
        h1 = compute_import_hash(
            "2026-01-15", "-85.42", "Whole Foods"
        )
        h2 = compute_import_hash(
            "2026-01-15", "-85.42", "Whole   Foods"
        )
        assert h1 == h2

    def test_case_insensitive(self):
        """Description comparison is case-insensitive."""
        h1 = compute_import_hash(
            "2026-01-15", "-85.42", "WHOLE FOODS"
        )
        h2 = compute_import_hash(
            "2026-01-15", "-85.42", "whole foods"
        )
        assert h1 == h2

    def test_strips_whitespace(self):
        """Leading/trailing whitespace is stripped."""
        h1 = compute_import_hash(
            "2026-01-15", "-85.42", "Whole Foods"
        )
        h2 = compute_import_hash(
            "2026-01-15", "-85.42", "  Whole Foods  "
        )
        assert h1 == h2

    def test_hash_is_sha256_hex(self):
        """Result is a 64-char hex string (SHA256)."""
        h = compute_import_hash(
            "2026-01-15", "-85.42", "Whole Foods"
        )
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)


# -----------------------------------------------------------------------
# check_duplicates tests
# -----------------------------------------------------------------------


class TestCheckDuplicates:
    def test_no_duplicates(self):
        """When no hashes match, all are marked as new."""
        rows = [
            {
                "date": "2026-01-15",
                "amount": "-85.42",
                "description": "Whole Foods",
            },
            {
                "date": "2026-01-16",
                "amount": "5000.00",
                "description": "Salary",
            },
        ]
        results = check_duplicates(rows, set())
        assert len(results) == 2
        assert not results[0].is_duplicate
        assert not results[1].is_duplicate

    def test_with_known_duplicates(self):
        """Rows matching existing hashes are flagged as duplicates."""
        rows = [
            {
                "date": "2026-01-15",
                "amount": "-85.42",
                "description": "Whole Foods",
            },
            {
                "date": "2026-01-16",
                "amount": "5000.00",
                "description": "Salary",
            },
        ]
        # Pre-compute hash for first row
        known_hash = compute_import_hash(
            "2026-01-15", "-85.42", "Whole Foods"
        )
        results = check_duplicates(rows, {known_hash})

        assert results[0].is_duplicate
        assert not results[1].is_duplicate

    def test_row_index_tracking(self):
        """Each result tracks the correct row index."""
        rows = [
            {
                "date": "2026-01-15",
                "amount": "-85.42",
                "description": "A",
            },
            {
                "date": "2026-01-16",
                "amount": "5000.00",
                "description": "B",
            },
            {
                "date": "2026-01-17",
                "amount": "-45.00",
                "description": "C",
            },
        ]
        results = check_duplicates(rows, set())
        assert results[0].row_index == 0
        assert results[1].row_index == 1
        assert results[2].row_index == 2


# -----------------------------------------------------------------------
# detect_transfers tests
# -----------------------------------------------------------------------


class TestDetectTransfers:
    def test_matching_amounts_detected(self):
        """Opposite amounts within the window are flagged as transfers."""
        rows = [
            {
                "date": "2026-01-18",
                "amount": "-500.00",
                "description": "Transfer Out",
            },
            {
                "date": "2026-01-19",
                "amount": "500.00",
                "description": "Transfer In",
            },
        ]
        candidates = detect_transfers(rows, window_days=3)
        assert len(candidates) == 1
        assert candidates[0].amount == Decimal("500.00")
        assert candidates[0].row_index_a == 0
        assert candidates[0].row_index_b == 1

    def test_respects_window(self):
        """Transfers outside the date window are not detected."""
        rows = [
            {
                "date": "2026-01-10",
                "amount": "-500.00",
                "description": "Transfer Out",
            },
            {
                "date": "2026-01-20",
                "amount": "500.00",
                "description": "Transfer In",
            },
        ]
        candidates = detect_transfers(rows, window_days=3)
        assert len(candidates) == 0

    def test_no_false_positives_same_sign(self):
        """Amounts with the same sign are not flagged."""
        rows = [
            {
                "date": "2026-01-18",
                "amount": "500.00",
                "description": "Income A",
            },
            {
                "date": "2026-01-19",
                "amount": "500.00",
                "description": "Income B",
            },
        ]
        candidates = detect_transfers(rows, window_days=3)
        assert len(candidates) == 0

    def test_handles_dollar_sign_and_commas(self):
        """Amounts with $ and commas are parsed correctly."""
        rows = [
            {
                "date": "2026-01-18",
                "amount": "-$1,500.00",
                "description": "Transfer Out",
            },
            {
                "date": "2026-01-19",
                "amount": "$1,500.00",
                "description": "Transfer In",
            },
        ]
        candidates = detect_transfers(rows, window_days=3)
        assert len(candidates) == 1
        assert candidates[0].amount == Decimal("1500.00")

    def test_bad_amount_skipped(self):
        """Rows with unparseable amounts are skipped gracefully."""
        rows = [
            {
                "date": "2026-01-18",
                "amount": "bad",
                "description": "Error",
            },
            {
                "date": "2026-01-19",
                "amount": "500.00",
                "description": "Good",
            },
        ]
        candidates = detect_transfers(rows, window_days=3)
        assert len(candidates) == 0


# -----------------------------------------------------------------------
# detect_structure tests
# -----------------------------------------------------------------------


class TestDetectStructure:
    def test_standard_csv(self, sample_csv: Path):
        """Standard CSV with Date, Description, Amount, Balance."""
        structure = detect_structure(sample_csv)
        assert len(structure.columns) == 4
        assert structure.date_column == 0
        assert structure.description_column == 1
        assert structure.amount_column == 2
        assert structure.balance_column == 3
        assert structure.delimiter == ","
        assert structure.date_format == "%Y-%m-%d"

    def test_semicolon_delimiter(self, semicolon_csv: Path):
        """CSV with semicolon delimiter is detected."""
        structure = detect_structure(semicolon_csv)
        assert structure.delimiter == ";"
        assert len(structure.columns) == 3

    def test_us_date_format(self, us_date_csv: Path):
        """US date format (MM/DD/YYYY) is detected."""
        structure = detect_structure(us_date_csv)
        assert structure.date_format == "%m/%d/%Y"
        assert structure.date_column == 0

    def test_sample_values_populated(self, sample_csv: Path):
        """Sample values are populated for each column."""
        structure = detect_structure(sample_csv, max_sample=3)
        for col in structure.columns:
            assert len(col.sample_values) <= 3
            assert len(col.sample_values) > 0

    def test_header_matching_case_insensitive(
        self, tmp_path: Path
    ):
        """Headers are matched case-insensitively."""
        csv_file = tmp_path / "upper.csv"
        csv_file.write_text(
            "DATE,DESCRIPTION,AMOUNT\n"
            "2026-01-15,Test,-10.00\n"
        )
        structure = detect_structure(csv_file)
        assert structure.date_column == 0
        assert structure.description_column == 1
        assert structure.amount_column == 2


# -----------------------------------------------------------------------
# generate_rules tests
# -----------------------------------------------------------------------


class TestGenerateRules:
    def test_creates_valid_rules_file(self, tmp_path: Path):
        """Rules file is written with correct fields."""
        structure = CSVStructure(
            columns=[
                CSVColumn(0, "Date", []),
                CSVColumn(1, "Description", []),
                CSVColumn(2, "Amount", []),
            ],
            date_column=0,
            description_column=1,
            amount_column=2,
            date_format="%Y-%m-%d",
            skip_lines=1,
            delimiter=",",
        )
        output = tmp_path / "test.rules"
        result = generate_rules(
            structure, "assets:bank:checking", output
        )
        assert result == output
        assert output.exists()

        content = output.read_text()
        assert "skip 1" in content
        assert "fields date, description, amount" in content
        assert "date-format %Y-%m-%d" in content
        assert "account1 assets:bank:checking" in content
        assert "currency $" in content

    def test_empty_header_gets_field_name(self, tmp_path: Path):
        """Columns with empty headers get field0, field1, etc."""
        structure = CSVStructure(
            columns=[
                CSVColumn(0, "", []),
                CSVColumn(1, "Desc", []),
            ],
            date_column=0,
            description_column=1,
        )
        output = tmp_path / "empty.rules"
        generate_rules(structure, "assets:cash", output)
        content = output.read_text()
        assert "field0" in content

    def test_special_chars_sanitized(self, tmp_path: Path):
        """Special characters in headers are sanitized."""
        structure = CSVStructure(
            columns=[
                CSVColumn(0, "Date/Time", []),
                CSVColumn(1, "Desc (memo)", []),
            ],
        )
        output = tmp_path / "special.rules"
        generate_rules(structure, "assets:bank", output)
        content = output.read_text()
        # Should not contain parens or slashes in field names
        assert "date_time" in content
        assert "desc__memo_" in content


# -----------------------------------------------------------------------
# parse_csv_rows tests
# -----------------------------------------------------------------------


class TestParseCsvRows:
    def test_reads_data_correctly(self, sample_csv: Path):
        """Parsed rows have correct date, description, amount."""
        structure = detect_structure(sample_csv)
        rows = parse_csv_rows(sample_csv, structure)

        assert len(rows) == 5
        assert rows[0]["date"] == "2026-01-15"
        assert rows[0]["description"] == "Whole Foods"
        assert rows[0]["amount"] == "-85.42"
        assert rows[0]["balance"] == "1914.58"

    def test_skips_header(self, sample_csv: Path):
        """The header row is skipped (not included in data)."""
        structure = detect_structure(sample_csv)
        rows = parse_csv_rows(sample_csv, structure)
        # First row should be data, not header
        assert rows[0]["description"] != "Description"

    def test_skips_empty_rows(self, tmp_path: Path):
        """Empty/blank rows in the CSV are skipped."""
        csv_file = tmp_path / "blanks.csv"
        csv_file.write_text(
            "Date,Description,Amount\n"
            "2026-01-15,Test,-10.00\n"
            "\n"
            ",,\n"
            "2026-01-16,Test2,-20.00\n"
        )
        structure = detect_structure(csv_file)
        rows = parse_csv_rows(csv_file, structure)
        assert len(rows) == 2

    def test_handles_missing_columns_gracefully(
        self, tmp_path: Path
    ):
        """Rows with fewer columns than expected are handled."""
        csv_file = tmp_path / "short.csv"
        csv_file.write_text(
            "Date,Description,Amount,Balance\n"
            "2026-01-15,Test\n"  # Missing amount and balance
        )
        structure = detect_structure(csv_file)
        rows = parse_csv_rows(csv_file, structure)
        assert len(rows) == 1
        assert rows[0]["date"] == "2026-01-15"
        assert rows[0]["description"] == "Test"
        assert "amount" not in rows[0]
