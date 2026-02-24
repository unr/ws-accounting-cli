"""Privacy-first data sanitization -- strips sensitive info before sending to AI."""

from __future__ import annotations

import re

# Patterns to redact (order matters -- more specific patterns first)
_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Masked card numbers: xxxx1234, XXXX-1234
    (re.compile(r"x{4,}[\s-]?\d{4}", re.IGNORECASE), "[CARD]"),
    # Credit/debit card numbers: 1234 5678 9012 3456
    (
        re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"),
        "[CARD]",
    ),
    # SSN: 123-45-6789
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN]"),
    # Email addresses
    (
        re.compile(
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
        ),
        "[EMAIL]",
    ),
    # Bank account numbers: 9-12 consecutive digits
    (re.compile(r"\b\d{9,12}\b"), "[ACCT]"),
]


def sanitize(text: str) -> str:
    """Remove sensitive information from text before sending to AI."""
    result = text
    for pattern, replacement in _PATTERNS:
        result = pattern.sub(replacement, result)
    return result


# Keep the old name as an alias for backward compatibility
sanitize_description = sanitize


def sanitize_transactions(transactions: list[dict]) -> list[dict]:
    """Sanitize a list of transaction dicts for AI processing.

    Applies sanitization to all string values in each dict.
    """
    sanitized = []
    for txn in transactions:
        clean = {}
        for key, value in txn.items():
            if isinstance(value, str):
                clean[key] = sanitize(value)
            else:
                clean[key] = value
        sanitized.append(clean)
    return sanitized


def sanitize_for_ai(descriptions: list[str]) -> list[str]:
    """Batch sanitize transaction descriptions for AI processing."""
    return [sanitize(d) for d in descriptions]


def get_preview(transactions: list[dict]) -> str:
    """Generate a human-readable preview of what data will be sent to AI."""
    lines = ["Data being sent to AI:", ""]
    for txn in transactions[:10]:
        desc = txn.get("description", "")
        amount = txn.get("amount", "")
        lines.append(f"  {desc}: {amount}")
    if len(transactions) > 10:
        lines.append(f"  ... and {len(transactions) - 10} more")
    return "\n".join(lines)
