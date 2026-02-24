"""Tests for reports-related utilities and DB queries (insights cache)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ws_accounting.core.models import Amount
from ws_accounting.core.parser import (
    AccountBalance,
    parse_amount,
    parse_balance_report,
)
from ws_accounting.db.database import Database
from ws_accounting.db.models import InsightsCacheEntry
from ws_accounting.db.queries import cache_insights, get_cached_insights
from ws_accounting.screens.reports import (
    _month_label,
    _month_range,
    _month_ranges_period,
)


# ---------------------------------------------------------------------------
# Database fixture using real migrations (returns Database object)
# ---------------------------------------------------------------------------


@pytest.fixture
def db(tmp_path):
    """Create a Database instance with real schema applied."""
    db_path = tmp_path / "test.db"
    database = Database(db_path)
    database.connect()
    database.migrate()
    return database


# ---------------------------------------------------------------------------
# InsightsCacheEntry model tests
# ---------------------------------------------------------------------------


class TestInsightsCacheEntry:
    def test_default_values(self):
        entry = InsightsCacheEntry()
        assert entry.content == ""
        assert entry.generated_at is None
        assert entry.period is None

    def test_with_values(self):
        entry = InsightsCacheEntry(
            content="Some insights",
            generated_at="2026-01-15 12:00:00",
            period="2026-01",
        )
        assert entry.content == "Some insights"
        assert entry.generated_at == "2026-01-15 12:00:00"
        assert entry.period == "2026-01"


# ---------------------------------------------------------------------------
# get_cached_insights / cache_insights tests
# ---------------------------------------------------------------------------


class TestInsightsCache:
    def test_get_cached_insights_returns_none_when_empty(self, db):
        result = get_cached_insights(db, "2026-01")
        assert result is None

    def test_cache_and_retrieve_insights(self, db):
        cache_insights(db, "2026-01", "Monthly analysis content", "claude")
        result = get_cached_insights(db, "2026-01")
        assert result is not None
        assert isinstance(result, InsightsCacheEntry)
        assert result.content == "Monthly analysis content"
        assert result.period == "2026-01"
        assert result.generated_at is not None

    def test_upsert_overwrites_same_period(self, db):
        cache_insights(db, "2026-01", "First version", "claude")
        cache_insights(db, "2026-01", "Updated version", "claude")
        result = get_cached_insights(db, "2026-01")
        assert result is not None
        assert result.content == "Updated version"

    def test_different_periods_stored_separately(self, db):
        cache_insights(db, "2026-01", "January insights", "claude")
        cache_insights(db, "2026-02", "February insights", "claude")

        jan = get_cached_insights(db, "2026-01")
        feb = get_cached_insights(db, "2026-02")

        assert jan is not None
        assert feb is not None
        assert jan.content == "January insights"
        assert feb.content == "February insights"

    def test_get_cached_insights_wrong_period_returns_none(self, db):
        cache_insights(db, "2026-01", "January", "claude")
        result = get_cached_insights(db, "2025-12")
        assert result is None

    def test_cache_insights_with_connection(self, db):
        """Test passing a raw connection instead of Database object."""
        conn = db.connect()
        cache_insights(conn, "2026-03", "March content", "claude")
        result = get_cached_insights(conn, "2026-03")
        assert result is not None
        assert result.content == "March content"

    def test_generated_at_is_populated(self, db):
        cache_insights(db, "2026-01", "Content", "claude")
        result = get_cached_insights(db, "2026-01")
        assert result is not None
        # generated_at should be a datetime string from SQLite
        assert result.generated_at is not None
        assert len(result.generated_at) > 0


# ---------------------------------------------------------------------------
# parse_balance_report tests
# ---------------------------------------------------------------------------


class TestParseBalanceReport:
    def test_parse_list_format(self):
        """Parse hledger balance JSON in list-of-lists format."""
        data = [
            [
                [
                    {
                        "acommodity": "$",
                        "aquantity": {
                            "decimalMantissa": 100050,
                            "decimalPlaces": 2,
                        },
                    }
                ],
                "assets:bank:checking",
            ],
            [
                [
                    {
                        "acommodity": "$",
                        "aquantity": {
                            "decimalMantissa": 8542,
                            "decimalPlaces": 2,
                        },
                    }
                ],
                "expenses:food:groceries",
            ],
        ]
        result = parse_balance_report(data)
        assert len(result) == 2
        assert isinstance(result[0], AccountBalance)
        assert result[0].account == "assets:bank:checking"
        assert result[0].balance.quantity == Decimal("1000.50")
        assert result[0].balance.commodity == "$"
        assert result[1].account == "expenses:food:groceries"
        assert result[1].balance.quantity == Decimal("85.42")

    def test_parse_dict_format(self):
        """Parse hledger balance JSON in dict-with-rows format."""
        data = {
            "rows": [
                {
                    "account": "assets:bank:checking",
                    "amounts": [
                        {
                            "acommodity": "$",
                            "aquantity": {
                                "decimalMantissa": 500000,
                                "decimalPlaces": 2,
                            },
                        }
                    ],
                },
                {
                    "account": "liabilities:credit",
                    "amounts": [
                        {
                            "acommodity": "$",
                            "aquantity": {
                                "decimalMantissa": -150000,
                                "decimalPlaces": 2,
                            },
                        }
                    ],
                },
            ]
        }
        result = parse_balance_report(data)
        assert len(result) == 2
        assert result[0].account == "assets:bank:checking"
        assert result[0].balance.quantity == Decimal("5000.00")
        assert result[1].account == "liabilities:credit"
        assert result[1].balance.quantity == Decimal("-1500.00")

    def test_parse_empty_list(self):
        result = parse_balance_report([])
        assert result == []

    def test_parse_empty_dict(self):
        result = parse_balance_report({})
        assert result == []

    def test_parse_list_with_empty_amounts(self):
        """When amounts list is empty, balance should be zero."""
        data = [[[], "assets:bank:checking"]]
        result = parse_balance_report(data)
        assert len(result) == 1
        assert result[0].balance.quantity == Decimal("0")

    def test_parse_dict_with_empty_amounts(self):
        data = {"rows": [{"account": "assets:bank", "amounts": []}]}
        result = parse_balance_report(data)
        assert len(result) == 1
        assert result[0].balance.quantity == Decimal("0")


# ---------------------------------------------------------------------------
# parse_amount tests
# ---------------------------------------------------------------------------


class TestParseAmount:
    def test_parse_mantissa_places(self):
        """Parse hledger JSON amount with decimalMantissa/decimalPlaces."""
        data = {
            "acommodity": "$",
            "aquantity": {
                "decimalMantissa": 12345,
                "decimalPlaces": 2,
            },
        }
        result = parse_amount(data)
        assert isinstance(result, Amount)
        assert result.quantity == Decimal("123.45")
        assert result.commodity == "$"

    def test_parse_zero_amount(self):
        data = {
            "acommodity": "$",
            "aquantity": {"decimalMantissa": 0, "decimalPlaces": 2},
        }
        result = parse_amount(data)
        assert result.quantity == Decimal("0")

    def test_parse_negative_amount(self):
        data = {
            "acommodity": "$",
            "aquantity": {"decimalMantissa": -50000, "decimalPlaces": 2},
        }
        result = parse_amount(data)
        assert result.quantity == Decimal("-500.00")

    def test_parse_integer_quantity(self):
        """Parse when aquantity is a plain number."""
        data = {
            "acommodity": "EUR",
            "aquantity": 42,
        }
        result = parse_amount(data)
        assert result.quantity == Decimal("42")
        assert result.commodity == "EUR"

    def test_parse_string_quantity(self):
        """Parse when aquantity is a string."""
        data = {
            "acommodity": "$",
            "aquantity": "99.99",
        }
        result = parse_amount(data)
        assert result.quantity == Decimal("99.99")

    def test_parse_no_places(self):
        """decimalPlaces defaults to 0."""
        data = {
            "acommodity": "$",
            "aquantity": {"decimalMantissa": 100},
        }
        result = parse_amount(data)
        assert result.quantity == Decimal("100")

    def test_parse_missing_commodity_defaults_to_dollar(self):
        data = {"aquantity": {"decimalMantissa": 1000, "decimalPlaces": 2}}
        result = parse_amount(data)
        assert result.commodity == "$"
        assert result.quantity == Decimal("10.00")

    def test_parse_empty_dict(self):
        """Empty dict yields zero amount."""
        result = parse_amount({})
        assert result.quantity == Decimal("0")
        assert result.commodity == "$"


# ---------------------------------------------------------------------------
# Reports helper function tests
# ---------------------------------------------------------------------------


class TestMonthLabel:
    def test_january(self):
        assert _month_label(2026, 1) == "Jan"

    def test_december(self):
        assert _month_label(2026, 12) == "Dec"

    def test_june(self):
        assert _month_label(2026, 6) == "Jun"


class TestMonthRange:
    def test_returns_correct_count(self):
        result = _month_range(6)
        assert len(result) == 6

    def test_last_element_is_current_month(self):
        result = _month_range(1)
        today = date.today()
        assert result[-1] == (today.year, today.month)

    def test_handles_year_boundary(self):
        result = _month_range(12)
        assert len(result) == 12
        # All tuples should have valid months (1-12)
        for year, month in result:
            assert 1 <= month <= 12

    def test_months_are_sequential(self):
        result = _month_range(6)
        for i in range(1, len(result)):
            prev_y, prev_m = result[i - 1]
            cur_y, cur_m = result[i]
            # Each month should be one after the previous
            expected_month = prev_m + 1
            expected_year = prev_y
            if expected_month > 12:
                expected_month = 1
                expected_year += 1
            assert (cur_y, cur_m) == (expected_year, expected_month)


class TestMonthRangesPeriod:
    def test_returns_monthly_period_string(self):
        result = _month_ranges_period(6)
        assert result.startswith("monthly from ")
        assert " to " in result

    def test_contains_iso_dates(self):
        result = _month_ranges_period(3)
        # Format: "monthly from YYYY-MM-DD to YYYY-MM-DD"
        parts = result.split()
        # parts: ['monthly', 'from', '<start>', 'to', '<end>']
        assert len(parts) == 5
        start_date = date.fromisoformat(parts[2])
        end_date = date.fromisoformat(parts[4])
        assert start_date < end_date
        # Both should be first of month
        assert start_date.day == 1
        assert end_date.day == 1

    def test_12_months_span(self):
        result = _month_ranges_period(12)
        parts = result.split()
        start_date = date.fromisoformat(parts[2])
        end_date = date.fromisoformat(parts[4])
        # Should span roughly 12 months
        diff_months = (
            (end_date.year - start_date.year) * 12
            + end_date.month
            - start_date.month
        )
        assert diff_months == 12
