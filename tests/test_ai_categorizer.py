"""Tests for AI categorizer -- cache, parsing, corrections, pipeline."""

from __future__ import annotations

import json
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from ws_accounting.ai.categorizer import (
    Categorizer,
    CategorizationPipeline,
    description_hash,
)
from ws_accounting.ai.client import AIProvider
from ws_accounting.core.models import CategorizedTransaction
from ws_accounting.db.database import Database
from ws_accounting.db.queries import (
    amount_to_bucket,
    cache_category,
    get_corrections_count,
    lookup_category,
    record_correction,
)


@pytest.fixture
def db() -> Database:
    """Create an in-memory Database with migrations applied."""
    database = Database(":memory:")
    database.migrate()
    yield database
    database.close()


def _make_mock_provider(response_text: str) -> AIProvider:
    """Create a mock AIProvider that returns the given text."""
    provider = AsyncMock(spec=AIProvider)
    provider.complete = AsyncMock(return_value=response_text)
    return provider


class MockAI:
    """Simple mock AI provider for pipeline tests."""

    def __init__(self, response: str):
        self._response = response
        self.call_count = 0

    async def complete(self, prompt: str, system: str = "") -> str:
        self.call_count += 1
        return self._response

    async def stream(self, prompt: str, system: str = ""):
        for word in self._response.split():
            yield word + " "


def _make_txn(
    description: str = "WHOLE FOODS",
    amount: str = "85.42",
    date: str = "2026-01-16",
) -> dict:
    """Create a test transaction dict."""
    return {
        "description": description,
        "amount": Decimal(amount),
        "date": date,
    }


# -----------------------------------------------------------------------
# description_hash tests
# -----------------------------------------------------------------------


class TestDescriptionHash:
    def test_deterministic(self):
        """Same inputs produce the same hash."""
        h1 = description_hash("WHOLE FOODS", "$25-100")
        h2 = description_hash("WHOLE FOODS", "$25-100")
        assert h1 == h2

    def test_different_descriptions(self):
        """Different descriptions produce different hashes."""
        h1 = description_hash("WHOLE FOODS", "$25-100")
        h2 = description_hash("STARBUCKS", "$25-100")
        assert h1 != h2

    def test_different_buckets(self):
        """Different amount buckets produce different hashes."""
        h1 = description_hash("WHOLE FOODS", "$0-25")
        h2 = description_hash("WHOLE FOODS", "$25-100")
        assert h1 != h2

    def test_case_insensitive(self):
        """Hash normalizes description to lowercase."""
        h1 = description_hash("Whole Foods", "$25-100")
        h2 = description_hash("whole foods", "$25-100")
        assert h1 == h2

    def test_strips_whitespace(self):
        """Hash strips leading/trailing whitespace."""
        h1 = description_hash("  WHOLE FOODS  ", "$25-100")
        h2 = description_hash("WHOLE FOODS", "$25-100")
        assert h1 == h2

    def test_returns_16_chars(self):
        """Hash is truncated to 16 hex characters."""
        h = description_hash("test", "bucket")
        assert len(h) == 16
        # All hex chars
        assert all(c in "0123456789abcdef" for c in h)


# -----------------------------------------------------------------------
# amount_to_bucket tests
# -----------------------------------------------------------------------


class TestAmountToBucket:
    def test_under_25(self):
        assert amount_to_bucket(Decimal("5.50")) == "$0-25"
        assert amount_to_bucket(Decimal("24.99")) == "$0-25"

    def test_25_to_100(self):
        assert amount_to_bucket(Decimal("25.00")) == "$25-100"
        assert amount_to_bucket(Decimal("99.99")) == "$25-100"

    def test_100_to_500(self):
        assert amount_to_bucket(Decimal("100.00")) == "$100-500"
        assert amount_to_bucket(Decimal("499.99")) == "$100-500"

    def test_500_plus(self):
        assert amount_to_bucket(Decimal("500.00")) == "$500+"
        assert amount_to_bucket(Decimal("9999.99")) == "$500+"

    def test_zero(self):
        assert amount_to_bucket(Decimal("0")) == "$0-25"

    def test_negative_uses_abs(self):
        """Negative amounts use absolute value for bucketing."""
        assert amount_to_bucket(Decimal("-85.42")) == "$25-100"


