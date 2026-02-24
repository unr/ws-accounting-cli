"""AI-powered transaction categorization with multi-layer caching."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal

from ws_accounting.ai.client import AIProvider
from ws_accounting.ai.privacy import sanitize_description, sanitize_transactions
from ws_accounting.ai.prompts import (
    SYSTEM_CATEGORIZER,
    categorize_batch_prompt,
)
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


# ---------------------------------------------------------------------------
# Hash helpers
# ---------------------------------------------------------------------------


def description_hash(description: str, amount_bucket: str = "") -> str:
    """Generate a deterministic hash for cache lookup.

    Combines normalized description and amount bucket into a 16-char hex digest.
    """
    key = f"{description.lower().strip()}|{amount_bucket}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# CategorizationPipeline (new API)
# ---------------------------------------------------------------------------


class CategorizationPipeline:
    """Multi-stage categorization: cache -> rules -> AI, with auto-promotion.

    This is the primary API for categorizing transactions. It wraps the
    lower-level Categorizer class with additional features like description
    hashing and configurable categories.
    """

    PROMOTION_THRESHOLD = 3  # corrections before auto-caching

    def __init__(
        self,
        ai_provider: AIProvider,
        db: Database | None = None,
        categories: list[str] | None = None,
    ) -> None:
        self.ai = ai_provider
        self.db = db
        self.categories = categories or DEFAULT_CATEGORIES

    async def categorize_batch(
        self,
        transactions: list[dict],
    ) -> list[CategorizedTransaction]:
        """Categorize a batch of transactions. Returns results in same order as input."""
        results: list[CategorizedTransaction | None] = [None] * len(transactions)
        uncached_indices: list[int] = []

        # Stage 1: Check cache
        if self.db:
            for i, txn in enumerate(transactions):
                desc = txn.get("description", "")
                amt = txn.get("amount", Decimal("0"))
                bucket = amount_to_bucket(abs(Decimal(str(amt))))
                cached = lookup_category(self.db, desc, bucket)
                if cached:
                    results[i] = CategorizedTransaction(
                        original_description=desc,
                        suggested_account=cached.account,
                        confidence=cached.confidence,
                        reasoning="Cached from previous categorization",
                        alternatives=[],
                    )
                else:
                    uncached_indices.append(i)
        else:
            uncached_indices = list(range(len(transactions)))

        # Stage 2: AI for uncached
        if uncached_indices:
            uncached_txns = [transactions[i] for i in uncached_indices]
            sanitized = sanitize_transactions(
                [
                    {
                        "description": t.get("description", ""),
                        "amount": str(t.get("amount", "")),
                        "date": t.get("date", ""),
                    }
                    for t in uncached_txns
                ]
            )

            prompt = categorize_batch_prompt(sanitized, self.categories)

            try:
                response = await self.ai.complete(prompt, system=SYSTEM_CATEGORIZER)

                # Strip markdown fences if present
                text = response.strip()
                if text.startswith("```"):
                    text = text.split("\n", 1)[1].rsplit("```", 1)[0]

                ai_results = json.loads(text)

                for ai_result in ai_results:
                    idx_in_batch = ai_result.get("id", 0)
                    if idx_in_batch < len(uncached_indices):
                        orig_idx = uncached_indices[idx_in_batch]
                        desc = transactions[orig_idx].get("description", "")

                        cat_txn = CategorizedTransaction(
                            original_description=desc,
                            suggested_account=ai_result.get(
                                "account", "expenses:miscellaneous"
                            ),
                            confidence=float(ai_result.get("confidence", 0.5)),
                            reasoning=ai_result.get("reasoning"),
                            alternatives=ai_result.get("alternatives", []),
                        )
                        results[orig_idx] = cat_txn

                        # Cache the result
                        if self.db:
                            amt = transactions[orig_idx].get("amount", Decimal("0"))
                            bucket = amount_to_bucket(abs(Decimal(str(amt))))
                            cache_category(
                                self.db,
                                desc,
                                bucket,
                                cat_txn.suggested_account,
                                cat_txn.confidence,
                                "ai",
                            )

            except (json.JSONDecodeError, KeyError, IndexError):
                # AI response unparseable -- mark remaining as unknown
                for idx in uncached_indices:
                    if results[idx] is None:
                        results[idx] = CategorizedTransaction(
                            original_description=transactions[idx].get(
                                "description", ""
                            ),
                            suggested_account="expenses:miscellaneous",
                            confidence=0.0,
                            reasoning="AI categorization failed",
                            alternatives=[],
                        )

        # Fill any remaining None entries
        for i, result in enumerate(results):
            if result is None:
                results[i] = CategorizedTransaction(
                    original_description=transactions[i].get("description", ""),
                    suggested_account="expenses:miscellaneous",
                    confidence=0.0,
                    reasoning="Uncategorized",
                    alternatives=[],
                )

        return results  # type: ignore[return-value]

    def record_user_correction(
        self,
        description: str,
        original_account: str,
        corrected_account: str,
    ) -> None:
        """Record a user correction and potentially auto-promote to cache."""
        if not self.db:
            return

        record_correction(self.db, description, original_account, corrected_account)

        count = get_corrections_count(self.db, description)
        if count >= self.PROMOTION_THRESHOLD:
            # Auto-promote: cache as user rule for all buckets
            cache_category(
                self.db,
                description,
                "$0-25",
                corrected_account,
                1.0,
                "user",
            )


# ---------------------------------------------------------------------------
# Categorizer (original API -- kept for backward compatibility)
# ---------------------------------------------------------------------------


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
            cached = lookup_category(self.db, txn["description"], bucket)
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
                    bucket = amount_to_bucket(abs(uncached[j]["amount"]))
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
                    original_description=transactions[i]["description"],
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
                "description": sanitize_description(t["description"]),
                "amount": str(t["amount"]),
                "date": t.get("date", ""),
            }
            for t in transactions
        ]

        prompt = categorize_batch_prompt(
            transactions=sanitized,
            categories=DEFAULT_CATEGORIES,
            corrections=[],
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
                        confidence=float(item.get("confidence", 0.5)),
                        reasoning=item.get("reasoning"),
                        alternatives=item.get("alternatives", []),
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
        record_correction(self.db, description, original, corrected)
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
