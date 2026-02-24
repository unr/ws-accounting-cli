"""Privacy-first data sanitization for AI calls."""

from __future__ import annotations

import re

# Patterns to redact (order matters -- more specific patterns first)
_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Masked card numbers: xxxx1234, XXXX-1234
    (re.compile(r"x{4,}[\s-]?\d{4}", re.IGNORECASE), "[CARD]"),
    # Credit/debit card numbers: 1234 5678 9012 3456
    (
        re.compile(
            r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"
        ),
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


def sanitize_description(text: str) -> str:
    """Remove sensitive patterns from a transaction description."""
    result = text
    for pattern, replacement in _PATTERNS:
        result = pattern.sub(replacement, result)
    return result


def sanitize_for_ai(descriptions: list[str]) -> list[str]:
    """Batch sanitize transaction descriptions for AI processing."""
    return [sanitize_description(d) for d in descriptions]