# -----------------------------------------------------------------------
# Cache hit / miss tests (Categorizer)
# -----------------------------------------------------------------------


class TestCacheHit:
    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached_result(self, db: Database):
        """When a transaction is in cache, return it without AI."""
        cache_category(
            db,
            "WHOLE FOODS",
            "$25-100",
            "expenses:food:groceries",
            0.95,
            "ai",
        )
        categorizer = Categorizer(db, provider=None)
        results = await categorizer.categorize_batch([_make_txn()])

        assert len(results) == 1
        assert results[0].suggested_account == "expenses:food:groceries"
        assert results[0].confidence == 0.95
        assert results[0].reasoning == "Cached result"

    @pytest.mark.asyncio
    async def test_cache_miss_no_provider_returns_default(self, db: Database):
        """Cache miss + no AI provider -> fallback to miscellaneous."""
        categorizer = Categorizer(db, provider=None)
        results = await categorizer.categorize_batch([_make_txn()])

        assert len(results) == 1
        assert results[0].suggested_account == "expenses:miscellaneous"
        assert results[0].confidence == 0.0
        assert "No AI provider" in results[0].reasoning

    @pytest.mark.asyncio
    async def test_mixed_cache_hit_and_miss(self, db: Database):
        """Mix of cached and uncached transactions."""
        cache_category(
            db,
            "STARBUCKS",
            "$0-25",
            "expenses:food:dining",
            0.9,
            "ai",
        )

        ai_response = json.dumps(
            [
                {
                    "description": "TARGET",
                    "account": "expenses:shopping:general",
                    "confidence": 0.8,
                    "reasoning": "Retail store",
                    "alternatives": ["expenses:shopping:clothing"],
                }
            ]
        )
        provider = _make_mock_provider(ai_response)
        categorizer = Categorizer(db, provider=provider)

        txns = [
            _make_txn("STARBUCKS", "5.50"),
            _make_txn("TARGET", "45.00"),
        ]
        results = await categorizer.categorize_batch(txns)

        assert len(results) == 2
        # First from cache
        assert results[0].suggested_account == "expenses:food:dining"
        assert results[0].reasoning == "Cached result"
        # Second from AI
        assert results[1].suggested_account == "expenses:shopping:general"
        assert results[1].confidence == 0.8

    @pytest.mark.asyncio
    async def test_ai_results_are_cached(self, db: Database):
        """After AI categorization, results are cached in DB."""
        ai_response = json.dumps(
            [
                {
                    "description": "NETFLIX",
                    "account": "expenses:subscriptions",
                    "confidence": 0.92,
                    "reasoning": "Streaming service",
                    "alternatives": ["expenses:entertainment"],
                }
            ]
        )
        provider = _make_mock_provider(ai_response)
        categorizer = Categorizer(db, provider=provider)

        await categorizer.categorize_batch([_make_txn("NETFLIX", "15.99")])

        # Verify it's now cached
        cached = lookup_category(db, "NETFLIX", "$0-25")
        assert cached is not None
        assert cached.account == "expenses:subscriptions"
        assert cached.source == "ai"


# -----------------------------------------------------------------------
# Response parsing tests (Categorizer)
# -----------------------------------------------------------------------


