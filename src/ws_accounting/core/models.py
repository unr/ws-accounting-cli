"""Domain models -- immutable dataclasses for all financial data."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum


class TransactionStatus(Enum):
    UNMARKED = ""
    PENDING = "!"
    CLEARED = "*"


@dataclass(frozen=True)
class Amount:
    quantity: Decimal
    commodity: str  # "$", "EUR", etc.

    def __str__(self) -> str:
        if self.commodity == "$":
            sign = "-" if self.quantity < 0 else ""
            return f"{sign}${abs(self.quantity):,.2f}"
        return f"{self.quantity} {self.commodity}"

    def __neg__(self) -> "Amount":
        return Amount(-self.quantity, self.commodity)

    def __add__(self, other: "Amount") -> "Amount":
        if self.commodity != other.commodity:
            raise ValueError(f"Cannot add {self.commodity} and {other.commodity}")
        return Amount(self.quantity + other.quantity, self.commodity)


@dataclass(frozen=True)
class Posting:
    account: str
    amount: Amount | None  # None only for single auto-balanced posting
    balance_assertion: Amount | None = None
    comment: str | None = None


@dataclass(frozen=True)
class Transaction:
    date: date
    description: str
    postings: tuple[Posting, ...]
    status: TransactionStatus = TransactionStatus.UNMARKED
    date2: date | None = None
    payee: str | None = None
    comment: str | None = None
    tags: dict[str, str] | None = None
    source_file: str | None = None
    source_line: int | None = None

    def validate(self) -> None:
        """Validate transaction: at most 1 None-amount posting.

        If all explicit, must sum to zero per commodity.
        """
        none_count = sum(1 for p in self.postings if p.amount is None)
        if none_count > 1:
            raise ValueError("At most one posting may have an inferred (None) amount")
        if none_count == 0:
            # All amounts explicit -- must balance per commodity
            sums: dict[str, Decimal] = {}
            for p in self.postings:
                assert p.amount is not None
                sums[p.amount.commodity] = (
                    sums.get(p.amount.commodity, Decimal(0)) + p.amount.quantity
                )
            for commodity, total in sums.items():
                if total != Decimal(0):
                    raise ValueError(
                        f"Transaction does not balance for {commodity}: {total}"
                    )


@dataclass(frozen=True)
class CategorizedTransaction:
    original_description: str
    suggested_account: str
    confidence: float  # 0.0 - 1.0
    reasoning: str | None = None
    alternatives: list[str] | None = None
