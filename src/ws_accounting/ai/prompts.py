"""All prompt templates for AI interactions -- single source of truth."""

from __future__ import annotations

import json


# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

SYSTEM_CATEGORIZER = (
    "You are a personal finance categorization assistant. "
    "You categorize bank transaction descriptions into accounting categories. "
    "You respond ONLY with valid JSON -- no markdown, no explanation. "
    "You are accurate and conservative -- when unsure, indicate lower confidence."
)

SYSTEM_INSIGHTS = (
    "You are a personal finance analyst. You analyze spending patterns "
    "and provide actionable, specific advice. Be concise and use concrete numbers. "
    "Format responses in Markdown."
)


# ---------------------------------------------------------------------------
# Categorization prompts
# ---------------------------------------------------------------------------


def categorize_batch_prompt(
    transactions: list[dict],
    categories: list[str],
    corrections: list[dict] | None = None,
) -> str:
    """Build the categorization prompt for a batch of transactions.

    Args:
        transactions: List of dicts with description, amount, date.
        categories: Chart of accounts (list of account strings).
        corrections: Recent user corrections for learning.

    Returns:
        The fully-assembled prompt string.
    """
    categories_str = "\n".join(f"  - {c}" for c in categories)

    txn_lines = []
    for i, txn in enumerate(transactions):
        desc = txn.get("description", "")
        amount = txn.get("amount", "")
        txn_lines.append(
            f'  {{"id": {i}, "description": "{desc}", "amount": "{amount}"}}'
        )
    txn_str = ",\n".join(txn_lines)

    corrections_section = ""
    if corrections:
        corr_lines = []
        for c in corrections:
            corr_lines.append(
                f'  "{c["description"]}": '
                f'{c.get("original", c.get("account", ""))} -> {c.get("corrected", c.get("account", ""))}'
            )
        corrections_section = (
            "\n\nPrevious corrections (learn from these):\n"
            + "\n".join(corr_lines)
        )

    return f"""Categorize these transactions into the following accounts:

Available categories:
{categories_str}
{corrections_section}

Transactions to categorize:
[
{txn_str}
]

Respond with a JSON array:
[
  {{"id": 0, "account": "expenses:food:groceries", "confidence": 0.95, "reasoning": "Whole Foods is a grocery store", "alternatives": ["expenses:shopping:household"]}},
  ...
]

Rules:
- confidence: 0.0-1.0 (0.9+ for obvious matches, 0.5-0.7 for uncertain)
- Always include 1-2 alternatives
- Use exact category names from the list above
- If truly unknown, use "expenses:other" with low confidence"""


# Keep old name as alias for backward compatibility
build_categorization_prompt = categorize_batch_prompt


# ---------------------------------------------------------------------------
# Insights prompts
# ---------------------------------------------------------------------------


def insights_prompt(context: dict) -> str:
    """Build the financial insights prompt from a context dict.

    Args:
        context: Dict with period, income, expenses, by_category.

    Returns:
        The fully-assembled prompt string.
    """
    period = context.get("period", "this month")
    income = context.get("income", "unknown")
    expenses = context.get("expenses", "unknown")
    by_category = context.get("by_category", {})

    cat_lines = []
    for cat, amount in sorted(
        by_category.items(),
        key=lambda x: float(x[1].replace("$", "").replace(",", ""))
        if isinstance(x[1], str) and x[1].replace("$", "").replace(",", "").replace(".", "").lstrip("-").isdigit()
        else 0,
        reverse=True,
    ):
        cat_lines.append(f"  - {cat}: {amount}")

    return f"""Analyze my finances for {period}:

Income: {income}
Total Expenses: {expenses}

Spending by category:
{chr(10).join(cat_lines) if cat_lines else "  No data"}

Please provide:
1. A brief summary of my financial health this period
2. Top 3 spending categories and whether they seem reasonable
3. Any unusual patterns or anomalies
4. 2-3 specific, actionable suggestions to improve

Keep the response under 300 words."""


def custom_query_prompt(query: str, context: dict) -> str:
    """Build a custom query prompt with financial context.

    Args:
        query: The user's question.
        context: Dict with period, income, expenses, by_category.

    Returns:
        The fully-assembled prompt string.
    """
    period = context.get("period", "recent")
    income = context.get("income", "unknown")
    expenses = context.get("expenses", "unknown")
    by_category = context.get("by_category", {})

    cat_lines = [f"  - {cat}: {amt}" for cat, amt in by_category.items()]

    return f"""Given my financial data for {period}:
Income: {income}, Expenses: {expenses}
Categories: {chr(10).join(cat_lines) if cat_lines else "No data"}

Answer this question: {query}

Be specific and reference actual numbers from the data provided."""


def build_insights_prompt(
    income_statement: str = "Not available",
    prev_income_statement: str = "Not available",
    expense_trends: str = "Not available",
    large_transactions: str = "Not available",
    budget_status: str = "Not available",
) -> str:
    """Build the financial insights prompt (legacy format for InsightsGenerator).

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
