"""Parse hledger JSON output into domain models with sign normalization."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from ws_accounting.core.models import (
    Amount,
    Posting,
    Transaction,
    TransactionStatus,
)


@dataclass(frozen=True)
class AccountBalance:
    account: str
    balance: Amount
    children: list["AccountBalance"] = field(default_factory=list)


@dataclass(frozen=True)
class IncomeStatement:
    income: list[AccountBalance]
    expenses: list[AccountBalance]
    total_income: Amount
    total_expenses: Amount
    net: Amount


@dataclass(frozen=True)
class BalanceSheet:
    assets: list[AccountBalance]
    liabilities: list[AccountBalance]
    equity: list[AccountBalance]
    total_assets: Amount
    total_liabilities: Amount
    net_worth: Amount


def _account_type(account_name: str) -> str:
    """Determine account type from name prefix."""
    prefix = account_name.split(":")[0].lower()
    return prefix  # "assets", "liabilities", "income", "expenses", "equity"


def normalize_sign(amount: Decimal, account_name: str) -> Decimal:
    """Normalize sign for display.

    - Income: negate (hledger reports as negative credit)
    - Liabilities: negate (show as positive = amount owed)
    - Assets/Expenses: as-is
    """
    atype = _account_type(account_name)
    if atype in ("income", "liabilities"):
        return -amount
    return amount


def parse_amount(data: dict) -> Amount:
    """Parse an hledger JSON amount object.

    hledger JSON amount format:
    {
        "acommodity": "$",
        "aquantity": {"decimalMantissa": ..., "decimalPlaces": ...},
        ...
    }
    """
    commodity = data.get("acommodity", "$")
    qty_data = data.get("aquantity", {})

    if isinstance(qty_data, dict):
        mantissa = qty_data.get("decimalMantissa", 0)
        places = qty_data.get("decimalPlaces", 0)
        quantity = Decimal(mantissa) / Decimal(10 ** places)
    elif isinstance(qty_data, (int, float, str)):
        quantity = Decimal(str(qty_data))
    else:
        quantity = Decimal("0")

    return Amount(quantity=quantity, commodity=commodity)


def parse_amounts(amounts: list[dict]) -> Amount | None:
    """Parse a list of amounts (hledger often returns list).

    Uses the first element. Returns None for empty lists.
    """
    if not amounts:
        return None
    return parse_amount(amounts[0])


def parse_balance_report(
    data: dict | list,
) -> list[AccountBalance]:
    """Parse hledger balance JSON output into AccountBalance list.

    hledger ``balance --output-format=json`` returns::

        [
          [                                       # rows list
            [short_name, full_name, depth, [amounts]],
            ...
          ],
          [total_amount, ...]                     # totals list
        ]
    """
    results: list[AccountBalance] = []

    if isinstance(data, list) and len(data) == 2:
        rows, _totals = data
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, list) and len(row) >= 4:
                    # [short_name, full_name, depth, amounts]
                    account_name = row[1]  # full account name
                    amounts_data = row[3]
                    if isinstance(amounts_data, list) and amounts_data:
                        amount = parse_amount(amounts_data[0])
                    else:
                        amount = Amount(Decimal("0"), "$")
                    results.append(AccountBalance(
                        account=account_name,
                        balance=amount,
                    ))

    return results


def parse_register(data: list[dict]) -> list[Transaction]:
    """Parse hledger register JSON output into Transaction list."""
    transactions: list[Transaction] = []

    for entry in data:
        date_str = entry.get("tdate", "")
        date2_str = entry.get("tdate2", "")
        status_str = entry.get("tstatus", "")
        description = entry.get("tdescription", "")

        # Parse date
        txn_date = (
            date.fromisoformat(date_str) if date_str else date.today()
        )
        txn_date2 = (
            date.fromisoformat(date2_str) if date2_str else None
        )

        # Parse status
        status_map = {
            "Cleared": TransactionStatus.CLEARED,
            "Pending": TransactionStatus.PENDING,
        }
        status = status_map.get(
            status_str, TransactionStatus.UNMARKED
        )

        # Parse postings
        postings_data = entry.get("tpostings", [])
        postings: list[Posting] = []
        for p in postings_data:
            account = p.get("paccount", "")
            p_amounts = p.get("pamount", [])
            amount = parse_amounts(p_amounts)

            # Balance assertion
            ba_data = p.get("pbalanceassertion")
            balance_assertion = None
            if ba_data:
                ba_amount = ba_data.get("baamount")
                if ba_amount:
                    balance_assertion = parse_amounts(
                        ba_amount
                        if isinstance(ba_amount, list)
                        else [ba_amount]
                    )

            comment = p.get("pcomment", "").strip() or None
            postings.append(Posting(
                account=account,
                amount=amount,
                balance_assertion=balance_assertion,
                comment=comment,
            ))

        # Parse tags
        tags = {}
        for tag in entry.get("ttags", []):
            if isinstance(tag, list) and len(tag) == 2:
                tags[tag[0]] = tag[1]

        # Parse payee from description (payee | note format)
        payee = None
        if "|" in description:
            parts = description.split("|", 1)
            payee = parts[0].strip()
            description = parts[1].strip()

        comment = entry.get("tcomment", "").strip() or None

        source_pos = entry.get("tsourcepos")
        source_file = None
        source_line = None
        if source_pos and isinstance(source_pos, list) and source_pos:
            source_file = source_pos[0].get("sourceName")
            source_line = source_pos[0].get("sourceLine")

        transactions.append(Transaction(
            date=txn_date,
            date2=txn_date2,
            status=status,
            description=description,
            payee=payee,
            postings=tuple(postings),
            comment=comment,
            tags=tags,
            source_file=source_file,
            source_line=source_line,
        ))

    return transactions
