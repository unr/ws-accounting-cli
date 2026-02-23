"""Database table models."""

from dataclasses import dataclass
import sqlite3


@dataclass
class Budget:
    id: int | None
    category: str
    month: str
    amount: str  # Decimal string e.g. "600.00"
    rollover: bool
    rollover_cap: str | None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Budget":
        return cls(
            id=row["id"],
            category=row["category"],
            month=row["month"],
            amount=row["amount"],
            rollover=bool(row["rollover"]),
            rollover_cap=row["rollover_cap"],
        )


@dataclass
class Goal:
    id: int | None
    name: str
    target_amount: str
    current_amount: str
    target_date: str | None
    linked_account: str | None
    type: str
    created_at: str | None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Goal":
        return cls(
            id=row["id"],
            name=row["name"],
            target_amount=row["target_amount"],
            current_amount=row["current_amount"],
            target_date=row["target_date"],
            linked_account=row["linked_account"],
            type=row["type"],
            created_at=row["created_at"],
        )


@dataclass
class RecurringTransaction:
    id: int | None
    description: str
    amount: str
    from_account: str
    to_account: str
    frequency: str  # "weekly", "monthly", "yearly"
    next_due: str
    end_date: str | None
    auto_enter: bool
    created_at: str | None

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
            end_date=row["end_date"],
            auto_enter=bool(row["auto_enter"]),
            created_at=row["created_at"],
        )


@dataclass
class CategorizationCache:
    id: int | None
    description: str
    amount_bucket: str
    account: str
    confidence: float
    source: str
    created_at: str | None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "CategorizationCache":
        return cls(
            id=row["id"],
            description=row["description"],
            amount_bucket=row["amount_bucket"],
            account=row["account"],
            confidence=row["confidence"],
            source=row["source"],
            created_at=row["created_at"],
        )


@dataclass
class CategorizationCorrection:
    id: int | None
    description: str
    original_account: str
    corrected_account: str
    created_at: str | None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "CategorizationCorrection":
        return cls(
            id=row["id"],
            description=row["description"],
            original_account=row["original_account"],
            corrected_account=row["corrected_account"],
            created_at=row["created_at"],
        )


@dataclass
class Reconciliation:
    id: int | None
    account: str
    statement_date: str
    statement_balance: str
    reconciled_at: str | None
    status: str

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
class ImportProfile:
    id: int | None
    name: str
    bank_name: str | None
    rules_path: str
    default_status: str
    last_used: str | None
    created_at: str | None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "ImportProfile":
        return cls(
            id=row["id"],
            name=row["name"],
            bank_name=row["bank_name"],
            rules_path=row["rules_path"],
            default_status=row["default_status"],
            last_used=row["last_used"],
            created_at=row["created_at"],
        )


@dataclass
class ImportHistory:
    id: int | None
    csv_filename: str
    profile_id: int | None
    txn_count: int
    duplicate_count: int
    imported_at: str | None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "ImportHistory":
        return cls(
            id=row["id"],
            csv_filename=row["csv_filename"],
            profile_id=row["profile_id"],
            txn_count=row["txn_count"],
            duplicate_count=row["duplicate_count"],
            imported_at=row["imported_at"],
        )


@dataclass
class InsightsCache:
    id: int | None
    period: str
    content: str
    model: str
    generated_at: str | None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "InsightsCache":
        return cls(
            id=row["id"],
            period=row["period"],
            content=row["content"],
            model=row["model"],
            generated_at=row["generated_at"],
        )


@dataclass
class ImportHash:
    id: int | None
    hash: str
    import_history_id: int | None
    created_at: str | None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "ImportHash":
        return cls(
            id=row["id"],
            hash=row["hash"],
            import_history_id=row["import_history_id"],
            created_at=row["created_at"],
        )


@dataclass
class AppSetting:
    key: str
    value: str
    updated_at: str | None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "AppSetting":
        return cls(
            key=row["key"],
            value=row["value"],
            updated_at=row["updated_at"],
        )
