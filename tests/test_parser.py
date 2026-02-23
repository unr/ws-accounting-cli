"""Tests for hledger JSON parser."""

from datetime import date
from decimal import Decimal

from ws_accounting.core.models import TransactionStatus
from ws_accounting.core.parser import (
    normalize_sign,
    parse_amount,
    parse_amounts,
    parse_register,
)


class TestParseAmount:
    def test_basic_amount(self) -> None:
        data = {
            "acommodity": "$",
            "aquantity": {
                "decimalMantissa": 5042,
                "decimalPlaces": 2,
            },
        }
        amt = parse_amount(data)
        assert amt.quantity == Decimal("50.42")
        assert amt.commodity == "$"

    def test_zero_decimal_places(self) -> None:
        data = {
            "acommodity": "EUR",
            "aquantity": {
                "decimalMantissa": 100,
                "decimalPlaces": 0,
            },
        }
        amt = parse_amount(data)
        assert amt.quantity == Decimal("100")
        assert amt.commodity == "EUR"

    def test_negative_amount(self) -> None:
        data = {
            "acommodity": "$",
            "aquantity": {
                "decimalMantissa": -8542,
                "decimalPlaces": 2,
            },
        }
        amt = parse_amount(data)
        assert amt.quantity == Decimal("-85.42")

    def test_string_quantity(self) -> None:
        data = {
            "acommodity": "$",
            "aquantity": "42.50",
        }
        amt = parse_amount(data)
        assert amt.quantity == Decimal("42.50")

    def test_int_quantity(self) -> None:
        data = {
            "acommodity": "$",
            "aquantity": 100,
        }
        amt = parse_amount(data)
        assert amt.quantity == Decimal("100")

    def test_missing_fields_defaults(self) -> None:
        amt = parse_amount({})
        assert amt.quantity == Decimal("0")
        assert amt.commodity == "$"


class TestParseAmounts:
    def test_empty_list(self) -> None:
        assert parse_amounts([]) is None

    def test_single_amount(self) -> None:
        data = [{
            "acommodity": "$",
            "aquantity": {
                "decimalMantissa": 1000,
                "decimalPlaces": 2,
            },
        }]
        amt = parse_amounts(data)
        assert amt is not None
        assert amt.quantity == Decimal("10.00")

    def test_multiple_amounts_uses_first(self) -> None:
        data = [
            {
                "acommodity": "$",
                "aquantity": {
                    "decimalMantissa": 1000,
                    "decimalPlaces": 2,
                },
            },
            {
                "acommodity": "EUR",
                "aquantity": {
                    "decimalMantissa": 2000,
                    "decimalPlaces": 2,
                },
            },
        ]
        amt = parse_amounts(data)
        assert amt is not None
        assert amt.commodity == "$"
        assert amt.quantity == Decimal("10.00")


class TestNormalizeSign:
    def test_income_negated(self) -> None:
        result = normalize_sign(Decimal("-500"), "income:salary")
        assert result == Decimal("500")

    def test_liabilities_negated(self) -> None:
        result = normalize_sign(
            Decimal("-1000"), "liabilities:credit"
        )
        assert result == Decimal("1000")

    def test_assets_unchanged(self) -> None:
        result = normalize_sign(
            Decimal("5000"), "assets:bank:checking"
        )
        assert result == Decimal("5000")

    def test_expenses_unchanged(self) -> None:
        result = normalize_sign(
            Decimal("85"), "expenses:food:groceries"
        )
        assert result == Decimal("85")

    def test_equity_unchanged(self) -> None:
        result = normalize_sign(
            Decimal("10000"), "equity:opening"
        )
        assert result == Decimal("10000")


