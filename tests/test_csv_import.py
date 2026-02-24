"""Tests for CSV import: core functions and DB operations."""

from __future__ import annotations

import sqlite3
from decimal import Decimal
from pathlib import Path

import pytest

from ws_accounting.core.csv_import import (
    CSVStructure,
    DuplicateResult,
    TransferCandidate,
    check_duplicates,
    compute_import_hash,
    detect_structure,
    detect_transfers,
    parse_csv_rows,
)
from ws_accounting.db.queries import (
    check_import_hash,
    record_import,
    store_import_hash,
    store_import_hashes,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_csv(path: Path, content: str) -> Path:
    """Write CSV content to a file and return the path."""
    path.write_text(content)
    return path


# ---------------------------------------------------------------------------
# detect_structure tests
# ---------------------------------------------------------------------------


class TestDetectStructure:
    """Tests for detect_structure()."""

    def test_standard_headers(self, tmp_path: Path) -> None:
        """Detect standard Date/Description/Amount columns."""
        csv_file = _write_csv(
            tmp_path / "bank.csv",
            "Date,Description,Amount\n"
            "2026-01-15,Coffee Shop,-4.50\n",
        )
        structure = detect_structure(csv_file)
        assert structure.date_column == 0
        assert structure.description_column == 1
        assert structure.amount_column == 2
        assert structure.headers == ["Date", "Description", "Amount"]

    def test_headers_with_balance(self, tmp_path: Path) -> None:
        """Detect balance column when present."""
        csv_file = _write_csv(
            tmp_path / "bank.csv",
            "Date,Memo,Amount,Balance\n"
            "2026-01-15,Coffee,-4.50,995.50\n",
        )
        structure = detect_structure(csv_file)
        assert structure.date_column == 0
        assert structure.description_column == 1
        assert structure.amount_column == 2
        assert structure.balance_column == 3

    def test_alternate_header_names(self, tmp_path: Path) -> None:
        """Recognize alternate header names (posting date, payee, debit)."""
        csv_file = _write_csv(
            tmp_path / "bank.csv",
            "Posting Date,Payee,Debit\n"
            "2026-01-15,Store,10.00\n",
        )
        structure = detect_structure(csv_file)
        assert structure.date_column == 0
        assert structure.description_column == 1
        assert structure.amount_column == 2

    def test_unrecognized_headers_use_defaults(self, tmp_path: Path) -> None:
        """When headers are not recognized, fall back to defaults (0, 1, 2)."""
        csv_file = _write_csv(
            tmp_path / "bank.csv",
            "Col A,Col B,Col C\n"
            "2026-01-15,Coffee,-4.50\n",
        )
        structure = detect_structure(csv_file)
        # Defaults: date=0, description=1, amount=2
        assert structure.date_column == 0
        assert structure.description_column == 1
        assert structure.amount_column == 2
        assert structure.headers == ["Col A", "Col B", "Col C"]

    def test_headers_stored(self, tmp_path: Path) -> None:
        """Headers list is populated in the structure."""
        csv_file = _write_csv(
            tmp_path / "bank.csv",
            "Transaction Date,Name,Amount,Running Balance\n"
            "2026-01-15,Store,10.00,1010.00\n",
        )
        structure = detect_structure(csv_file)
        assert len(structure.headers) == 4
        assert structure.headers[0] == "Transaction Date"
        assert structure.headers[3] == "Running Balance"

    def test_delimiter_defaults_to_comma(self, tmp_path: Path) -> None:
        """Structure defaults to comma delimiter."""
        csv_file = _write_csv(
            tmp_path / "bank.csv",
            "Date,Description,Amount\n"
            "2026-01-15,Coffee,-4.50\n",
        )
        structure = detect_structure(csv_file)
        assert structure.delimiter == ","


# ---------------------------------------------------------------------------
# compute_import_hash tests
# ---------------------------------------------------------------------------


class TestComputeImportHash:
    """Tests for compute_import_hash()."""

    def test_stable_output(self) -> None:
        """Same inputs always produce the same hash."""
        h1 = compute_import_hash("2026-01-15", "Coffee Shop", "-4.50")
        h2 = compute_import_hash("2026-01-15", "Coffee Shop", "-4.50")
        assert h1 == h2

    def test_different_inputs_different_hash(self) -> None:
        """Different inputs produce different hashes."""
        h1 = compute_import_hash("2026-01-15", "Coffee Shop", "-4.50")
        h2 = compute_import_hash("2026-01-15", "Tea Shop", "-4.50")
        assert h1 != h2

    def test_hash_length(self) -> None:
        """Hash is truncated to 16 characters."""
        h = compute_import_hash("2026-01-15", "Coffee", "10.00")
        assert len(h) == 16

    def test_whitespace_handling(self) -> None:
        """Leading/trailing whitespace in description and amount is stripped."""
        h1 = compute_import_hash("2026-01-15", "  Coffee  ", " -4.50 ")
        h2 = compute_import_hash("2026-01-15", "Coffee", "-4.50")
        assert h1 == h2


# ---------------------------------------------------------------------------
# check_duplicates tests
# ---------------------------------------------------------------------------


class TestCheckDuplicates:
    """Tests for check_duplicates()."""

    def test_no_duplicates(self) -> None:
        """All rows are new when existing_hashes is empty."""
        rows = [
            {"date": "2026-01-15", "description": "Coffee", "amount": "-4.50"},
            {"date": "2026-01-16", "description": "Lunch", "amount": "-12.00"},
        ]
        results = check_duplicates(rows, set())
        assert len(results) == 2
        assert all(not r.is_duplicate for r in results)

    def test_with_duplicates(self) -> None:
        """Rows matching existing hashes are flagged as duplicates."""
        rows = [
            {"date": "2026-01-15", "description": "Coffee", "amount": "-4.50"},
            {"date": "2026-01-16", "description": "Lunch", "amount": "-12.00"},
        ]
        # Pre-compute hash for the first row
        existing = {compute_import_hash("2026-01-15", "Coffee", "-4.50")}
        results = check_duplicates(rows, existing)
        assert results[0].is_duplicate is True
        assert results[1].is_duplicate is False

    def test_result_order_matches_input(self) -> None:
        """Results are returned in the same order as input rows."""
        rows = [
            {"date": "2026-01-15", "description": "A", "amount": "1"},
            {"date": "2026-01-16", "description": "B", "amount": "2"},
            {"date": "2026-01-17", "description": "C", "amount": "3"},
        ]
        existing = {compute_import_hash("2026-01-16", "B", "2")}
        results = check_duplicates(rows, existing)
        assert results[0].is_duplicate is False
        assert results[1].is_duplicate is True
        assert results[2].is_duplicate is False

    def test_result_has_hash(self) -> None:
        """Each result contains the computed hash."""
        rows = [
            {"date": "2026-01-15", "description": "Coffee", "amount": "-4.50"},
        ]
        results = check_duplicates(rows, set())
        expected_hash = compute_import_hash("2026-01-15", "Coffee", "-4.50")
        assert results[0].hash == expected_hash

    def test_all_duplicates(self) -> None:
        """All rows flagged when all hashes are in existing set."""
        rows = [
            {"date": "2026-01-15", "description": "Coffee", "amount": "-4.50"},
            {"date": "2026-01-16", "description": "Lunch", "amount": "-12.00"},
        ]
        existing = {
            compute_import_hash("2026-01-15", "Coffee", "-4.50"),
            compute_import_hash("2026-01-16", "Lunch", "-12.00"),
        }
        results = check_duplicates(rows, existing)
        assert all(r.is_duplicate for r in results)


# ---------------------------------------------------------------------------
# detect_transfers tests
# ---------------------------------------------------------------------------


class TestDetectTransfers:
    """Tests for detect_transfers()."""

    def test_matching_amounts(self) -> None:
        """Detect a transfer when amounts sum to zero."""
        rows = [
            {"date": "2026-01-15", "description": "Transfer Out", "amount": "-500.00"},
            {"date": "2026-01-15", "description": "Transfer In", "amount": "500.00"},
        ]
        candidates = detect_transfers(rows)
        assert len(candidates) == 1
        assert candidates[0].from_idx == 0
        assert candidates[0].to_idx == 1
        assert candidates[0].amount == Decimal("500.00")

    def test_no_matching_amounts(self) -> None:
        """No transfers when amounts don't cancel out."""
        rows = [
            {"date": "2026-01-15", "description": "Coffee", "amount": "-4.50"},
            {"date": "2026-01-16", "description": "Lunch", "amount": "-12.00"},
        ]
        candidates = detect_transfers(rows)
        assert len(candidates) == 0

    def test_multiple_transfer_pairs(self) -> None:
        """Detect multiple transfer pairs."""
        rows = [
            {"date": "2026-01-15", "description": "Xfer Out 1", "amount": "-100.00"},
            {"date": "2026-01-15", "description": "Xfer In 1", "amount": "100.00"},
            {"date": "2026-01-16", "description": "Xfer Out 2", "amount": "-200.00"},
            {"date": "2026-01-16", "description": "Xfer In 2", "amount": "200.00"},
        ]
        candidates = detect_transfers(rows)
        assert len(candidates) == 2

    def test_transfer_candidate_fields(self) -> None:
        """TransferCandidate has correct field names."""
        rows = [
            {"date": "2026-01-15", "description": "Out", "amount": "-50.00"},
            {"date": "2026-01-15", "description": "In", "amount": "50.00"},
        ]
        candidates = detect_transfers(rows)
        tc = candidates[0]
        assert hasattr(tc, "from_idx")
        assert hasattr(tc, "to_idx")
        assert hasattr(tc, "amount")
        assert hasattr(tc, "days_apart")

    def test_bad_amounts_skipped(self) -> None:
        """Rows with non-numeric amounts are skipped."""
        rows = [
            {"date": "2026-01-15", "description": "Bad", "amount": "not-a-number"},
            {"date": "2026-01-15", "description": "Good", "amount": "50.00"},
        ]
        candidates = detect_transfers(rows)
        assert len(candidates) == 0


# ---------------------------------------------------------------------------
# parse_csv_rows tests
# ---------------------------------------------------------------------------


class TestParseCsvRows:
    """Tests for parse_csv_rows()."""

    def test_basic_parsing(self, tmp_path: Path) -> None:
        """Parse a simple CSV with default structure."""
        csv_file = _write_csv(
            tmp_path / "bank.csv",
            "Date,Description,Amount\n"
            "2026-01-15,Coffee Shop,-4.50\n"
            "2026-01-16,Grocery Store,-52.30\n",
        )
        structure = detect_structure(csv_file)
        rows = parse_csv_rows(csv_file, structure)
        assert len(rows) == 2
        assert rows[0]["date"] == "2026-01-15"
        assert rows[0]["description"] == "Coffee Shop"
        assert rows[0]["amount"] == "-4.50"
        assert rows[1]["date"] == "2026-01-16"

    def test_skip_header_row(self, tmp_path: Path) -> None:
        """Default skip_rows=1 skips the header."""
        csv_file = _write_csv(
            tmp_path / "bank.csv",
            "Date,Description,Amount\n"
            "2026-01-15,Coffee,-4.50\n",
        )
        structure = CSVStructure(
            headers=["Date", "Description", "Amount"],
            skip_rows=1,
        )
        rows = parse_csv_rows(csv_file, structure)
        assert len(rows) == 1
        assert rows[0]["date"] == "2026-01-15"

    def test_skip_empty_rows(self, tmp_path: Path) -> None:
        """Empty rows in the CSV are skipped."""
        csv_file = _write_csv(
            tmp_path / "bank.csv",
            "Date,Description,Amount\n"
            "2026-01-15,Coffee,-4.50\n"
            "\n"
            "2026-01-16,Lunch,-12.00\n",
        )
        structure = detect_structure(csv_file)
        rows = parse_csv_rows(csv_file, structure)
        assert len(rows) == 2

    def test_custom_column_mapping(self, tmp_path: Path) -> None:
        """Use custom column indices for non-standard CSV layouts."""
        csv_file = _write_csv(
            tmp_path / "bank.csv",
            "ID,Amount,Name,Date\n"
            "1,-4.50,Coffee,2026-01-15\n",
        )
        structure = CSVStructure(
            date_column=3,
            description_column=2,
            amount_column=1,
            headers=["ID", "Amount", "Name", "Date"],
            skip_rows=1,
        )
        rows = parse_csv_rows(csv_file, structure)
        assert len(rows) == 1
        assert rows[0]["date"] == "2026-01-15"
        assert rows[0]["description"] == "Coffee"
        assert rows[0]["amount"] == "-4.50"

    def test_balance_column(self, tmp_path: Path) -> None:
        """Parse balance column when configured."""
        csv_file = _write_csv(
            tmp_path / "bank.csv",
            "Date,Description,Amount,Balance\n"
            "2026-01-15,Coffee,-4.50,995.50\n",
        )
        structure = detect_structure(csv_file)
        rows = parse_csv_rows(csv_file, structure)
        assert len(rows) == 1
        assert rows[0]["balance"] == "995.50"

    def test_many_rows(self, tmp_path: Path) -> None:
        """Parse a CSV with many rows."""
        lines = ["Date,Description,Amount\n"]
        for i in range(100):
            lines.append(f"2026-01-{(i % 28) + 1:02d},Item {i},{i * 1.5:.2f}\n")
        csv_file = _write_csv(tmp_path / "bank.csv", "".join(lines))
        structure = detect_structure(csv_file)
        rows = parse_csv_rows(csv_file, structure)
        assert len(rows) == 100


# ---------------------------------------------------------------------------
# DB: record_import tests
# ---------------------------------------------------------------------------


class TestRecordImport:
    """Tests for record_import()."""

    def test_creates_import_record(self, in_memory_db: sqlite3.Connection) -> None:
        """record_import inserts a row and returns ImportHistory."""
        history = record_import(
            in_memory_db,
            csv_filename="bank_export.csv",
            profile_id=None,
            txn_count=25,
            duplicate_count=3,
        )
        assert history.id is not None
        assert history.file_path == "bank_export.csv"
        assert history.imported_count == 25
        assert history.duplicate_count == 3
        assert history.imported_at is not None

    def test_with_profile_id(self, in_memory_db: sqlite3.Connection) -> None:
        """record_import can store a profile_id reference."""
        # First create a profile to reference
        in_memory_db.execute(
            "INSERT INTO import_profiles (name, account) VALUES (?, ?)",
            ("Chase Checking", "assets:checking"),
        )
        in_memory_db.commit()
        profile_row = in_memory_db.execute(
            "SELECT id FROM import_profiles LIMIT 1"
        ).fetchone()
        profile_id = profile_row["id"]

        history = record_import(
            in_memory_db,
            csv_filename="chase.csv",
            profile_id=profile_id,
            txn_count=10,
            duplicate_count=0,
        )
        assert history.profile_id == profile_id

    def test_multiple_imports(self, in_memory_db: sqlite3.Connection) -> None:
        """Multiple imports produce distinct records."""
        h1 = record_import(in_memory_db, "file1.csv", txn_count=5, duplicate_count=0)
        h2 = record_import(in_memory_db, "file2.csv", txn_count=10, duplicate_count=2)
        assert h1.id != h2.id
        assert h1.file_path == "file1.csv"
        assert h2.file_path == "file2.csv"


# ---------------------------------------------------------------------------
# DB: store_import_hashes tests
# ---------------------------------------------------------------------------


class TestStoreImportHashes:
    """Tests for store_import_hashes()."""

    def test_bulk_insert(self, in_memory_db: sqlite3.Connection) -> None:
        """store_import_hashes inserts multiple hashes."""
        hashes = ["aaa111", "bbb222", "ccc333"]
        store_import_hashes(in_memory_db, hashes, "test.csv")
        count = in_memory_db.execute(
            "SELECT COUNT(*) FROM import_hashes"
        ).fetchone()[0]
        assert count == 3

    def test_hashes_are_queryable(self, in_memory_db: sqlite3.Connection) -> None:
        """Stored hashes can be found via check_import_hash."""
        hashes = ["hash_a", "hash_b"]
        store_import_hashes(in_memory_db, hashes, "source.csv")
        assert check_import_hash(in_memory_db, "hash_a") is True
        assert check_import_hash(in_memory_db, "hash_b") is True
        assert check_import_hash(in_memory_db, "hash_c") is False

    def test_duplicate_hashes_ignored(self, in_memory_db: sqlite3.Connection) -> None:
        """Inserting the same hash twice does not raise an error."""
        store_import_hashes(in_memory_db, ["dup_hash"], "file1.csv")
        store_import_hashes(in_memory_db, ["dup_hash"], "file2.csv")
        count = in_memory_db.execute(
            "SELECT COUNT(*) FROM import_hashes WHERE hash = 'dup_hash'"
        ).fetchone()[0]
        assert count == 1

    def test_source_stored(self, in_memory_db: sqlite3.Connection) -> None:
        """Source file is stored alongside the hash."""
        store_import_hashes(in_memory_db, ["src_hash"], "my_bank.csv")
        row = in_memory_db.execute(
            "SELECT source_file FROM import_hashes WHERE hash = 'src_hash'"
        ).fetchone()
        assert row["source_file"] == "my_bank.csv"

    def test_empty_hash_list(self, in_memory_db: sqlite3.Connection) -> None:
        """Calling with an empty list does not error."""
        store_import_hashes(in_memory_db, [], "empty.csv")
        count = in_memory_db.execute(
            "SELECT COUNT(*) FROM import_hashes"
        ).fetchone()[0]
        assert count == 0

    def test_int_source_converted_to_string(self, in_memory_db: sqlite3.Connection) -> None:
        """Source can be an int (import history id) and is stored as string."""
        store_import_hashes(in_memory_db, ["int_src"], 42)
        row = in_memory_db.execute(
            "SELECT source_file FROM import_hashes WHERE hash = 'int_src'"
        ).fetchone()
        assert row["source_file"] == "42"


# ---------------------------------------------------------------------------
# DB: check_import_hash tests
# ---------------------------------------------------------------------------


class TestCheckImportHash:
    """Tests for check_import_hash()."""

    def test_hash_not_found(self, in_memory_db: sqlite3.Connection) -> None:
        """Returns False when hash does not exist."""
        assert check_import_hash(in_memory_db, "nonexistent") is False

    def test_hash_found(self, in_memory_db: sqlite3.Connection) -> None:
        """Returns True when hash exists."""
        store_import_hash(in_memory_db, "found_hash", "test.csv")
        assert check_import_hash(in_memory_db, "found_hash") is True

    def test_accepts_database_object(self) -> None:
        """check_import_hash works with a Database wrapper object."""
        from ws_accounting.db.database import Database

        db = Database(":memory:")
        db.migrate()
        try:
            assert check_import_hash(db, "missing") is False
            conn = db.connect()
            conn.execute(
                "INSERT INTO import_hashes (hash, source_file) VALUES (?, ?)",
                ("db_hash", "test"),
            )
            conn.commit()
            assert check_import_hash(db, "db_hash") is True
        finally:
            db.close()


# ---------------------------------------------------------------------------
# Integration: end-to-end CSV to duplicates
# ---------------------------------------------------------------------------


class TestCSVImportIntegration:
    """Integration tests combining multiple CSV import functions."""

    def test_detect_parse_dedup_flow(self, tmp_path: Path) -> None:
        """Full flow: detect structure, parse rows, check duplicates."""
        csv_file = _write_csv(
            tmp_path / "bank.csv",
            "Date,Description,Amount\n"
            "2026-01-15,Coffee Shop,-4.50\n"
            "2026-01-16,Grocery Store,-52.30\n"
            "2026-01-17,Gas Station,-35.00\n",
        )

        # Step 1: detect
        structure = detect_structure(csv_file)
        assert structure.headers == ["Date", "Description", "Amount"]

        # Step 2: parse
        rows = parse_csv_rows(csv_file, structure)
        assert len(rows) == 3

        # Step 3: check duplicates (none existing)
        results = check_duplicates(rows, set())
        assert all(not r.is_duplicate for r in results)

        # Step 4: simulate re-import with first row already imported
        first_hash = compute_import_hash("2026-01-15", "Coffee Shop", "-4.50")
        results2 = check_duplicates(rows, {first_hash})
        assert results2[0].is_duplicate is True
        assert results2[1].is_duplicate is False
        assert results2[2].is_duplicate is False

    def test_transfer_detection_in_parsed_data(self, tmp_path: Path) -> None:
        """Detect transfers from parsed CSV data."""
        csv_file = _write_csv(
            tmp_path / "bank.csv",
            "Date,Description,Amount\n"
            "2026-01-15,Transfer to Savings,-1000.00\n"
            "2026-01-15,Transfer from Checking,1000.00\n"
            "2026-01-16,Coffee,-4.50\n",
        )
        structure = detect_structure(csv_file)
        rows = parse_csv_rows(csv_file, structure)
        transfers = detect_transfers(rows)
        assert len(transfers) == 1
        assert transfers[0].amount == Decimal("1000.00")