class TestParseResponse:
    def test_valid_json(self, db: Database):
        """Valid JSON array is parsed correctly."""
        categorizer = Categorizer(db)
        response = json.dumps(
            [
                {
                    "description": "WHOLE FOODS",
                    "account": "expenses:food:groceries",
                    "confidence": 0.95,
                    "reasoning": "Grocery store",
                    "alternatives": ["expenses:food:dining"],
                }
            ]
        )
        originals = [_make_txn()]
        results = categorizer._parse_response(response, originals)

        assert len(results) == 1
        assert isinstance(results[0], CategorizedTransaction)
        assert results[0].suggested_account == "expenses:food:groceries"
        assert results[0].confidence == 0.95
        assert results[0].reasoning == "Grocery store"
        assert results[0].alternatives == ["expenses:food:dining"]

    def test_invalid_json_returns_fallback(self, db: Database):
        """Invalid JSON returns low-confidence defaults."""
        categorizer = Categorizer(db)
        originals = [_make_txn(), _make_txn("TARGET", "30.00")]
        results = categorizer._parse_response("not valid json at all", originals)

        assert len(results) == 2
        for r in results:
            assert r.suggested_account == "expenses:miscellaneous"
            assert r.confidence == 0.0
            assert "Failed to parse" in r.reasoning

    def test_markdown_wrapped_json(self, db: Database):
        """JSON wrapped in markdown code fences is extracted."""
        categorizer = Categorizer(db)
        inner = json.dumps(
            [
                {
                    "description": "COSTCO",
                    "account": "expenses:food:groceries",
                    "confidence": 0.88,
                    "reasoning": "Warehouse store",
                    "alternatives": [],
                }
            ]
        )
        wrapped = f"```json\n{inner}\n```"
        originals = [_make_txn("COSTCO", "150.00")]
        results = categorizer._parse_response(wrapped, originals)

        assert len(results) == 1
        assert results[0].suggested_account == "expenses:food:groceries"
        assert results[0].confidence == 0.88

    def test_multiple_items(self, db: Database):
        """Multiple items in JSON array are all parsed."""
        categorizer = Categorizer(db)
        response = json.dumps(
            [
                {
                    "description": "WHOLE FOODS",
                    "account": "expenses:food:groceries",
                    "confidence": 0.95,
                    "reasoning": "Grocery",
                    "alternatives": [],
                },
                {
                    "description": "UBER",
                    "account": "expenses:transportation:transit",
                    "confidence": 0.85,
                    "reasoning": "Rideshare",
                    "alternatives": ["expenses:travel"],
                },
            ]
        )
        originals = [
            _make_txn("WHOLE FOODS", "85.42"),
            _make_txn("UBER", "22.50"),
        ]
        results = categorizer._parse_response(response, originals)

        assert len(results) == 2
        assert results[0].suggested_account == "expenses:food:groceries"
        assert results[1].suggested_account == "expenses:transportation:transit"

    def test_preserves_original_description(self, db: Database):
        """Original (unsanitized) description is used, not AI's."""
        categorizer = Categorizer(db)
        response = json.dumps(
            [
                {
                    "description": "sanitized desc",
                    "account": "expenses:food:dining",
                    "confidence": 0.7,
                    "reasoning": "Cafe",
                    "alternatives": [],
                }
            ]
        )
        originals = [_make_txn("REAL DESCRIPTION")]
        results = categorizer._parse_response(response, originals)
        assert results[0].original_description == "REAL DESCRIPTION"

    def test_missing_optional_fields(self, db: Database):
        """Items missing optional fields get defaults."""
        categorizer = Categorizer(db)
        response = json.dumps(
            [
                {
                    "description": "TEST",
                    "account": "expenses:food:groceries",
                }
            ]
        )
        originals = [_make_txn("TEST")]
        results = categorizer._parse_response(response, originals)

        assert results[0].confidence == 0.5  # default
        assert results[0].reasoning is None
        assert results[0].alternatives == []


# -----------------------------------------------------------------------
# Correction tests (Categorizer)
# -----------------------------------------------------------------------


class TestCorrections:
    def test_apply_correction_records(self, db: Database):
        """Applying a correction records it in the DB."""
        categorizer = Categorizer(db)
        categorizer.apply_correction(
            "AMZN", "expenses:shopping:general", "expenses:office"
        )

        count = get_corrections_count(db, "AMZN")
        assert count == 1

    def test_auto_promote_at_three_corrections(self, db: Database):
        """After 3 corrections for same description, auto-promote."""
        categorizer = Categorizer(db)

        # Apply 3 corrections
        for _ in range(3):
            categorizer.apply_correction(
                "AMZN",
                "expenses:shopping:general",
                "expenses:office",
            )

        # Should now be cached as a user rule
        cached = lookup_category(db, "AMZN", "$0-25")
        assert cached is not None
        assert cached.account == "expenses:office"
        assert cached.confidence == 1.0
        assert cached.source == "user"

    def test_no_promote_below_three(self, db: Database):
        """Two corrections do not trigger auto-promote."""
        categorizer = Categorizer(db)
        categorizer.apply_correction(
            "TARGET",
            "expenses:shopping:general",
            "expenses:shopping:clothing",
        )
        categorizer.apply_correction(
            "TARGET",
            "expenses:shopping:general",
            "expenses:shopping:clothing",
        )

        # Not yet promoted
        cached = lookup_category(db, "TARGET", "$0-25")
        assert cached is None


