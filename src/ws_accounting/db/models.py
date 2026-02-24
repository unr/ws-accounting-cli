"""Database table dataclasses.

Each dataclass mirrors a table in the sidecar SQLite database.
All monetary amounts are stored as TEXT strings, never floats.
"""

from dataclasses import dataclass, field
import sqlite3


@dataclass
class Budget:
    """A budget period for a spending category."""

    id: int | None = None
    category: str = ""
    amount: str = "0"  # TEXT for money
    period: str = "monthly"  # "monthly", "quarterly", "yearly"
    start_date: str | None = None
    end_date: str | None = None
    rollover: int = 0
    created_at: str | None = None
    updated_at: str | None = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Budget":
        return cls(
            id=row["id"],
            category=row["category"],
            amount=row["amount"],
            period=row["period"],
            start_date=row["start_date"],
            end_date=row["end_date"],
            rollover=row["rollover"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


@dataclass
class Goal:
    """A savings goal."""

    id: int | None = None
    name: str = ""
    target_amount: str = "0"
    current_amount: str = "0"
    account: str | None = None
    target_date: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Goal":
        return cls(
            id=row["id"],
            name=row["name"],
            target_amount=row["target_amount"],
            current_amount=row["current_amount"],
            account=row["account"],
            target_date=row["target_date"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


@dataclass
class RecurringTransaction:
    """A recurring transaction template."""

    id: int | None = None
    description: str = ""
    amount: str = "0"
    from_account: str = ""
    to_account: str = ""
    frequency: str = "monthly"  # "weekly", "monthly", "yearly"
    next_due: str = ""
    last_generated: str | None = None
    active: int = 1
    created_at: str | None = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "RecurringTransaction":
        return cls(
            id=row["id"],
            description=row["description"],
            amount=row["amount"],
            from_account=row["from_account"],
            to_account=row["to_account"],
            frequency=row["frequency"],
            next_due=row["next_due"],
            last_generated=row["last_generated"],
            active=row["active"],
            created_at=row["created_at"],
        )


@dataclass
class CategorizationEntry:
    """A cached AI categorization result."""

    id: int | None = None
    description_hash: str = ""
    description: str = ""
    amount_bucket: str | None = None
    suggested_account: str = ""
    confidence: float = 0.0
    source: str = "ai"  # "ai", "user", "rule"
    created_at: str | None = None
    used_count: int = 1

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "CategorizationEntry":
        return cls(
            id=row["id"],
            description_hash=row["description_hash"],
            description=row["description"],
            amount_bucket=row["amount_bucket"],
            suggested_account=row["suggested_account"],
            confidence=row["confidence"],
            source=row["source"],
            created_at=row["created_at"],
            used_count=row["used_count"],
        )


@dataclass
class ImportProfile:
    """A bank-specific import profile."""

    id: int | None = None
    name: str = ""
    bank_name: str | None = None
    account: str = ""
    rules_file: str | None = None
    date_format: str | None = None
    csv_delimiter: str = ","
    skip_rows: int = 1
    created_at: str | None = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "ImportProfile":
        return cls(
            id=row["id"],
            name=row["name"],
            bank_name=row["bank_name"],
            account=row["account"],
            rules_file=row["rules_file"],
            date_format=row["date_format"],
            csv_delimiter=row["csv_delimiter"],
            skip_rows=row["skip_rows"],
            created_at=row["created_at"],
        )


@dataclass
class ImportHistory:
    """A record of a CSV import event."""

    id: int | None = None
    profile_id: int | None = None
    file_path: str = ""
    imported_count: int = 0
    duplicate_count: int = 0
    imported_at: str | None = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "ImportHistory":
        return cls(
            id=row["id"],
            profile_id=row["profile_id"],
            file_path=row["file_path"],
            imported_count=row["imported_count"],
            duplicate_count=row["duplicate_count"],
            imported_at=row["imported_at"],
        )


@dataclass
class Reconciliation:
    """A reconciliation record for an account."""

    id: int | None = None
    account: str = ""
    statement_date: str = ""
    statement_balance: str = "0"
    reconciled_at: str | None = None
    status: str = "completed"

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Reconciliation":
        return cls(
            id=row["id"],
            account=row["account"],
            statement_date=row["statement_date"],
            statement_balance=row["statement_balance"],
            reconciled_at=row["reconciled_at"],
            status=row["status"],
        )


@dataclass
class AppSetting:
    """A key-value app setting."""

    key: str = ""
    value: str = ""
    updated_at: str | None = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "AppSetting":
        return cls(
            key=row["key"],
            value=row["value"],
            updated_at=row["updated_at"],
        )
