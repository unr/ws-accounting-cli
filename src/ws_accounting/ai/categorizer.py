"""AI-powered transaction categorization with multi-layer caching."""

from __future__ import annotations

import json
from decimal import Decimal

from ws_accounting.ai.client import AIProvider
from ws_accounting.ai.privacy import sanitize_description
from ws_accounting.ai.prompts import build_categorization_prompt
from ws_accounting.config.defaults import DEFAULT_CATEGORIES
from ws_accounting.core.models import CategorizedTransaction
from ws_accounting.db.database import Database
from ws_accounting.db.queries import (
    amount_to_bucket,
    cache_category,
    get_corrections_count,
    lookup_category,
    record_correction,
)


class Categorizer:
    """Multi-layer categorization: cache -> rules -> AI."""

    def __init__(
        self,
        db: Database,
        provider: AIProvider | None = None,
    ) -> None:
        self.db = db
        self.provider = provider

    async def categorize_batch(
        self,
        transactions: list[dict],
    ) -> list[CategorizedTransaction]:
        """Categorize a batch of transactions.

        Each transaction dict must have:
            description (str), amount (Decimal), date (str).

        Pipeline:
        1. Check SQLite cache (description + amount_bucket).
        2. Send remaining unknowns to AI in a single batch.
        3. Cache AI results.
        4. Return merged results.
        """
        results: list[CategorizedTransaction | None] = []
        uncached: list[dict] = []
        uncached_indices: list[int] = []

        # Step 1: Check cache
        for i, txn in enumerate(transactions):
            bucket = amount_to_bucket(abs(txn["amount"]))
            cached = lookup_category(
                self.db, txn["description"], bucket
            )
            if cached:
                results.append(
                    CategorizedTransaction(
                        original_description=txn["description"],
                        suggested_account=cached.account,
                        confidence=cached.confidence,
                        reasoning="Cached result",
                        alternatives=[],
                    )
                )
            else:
                results.append(None)  # placeholder
                uncached.append(txn)
                uncached_indices.append(i)

        # Step 2: AI categorization for uncached
        if uncached and self.provider:
            ai_results = await self._ai_categorize(uncached)
            for j, idx in enumerate(uncached_indices):
                if j < len(ai_results):
                    results[idx] = ai_results[j]
                    # Cache the result
                    bucket = amount_to_bucket(
                        abs(uncached[j]["amount"])
                    )
                    cache_category(
                        self.db,
                        ai_results[j].original_description,
                        bucket,
                        ai_results[j].suggested_account,
                        ai_results[j].confidence,
                        "ai",
                    )

        # Fill any remaining None with fallback
        for i, r in enumerate(results):
            if r is None:
                results[i] = CategorizedTransaction(
                    original_description=transactions[i][
                        "description"
                    ],
                    suggested_account="expenses:miscellaneous",
                    confidence=0.0,
                    reasoning="No AI provider available",
                )

        return results  # type: ignore[return-value]

    async def _ai_categorize(
        self, transactions: list[dict]
    ) -> list[CategorizedTransaction]:
        """Send batch to AI and parse response."""
        assert self.provider is not None

        sanitized = [
            {
                "description": sanitize_description(
                    t["description"]
                ),
                "amount": str(t["amount"]),
                "date": t.get("date", ""),
            }
            for t in transactions
        ]

        prompt = build_categorization_prompt(
            transactions=sanitized,
            accounts=DEFAULT_CATEGORIES,
            corrections=[],  # TODO: load recent corrections
        )

        response = await self.provider.complete(prompt)
        return self._parse_response(response, transactions)

    def _parse_response(
        self,
        response: str,
        originals: list[dict],
    ) -> list[CategorizedTransaction]:
        """Parse AI JSON response into CategorizedTransaction list."""
        try:
            text = response.strip()
            # Strip markdown code fences if present
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0]

            data = json.loads(text)
            results: list[CategorizedTransaction] = []
            for i, item in enumerate(data):
                desc = (
                    originals[i]["description"]
                    if i < len(originals)
                    else item.get("description", "")
                )
                results.append(
                    CategorizedTransaction(
                        original_description=desc,
                        suggested_account=item.get(
                            "account", "expenses:miscellaneous"
                        ),
                        confidence=float(
                            item.get("confidence", 0.5)
                        ),
                        reasoning=item.get("reasoning"),
                        alternatives=item.get(
                            "alternatives", []
                        ),
                    )
                )
            return results
        except (json.JSONDecodeError, KeyError, IndexError):
            # Fallback: return low-confidence defaults
            return [
                CategorizedTransaction(
                    original_description=t["description"],
                    suggested_account="expenses:miscellaneous",
                    confidence=0.0,
                    reasoning="Failed to parse AI response",
                )
                for t in originals
            ]

    def apply_correction(
        self,
        description: str,
        original: str,
        corrected: str,
    ) -> None:
        """Record a user correction.

        Auto-promotes to cache after 3+ corrections for the
        same description.
        """
        record_correction(
            self.db, description, original, corrected
        )
        count = get_corrections_count(self.db, description)
        if count >= 3:
            # Auto-promote: cache as user rule for all buckets
            cache_category(
                self.db,
                description,
                "$0-25",
                corrected,
                1.0,
                "user",
            )
