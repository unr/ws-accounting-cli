"""Tests for domain models."""

from datetime import date
from decimal import Decimal

import pytest

from ws_accounting.core.models import (
    Amount,
    CategorizedTransaction,
    Posting,
    Transaction,
    TransactionStatus,
)


class TestTransactionStatus:
    def test_unmarked_value(self) -> None:
        assert TransactionStatus.UNMARKED.value == ""

    def test_pending_value(self) -> None:
        assert TransactionStatus.PENDING.value == "!"

    def test_cleared_value(self) -> None:
        assert TransactionStatus.CLEARED.value == "*"

    def test_all_members(self) -> None:
        assert set(TransactionStatus) == {
            TransactionStatus.UNMARKED,
            TransactionStatus.PENDING,
            TransactionStatus.CLEARED,
        }


class TestAmountStr:
    def test_positive_dollar(self) -> None:
        amt = Amount(Decimal("1234.56"), "$")
        assert str(amt) == "$1,234.56"

    def test_negative_dollar(self) -> None:
        amt = Amount(Decimal("-50.00"), "$")
        assert str(amt) == "-$50.00"

    def test_zero_dollar(self) -> None:
        amt = Amount(Decimal("0.00"), "$")
        assert str(amt) == "$0.00"

    def test_large_dollar(self) -> None:
        amt = Amount(Decimal("1000000.00"), "$")
        assert str(amt) == "$1,000,000.00"

    def test_non_dollar_commodity(self) -> None:
        amt = Amount(Decimal("99.99"), "EUR")
        assert str(amt) == "99.99 EUR"

    def test_negative_non_dollar(self) -> None:
        amt = Amount(Decimal("-42"), "BTC")
        assert str(amt) == "-42 BTC"


class TestAmountNeg:
    def test_negate_positive(self) -> None:
        amt = Amount(Decimal("100.00"), "$")
        result = -amt
        assert result.quantity == Decimal("-100.00")
        assert result.commodity == "$"

    def test_negate_negative(self) -> None:
        amt = Amount(Decimal("-50.00"), "$")
        result = -amt
        assert result.quantity == Decimal("50.00")
        assert result.commodity == "$"

    def test_negate_zero(self) -> None:
        amt = Amount(Decimal("0"), "$")
        result = -amt
        assert result.quantity == Decimal("0")

    def test_negate_preserves_commodity(self) -> None:
        amt = Amount(Decimal("10"), "EUR")
        result = -amt
        assert result.commodity == "EUR"


class TestAmountAdd:
    def test_add_same_commodity(self) -> None:
        a = Amount(Decimal("100.00"), "$")
        b = Amount(Decimal("50.00"), "$")
        result = a + b
        assert result.quantity == Decimal("150.00")
        assert result.commodity == "$"

    def test_add_negative(self) -> None:
        a = Amount(Decimal("100.00"), "$")
        b = Amount(Decimal("-30.00"), "$")
        result = a + b
        assert result.quantity == Decimal("70.00")

    def test_add_to_zero(self) -> None:
        a = Amount(Decimal("50.00"), "$")
        b = Amount(Decimal("-50.00"), "$")
        result = a + b
        assert result.quantity == Decimal("0.00")

    def test_add_mismatched_commodity_raises(self) -> None:
        a = Amount(Decimal("100"), "$")
        b = Amount(Decimal("100"), "EUR")
        with pytest.raises(ValueError, match="Cannot add \\$ and EUR"):
            a + b


class TestAmountBasics:
    def test_creation(self) -> None:
        amt = Amount(quantity=Decimal("42.50"), commodity="$")
        assert amt.quantity == Decimal("42.50")
        assert amt.commodity == "$"

    def test_frozen(self) -> None:
        amt = Amount(quantity=Decimal("10"), commodity="EUR")
        with pytest.raises(AttributeError):
            amt.quantity = Decimal("20")  # type: ignore[misc]

    def test_equality(self) -> None:
        a = Amount(Decimal("100.00"), "$")
        b = Amount(Decimal("100.00"), "$")
        assert a == b

    def test_different_commodity_not_equal(self) -> None:
        a = Amount(Decimal("100"), "$")
        b = Amount(Decimal("100"), "EUR")
        assert a != b