# -----------------------------------------------------------------------
# amount_to_bucket integration (Categorizer)
# -----------------------------------------------------------------------


class TestAmountBucketIntegration:
    @pytest.mark.asyncio
    async def test_correct_bucket_used_for_cache(self, db: Database):
        """Cache lookup uses the correct amount bucket."""
        # Cache for $25-100 bucket
        cache_category(
            db,
            "STARBUCKS",
            "$25-100",
            "expenses:food:dining",
            0.9,
            "ai",
        )
        # Cache for $0-25 bucket (different account)
        cache_category(
            db,
            "STARBUCKS",
            "$0-25",
            "expenses:food:dining",
            0.85,
            "user",
        )

        categorizer = Categorizer(db)

        # $5.50 -> $0-25 bucket
        results = await categorizer.categorize_batch(
            [_make_txn("STARBUCKS", "5.50")]
        )
        assert results[0].confidence == 0.85

        # $50.00 -> $25-100 bucket
        results = await categorizer.categorize_batch(
            [_make_txn("STARBUCKS", "50.00")]
        )
        assert results[0].confidence == 0.9


# -----------------------------------------------------------------------
# CategorizationPipeline tests (new API with MockAI)
# -----------------------------------------------------------------------


class TestPipelineCacheHits:
    """Test that cache hits skip AI calls entirely."""

    @pytest.mark.asyncio
    async def test_cache_hit_skips_ai(self, db: Database):
        """Cached transactions should not trigger an AI call."""
        cache_category(
            db,
            "WHOLE FOODS",
            "$25-100",
            "expenses:food:groceries",
            0.95,
            "ai",
        )

        mock_ai = MockAI("should not be called")
        pipeline = CategorizationPipeline(ai_provider=mock_ai, db=db)

        results = await pipeline.categorize_batch([_make_txn()])

        assert len(results) == 1
        assert results[0].suggested_account == "expenses:food:groceries"
        assert results[0].confidence == 0.95
        assert mock_ai.call_count == 0  # AI was never called

    @pytest.mark.asyncio
    async def test_uncached_items_sent_to_ai(self, db: Database):
        """Uncached transactions should be sent to AI."""
        ai_response = json.dumps(
            [
                {
                    "id": 0,
                    "account": "expenses:food:groceries",
                    "confidence": 0.92,
                    "reasoning": "Grocery store",
                    "alternatives": ["expenses:shopping:general"],
                }
            ]
        )
        mock_ai = MockAI(ai_response)
        pipeline = CategorizationPipeline(ai_provider=mock_ai, db=db)

        results = await pipeline.categorize_batch([_make_txn()])

        assert len(results) == 1
        assert results[0].suggested_account == "expenses:food:groceries"
        assert results[0].confidence == 0.92
        assert mock_ai.call_count == 1

    @pytest.mark.asyncio
    async def test_ai_results_are_cached_in_pipeline(self, db: Database):
        """Pipeline caches AI results for future lookups."""
        ai_response = json.dumps(
            [
                {
                    "id": 0,
                    "account": "expenses:subscriptions",
                    "confidence": 0.9,
                    "reasoning": "Streaming",
                    "alternatives": [],
                }
            ]
        )
        mock_ai = MockAI(ai_response)
        pipeline = CategorizationPipeline(ai_provider=mock_ai, db=db)

        await pipeline.categorize_batch([_make_txn("NETFLIX", "15.99")])

        # Verify it's cached
        cached = lookup_category(db, "NETFLIX", "$0-25")
        assert cached is not None
        assert cached.account == "expenses:subscriptions"
        assert cached.source == "ai"

    @pytest.mark.asyncio
    async def test_mixed_cache_and_ai(self, db: Database):
        """Pipeline handles mix of cached and uncached."""
        cache_category(
            db,
            "STARBUCKS",
            "$0-25",
            "expenses:food:dining",
            0.88,
            "ai",
        )

        ai_response = json.dumps(
            [
                {
                    "id": 0,
                    "account": "expenses:food:groceries",
                    "confidence": 0.91,
                    "reasoning": "Grocery store",
                    "alternatives": [],
                }
            ]
        )
        mock_ai = MockAI(ai_response)
        pipeline = CategorizationPipeline(ai_provider=mock_ai, db=db)

        txns = [
            _make_txn("STARBUCKS", "5.50"),
            _make_txn("WHOLE FOODS", "85.42"),
        ]
        results = await pipeline.categorize_batch(txns)

        assert len(results) == 2
        # First from cache
        assert results[0].suggested_account == "expenses:food:dining"
        assert results[0].confidence == 0.88
        # Second from AI
        assert results[1].suggested_account == "expenses:food:groceries"
        assert results[1].confidence == 0.91
        assert mock_ai.call_count == 1


