"""Domain models — immutable dataclasses for all financial data."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum


class TransactionStatus(Enum):
    UNMARKED = ""        # Just entered, not verified
    PENDING = "!"        # Seen on statement, not fully reconciled
    CLEARED = "*"        # Verified against bank statement


@dataclass(frozen=True)
class Amount:
    quantity: Decimal
    commodity: str              # "$", "EUR", etc.


@dataclass(frozen=True)
class Posting:
    account: str                # e.g., "expenses:food:groceries"
    amount: Amount | None       # None only for the single auto-balanced posting
    balance_assertion: Amount | None = None  # e.g., = $1,234.56
    comment: str | None = None


@dataclass(frozen=True)
class Transaction:
    date: date
    status: TransactionStatus
    description: str
    postings: tuple[Posting, ...]
    date2: date | None = None          # Auxiliary/effective date
    payee: str | None = None
    comment: str | None = None
    tags: dict[str, str] = field(default_factory=dict)
    source_file: str | None = None
    source_line: int | None = None

    def validate(self) -> None:
        """Enforce double-entry invariants before any journal write.

        - At most one posting may have None amount
        - If all amounts are explicit, they must sum to zero per commodity
        """
        none_count = sum(1 for p in self.postings if p.amount is None)
        if none_count > 1:
            raise ValueError(
                f"At most one posting may omit amount, found {none_count}"
            )

        if none_count == 0:
            sums: dict[str, Decimal] = {}
            for p in self.postings:
                assert p.amount is not None
                key = p.amount.commodity
                sums[key] = sums.get(key, Decimal("0")) + p.amount.quantity
            for commodity, total in sums.items():
                if total != Decimal("0"):
                    raise ValueError(
                        f"Transaction does not balance for"
                        f" {commodity}: off by {total}"
                    )


@dataclass(frozen=True)
class CategorizedTransaction:
    original_description: str
    suggested_account: str
    confidence: float           # 0.0 - 1.0
    reasoning: str | None = None
    alternatives: list[str] = field(default_factory=list)