class TestTransactionValidate:
    def _make_txn(self, postings: tuple[Posting, ...]) -> Transaction:
        return Transaction(
            date=date(2026, 1, 15),
            description="Test",
            postings=postings,
            status=TransactionStatus.CLEARED,
        )

    def test_balanced_transaction_passes(self) -> None:
        txn = self._make_txn((
            Posting(
                account="expenses:food",
                amount=Amount(Decimal("50.00"), "$"),
            ),
            Posting(
                account="assets:bank",
                amount=Amount(Decimal("-50.00"), "$"),
            ),
        ))
        txn.validate()  # Should not raise

    def test_unbalanced_transaction_fails(self) -> None:
        txn = self._make_txn((
            Posting(
                account="expenses:food",
                amount=Amount(Decimal("50.00"), "$"),
            ),
            Posting(
                account="assets:bank",
                amount=Amount(Decimal("-30.00"), "$"),
            ),
        ))
        with pytest.raises(ValueError, match="does not balance"):
            txn.validate()

    def test_multiple_none_amounts_fails(self) -> None:
        txn = self._make_txn((
            Posting(account="expenses:food", amount=None),
            Posting(account="assets:bank", amount=None),
        ))
        with pytest.raises(ValueError, match="At most one posting"):
            txn.validate()

    def test_single_none_amount_passes(self) -> None:
        txn = self._make_txn((
            Posting(
                account="expenses:food",
                amount=Amount(Decimal("50.00"), "$"),
            ),
            Posting(account="assets:bank", amount=None),
        ))
        txn.validate()  # Should not raise

    def test_multi_commodity_balanced(self) -> None:
        txn = self._make_txn((
            Posting(
                account="expenses:food",
                amount=Amount(Decimal("50.00"), "$"),
            ),
            Posting(
                account="expenses:travel",
                amount=Amount(Decimal("100.00"), "EUR"),
            ),
            Posting(
                account="assets:bank:usd",
                amount=Amount(Decimal("-50.00"), "$"),
            ),
            Posting(
                account="assets:bank:eur",
                amount=Amount(Decimal("-100.00"), "EUR"),
            ),
        ))
        txn.validate()  # Should not raise

    def test_multi_commodity_unbalanced(self) -> None:
        txn = self._make_txn((
            Posting(
                account="expenses:food",
                amount=Amount(Decimal("50.00"), "$"),
            ),
            Posting(
                account="expenses:travel",
                amount=Amount(Decimal("100.00"), "EUR"),
            ),
            Posting(
                account="assets:bank:usd",
                amount=Amount(Decimal("-50.00"), "$"),
            ),
            Posting(
                account="assets:bank:eur",
                amount=Amount(Decimal("-90.00"), "EUR"),
            ),
        ))
        with pytest.raises(ValueError, match="EUR"):
            txn.validate()


class TestCategorizedTransaction:
    def test_creation(self) -> None:
        cat = CategorizedTransaction(
            original_description="WHOLE FOODS #123",
            suggested_account="expenses:food:groceries",
            confidence=0.92,
            reasoning="Pattern match on merchant name",
            alternatives=[
                "expenses:food:dining",
                "expenses:household",
            ],
        )
        assert cat.original_description == "WHOLE FOODS #123"
        assert cat.suggested_account == "expenses:food:groceries"
        assert cat.confidence == 0.92
        assert cat.reasoning == "Pattern match on merchant name"
        assert cat.alternatives is not None
        assert len(cat.alternatives) == 2

    def test_defaults(self) -> None:
        cat = CategorizedTransaction(
            original_description="desc",
            suggested_account="expenses:misc",
            confidence=0.5,
        )
        assert cat.reasoning is None
        assert cat.alternatives is None

    def test_frozen(self) -> None:
        cat = CategorizedTransaction(
            original_description="desc",
            suggested_account="expenses:misc",
            confidence=0.5,
        )
        with pytest.raises(AttributeError):
            cat.confidence = 0.9  # type: ignore[misc]