class TestParseRegister:
    SAMPLE_REGISTER_JSON = [
        {
            "tdate": "2026-01-15",
            "tdate2": "",
            "tstatus": "Cleared",
            "tdescription": "Employer | Salary",
            "tpostings": [
                {
                    "paccount": "assets:bank:checking",
                    "pamount": [{
                        "acommodity": "$",
                        "aquantity": {
                            "decimalMantissa": 500000,
                            "decimalPlaces": 2,
                        },
                    }],
                    "pcomment": "",
                    "pbalanceassertion": None,
                },
                {
                    "paccount": "income:salary",
                    "pamount": [{
                        "acommodity": "$",
                        "aquantity": {
                            "decimalMantissa": -500000,
                            "decimalPlaces": 2,
                        },
                    }],
                    "pcomment": "monthly pay",
                    "pbalanceassertion": None,
                },
            ],
            "ttags": [["year", "2026"]],
            "tcomment": "regular income",
            "tsourcepos": [
                {
                    "sourceName": "test.journal",
                    "sourceLine": 7,
                }
            ],
        },
        {
            "tdate": "2026-01-16",
            "tdate2": "",
            "tstatus": "Pending",
            "tdescription": "Whole Foods",
            "tpostings": [
                {
                    "paccount": "expenses:food:groceries",
                    "pamount": [{
                        "acommodity": "$",
                        "aquantity": {
                            "decimalMantissa": 8542,
                            "decimalPlaces": 2,
                        },
                    }],
                    "pcomment": "",
                    "pbalanceassertion": None,
                },
                {
                    "paccount": "assets:bank:checking",
                    "pamount": [{
                        "acommodity": "$",
                        "aquantity": {
                            "decimalMantissa": -8542,
                            "decimalPlaces": 2,
                        },
                    }],
                    "pcomment": "",
                    "pbalanceassertion": None,
                },
            ],
            "ttags": [],
            "tcomment": "",
            "tsourcepos": [
                {
                    "sourceName": "test.journal",
                    "sourceLine": 12,
                }
            ],
        },
    ]

    def test_parses_two_transactions(self) -> None:
        txns = parse_register(self.SAMPLE_REGISTER_JSON)
        assert len(txns) == 2

    def test_first_transaction_fields(self) -> None:
        txns = parse_register(self.SAMPLE_REGISTER_JSON)
        txn = txns[0]
        assert txn.date == date(2026, 1, 15)
        assert txn.status == TransactionStatus.CLEARED
        assert txn.payee == "Employer"
        assert txn.description == "Salary"
        assert txn.comment == "regular income"
        assert txn.tags == {"year": "2026"}
        assert txn.source_file == "test.journal"
        assert txn.source_line == 7

    def test_first_transaction_postings(self) -> None:
        txns = parse_register(self.SAMPLE_REGISTER_JSON)
        postings = txns[0].postings
        assert len(postings) == 2
        assert postings[0].account == "assets:bank:checking"
        assert postings[0].amount is not None
        assert postings[0].amount.quantity == Decimal("5000.00")
        assert postings[0].amount.commodity == "$"
        assert postings[1].comment == "monthly pay"

    def test_second_transaction_status(self) -> None:
        txns = parse_register(self.SAMPLE_REGISTER_JSON)
        assert txns[1].status == TransactionStatus.PENDING

    def test_unmarked_status(self) -> None:
        data = [{
            "tdate": "2026-02-01",
            "tdate2": "",
            "tstatus": "",
            "tdescription": "Test",
            "tpostings": [],
            "ttags": [],
            "tcomment": "",
            "tsourcepos": [],
        }]
        txns = parse_register(data)
        assert txns[0].status == TransactionStatus.UNMARKED

    def test_no_payee_separator(self) -> None:
        txns = parse_register(self.SAMPLE_REGISTER_JSON)
        # Second transaction has no "|" so no payee
        assert txns[1].payee is None
        assert txns[1].description == "Whole Foods"

    def test_balance_assertion_parsing(self) -> None:
        data = [{
            "tdate": "2026-01-20",
            "tdate2": "",
            "tstatus": "Cleared",
            "tdescription": "Balance check",
            "tpostings": [{
                "paccount": "assets:bank",
                "pamount": [{
                    "acommodity": "$",
                    "aquantity": {
                        "decimalMantissa": 0,
                        "decimalPlaces": 2,
                    },
                }],
                "pcomment": "",
                "pbalanceassertion": {
                    "baamount": {
                        "acommodity": "$",
                        "aquantity": {
                            "decimalMantissa": 123456,
                            "decimalPlaces": 2,
                        },
                    },
                },
            }],
            "ttags": [],
            "tcomment": "",
            "tsourcepos": [],
        }]
        txns = parse_register(data)
        posting = txns[0].postings[0]
        assert posting.balance_assertion is not None
        assert posting.balance_assertion.quantity == Decimal("1234.56")
        assert posting.balance_assertion.commodity == "$"

    def test_empty_sourcepos(self) -> None:
        data = [{
            "tdate": "2026-01-20",
            "tdate2": "",
            "tstatus": "",
            "tdescription": "Test",
            "tpostings": [],
            "ttags": [],
            "tcomment": "",
            "tsourcepos": [],
        }]
        txns = parse_register(data)
        assert txns[0].source_file is None
        assert txns[0].source_line is None

    def test_date2_parsing(self) -> None:
        data = [{
            "tdate": "2026-01-15",
            "tdate2": "2026-01-20",
            "tstatus": "",
            "tdescription": "Effective date test",
            "tpostings": [],
            "ttags": [],
            "tcomment": "",
            "tsourcepos": [],
        }]
        txns = parse_register(data)
        assert txns[0].date2 == date(2026, 1, 20)
