"""Single source of truth for all AI prompt templates."""

from __future__ import annotations

import json


def build_categorization_prompt(
    transactions: list[dict],
    accounts: list[str],
    corrections: list[dict] | None = None,
) -> str:
    """Build the categorization prompt for a batch of transactions.

    Args:
        transactions: List of dicts with description, amount, date.
        accounts: Chart of accounts (list of account strings).
        corrections: Recent user corrections for learning.

    Returns:
        The fully-assembled prompt string.
    """
    accounts_list = "\n".join(f"  - {a}" for a in accounts)

    corrections_block = "None yet."
    if corrections:
        lines = []
        for c in corrections:
            lines.append(
                f'  - "{c["description"]}": '
                f'{c["original"]} -> {c["corrected"]}'
            )
        corrections_block = "\n".join(lines)

    txn_block = json.dumps(transactions, indent=2)

    return f"""\
Given these financial transactions, categorize each one into the \
most appropriate account from the chart of accounts below.

Chart of Accounts:
{accounts_list}

Previous corrections (learn from these):
{corrections_block}

For each transaction, respond with a JSON array where each element has:
- "description": the original description
- "account": the suggested account from the chart
- "confidence": 0.0 to 1.0
- "reasoning": brief explanation
- "alternatives": list of 1-2 alternative accounts

Transactions to categorize:
{txn_block}

Respond with ONLY valid JSON, no other text."""


def build_insights_prompt(
    income_statement: str = "Not available",
    prev_income_statement: str = "Not available",
    expense_trends: str = "Not available",
    large_transactions: str = "Not available",
    budget_status: str = "Not available",
) -> str:
    """Build the financial insights prompt.

    All parameters default to "Not available" so callers can
    provide only the data they have.

    Returns:
        The fully-assembled prompt string.
    """
    return f"""\
You are a personal finance analyst. Analyze this financial data \
and provide insights.

Income Statement (Current Month):
{income_statement}

Income Statement (Previous Month):
{prev_income_statement}

Top Expense Categories (3-month trend):
{expense_trends}

Large Transactions (>$200 this month):
{large_transactions}

Budget Status:
{budget_status}

Provide your analysis in markdown format with these sections:
## Key Findings
## Anomalies
## Budget Adherence
## Recommendations (2-3 actionable items)"""