class TestPipelineErrorHandling:
    """Test graceful handling of AI failures."""

    @pytest.mark.asyncio
    async def test_invalid_json_response(self, db: Database):
        """Invalid JSON from AI produces fallback results."""
        mock_ai = MockAI("This is not valid JSON at all!")
        pipeline = CategorizationPipeline(ai_provider=mock_ai, db=db)

        results = await pipeline.categorize_batch([_make_txn()])

        assert len(results) == 1
        assert results[0].suggested_account == "expenses:miscellaneous"
        assert results[0].confidence == 0.0

    @pytest.mark.asyncio
    async def test_empty_json_array(self, db: Database):
        """Empty JSON array from AI still fills all results."""
        mock_ai = MockAI("[]")
        pipeline = CategorizationPipeline(ai_provider=mock_ai, db=db)

        results = await pipeline.categorize_batch([_make_txn()])

        assert len(results) == 1
        # Fills with fallback since no AI result matched
        assert results[0].suggested_account == "expenses:miscellaneous"
        assert results[0].confidence == 0.0

    @pytest.mark.asyncio
    async def test_no_db_still_works(self):
        """Pipeline works without a database (no caching)."""
        ai_response = json.dumps(
            [
                {
                    "id": 0,
                    "account": "expenses:food:groceries",
                    "confidence": 0.85,
                    "reasoning": "Grocery",
                    "alternatives": [],
                }
            ]
        )
        mock_ai = MockAI(ai_response)
        pipeline = CategorizationPipeline(ai_provider=mock_ai, db=None)

        results = await pipeline.categorize_batch([_make_txn()])

        assert len(results) == 1
        assert results[0].suggested_account == "expenses:food:groceries"


class TestPipelineCorrections:
    """Test user correction recording via pipeline."""

    def test_record_correction(self, db: Database):
        """Pipeline records corrections in the DB."""
        mock_ai = MockAI("{}")
        pipeline = CategorizationPipeline(ai_provider=mock_ai, db=db)

        pipeline.record_user_correction(
            "AMZN", "expenses:shopping:general", "expenses:office"
        )

        count = get_corrections_count(db, "AMZN")
        assert count == 1

    def test_auto_promote_at_threshold(self, db: Database):
        """After PROMOTION_THRESHOLD corrections, auto-promote."""
        mock_ai = MockAI("{}")
        pipeline = CategorizationPipeline(ai_provider=mock_ai, db=db)

        for _ in range(pipeline.PROMOTION_THRESHOLD):
            pipeline.record_user_correction(
                "AMZN", "expenses:shopping:general", "expenses:office"
            )

        cached = lookup_category(db, "AMZN", "$0-25")
        assert cached is not None
        assert cached.account == "expenses:office"
        assert cached.confidence == 1.0
        assert cached.source == "user"

    def test_no_promote_below_threshold(self, db: Database):
        """Below threshold corrections do not auto-promote."""
        mock_ai = MockAI("{}")
        pipeline = CategorizationPipeline(ai_provider=mock_ai, db=db)

        for _ in range(pipeline.PROMOTION_THRESHOLD - 1):
            pipeline.record_user_correction(
                "TARGET", "expenses:shopping:general", "expenses:shopping:clothing"
            )

        cached = lookup_category(db, "TARGET", "$0-25")
        assert cached is None

    def test_correction_without_db(self):
        """Corrections without a DB are silently ignored."""
        mock_ai = MockAI("{}")
        pipeline = CategorizationPipeline(ai_provider=mock_ai, db=None)
        # Should not raise
        pipeline.record_user_correction(
            "AMZN", "expenses:shopping:general", "expenses:office"
        )
