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


class TestAmount:
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

    def test_different_commodity(self) -> None:
        a = Amount(Decimal("100"), "$")
        b = Amount(Decimal("100"), "EUR")
        assert a != b


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


class TestTransactionValidate:
    def _make_txn(
        self, postings: tuple[Posting, ...]
    ) -> Transaction:
        return Transaction(
            date=date(2026, 1, 15),
            status=TransactionStatus.CLEARED,
            description="Test",
            postings=postings,
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
        with pytest.raises(
            ValueError, match="At most one posting may omit amount"
        ):
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
        assert len(cat.alternatives) == 2

    def test_defaults(self) -> None:
        cat = CategorizedTransaction(
            original_description="desc",
            suggested_account="expenses:misc",
            confidence=0.5,
        )
        assert cat.reasoning is None
        assert cat.alternatives == []

    def test_frozen(self) -> None:
        cat = CategorizedTransaction(
            original_description="desc",
            suggested_account="expenses:misc",
            confidence=0.5,
        )
        with pytest.raises(AttributeError):
            cat.confidence = 0.9  # type: ignore[misc]
