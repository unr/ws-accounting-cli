"""AI-powered financial insights and narrative analysis."""

from __future__ import annotations

from decimal import Decimal

from ws_accounting.ai.client import AIProvider
from ws_accounting.ai.privacy import sanitize
from ws_accounting.ai.prompts import (
    SYSTEM_INSIGHTS,
    build_insights_prompt,
    custom_query_prompt,
    insights_prompt,
)
from ws_accounting.core.hledger import HLedgerGateway
from ws_accounting.db.database import Database
from ws_accounting.db.queries import (
    cache_insights,
    get_cached_insights,
)


# ---------------------------------------------------------------------------
# InsightsEngine (new API -- context-dict based)
# ---------------------------------------------------------------------------


class InsightsEngine:
    """Generates financial insights using AI with a simple context-dict API."""

    def __init__(
        self,
        ai_provider: AIProvider,
        db: Database | None = None,
    ) -> None:
        self.ai = ai_provider
        self.db = db

    async def generate_summary(
        self,
        period: str,
        income: Decimal,
        expenses: Decimal,
        by_category: dict[str, Decimal],
    ) -> str:
        """Generate a monthly spending summary.

        Checks the insights cache first and caches the result.
        """
        # Check cache first
        if self.db:
            cached = get_cached_insights(self.db, period)
            if cached:
                return cached.content

        context = {
            "period": period,
            "income": f"${income:,.2f}",
            "expenses": f"${expenses:,.2f}",
            "by_category": {k: f"${v:,.2f}" for k, v in by_category.items()},
        }

        prompt = insights_prompt(context)
        response = await self.ai.complete(prompt, system=SYSTEM_INSIGHTS)

        # Cache the response
        if self.db:
            cache_insights(self.db, period, response, "claude")

        return response

    async def answer_query(
        self,
        query: str,
        period: str,
        income: Decimal,
        expenses: Decimal,
        by_category: dict[str, Decimal],
    ) -> str:
        """Answer a custom financial question."""
        context = {
            "period": period,
            "income": f"${income:,.2f}",
            "expenses": f"${expenses:,.2f}",
            "by_category": {k: f"${v:,.2f}" for k, v in by_category.items()},
        }
        prompt = custom_query_prompt(sanitize(query), context)
        return await self.ai.complete(prompt, system=SYSTEM_INSIGHTS)

    async def stream_response(
        self,
        query: str,
        period: str,
        income: Decimal,
        expenses: Decimal,
        by_category: dict[str, Decimal],
    ):
        """Stream a response token by token for the UI."""
        context = {
            "period": period,
            "income": f"${income:,.2f}",
            "expenses": f"${expenses:,.2f}",
            "by_category": {k: f"${v:,.2f}" for k, v in by_category.items()},
        }
        prompt = custom_query_prompt(sanitize(query), context)
        async for token in self.ai.stream(prompt, system=SYSTEM_INSIGHTS):
            yield token


# ---------------------------------------------------------------------------
# InsightsGenerator (original API -- hledger-gateway based)
# ---------------------------------------------------------------------------


class InsightsGenerator:
    """Generate AI-powered financial narrative insights (legacy API)."""

    def __init__(
        self,
        gateway: HLedgerGateway,
        db: Database,
        provider: AIProvider | None = None,
    ) -> None:
        self.gateway = gateway
        self.db = db
        self.provider = provider

    async def generate(
        self,
        period: str,
        force_refresh: bool = False,
    ) -> str:
        """Generate insights for a period.

        Returns markdown string with analysis sections.
        """
        # Check cache first
        if not force_refresh:
            cached = get_cached_insights(self.db, period)
            if cached:
                return cached.content

        if not self.provider:
            return (
                "AI insights require an API key. "
                "Configure one in Settings."
            )

        # Gather financial context
        context = await self._gather_context(period)

        # Build prompt and call AI
        prompt = build_insights_prompt(**context)
        result = await self.provider.complete(prompt)

        # Cache result
        cache_insights(self.db, period, result, "claude")

        return result

    async def _gather_context(self, period: str) -> dict:
        """Gather financial data for the insights prompt.

        Each query is wrapped in a try/except so partial data
        still produces useful insights.
        """
        context: dict[str, str] = {}

        try:
            context["income_statement"] = await self.gateway.income_statement(period)
        except Exception:
            context["income_statement"] = "Not available"

        try:
            context["prev_income_statement"] = await self.gateway.income_statement(
                _prev_period(period)
            )
        except Exception:
            context["prev_income_statement"] = "Not available"

        try:
            context["expense_trends"] = await self.gateway.balance(
                accounts=["expenses"],
                period=f"monthly from 3 months ago to {period}",
            )
        except Exception:
            context["expense_trends"] = "Not available"

        try:
            context["large_transactions"] = await self.gateway.register(
                query="amt:>200", period=period
            )
        except Exception:
            context["large_transactions"] = "Not available"

        try:
            context["budget_status"] = await self.gateway.balance(
                budget=True, period=period
            )
        except Exception:
            context["budget_status"] = "Not available"

        return context


def _prev_period(period: str) -> str:
    """Given a 'YYYY-MM' period, return the previous month."""
    try:
        parts = period.split("-")
        year, month = int(parts[0]), int(parts[1])
        if month == 1:
            return f"{year - 1}-12"
        return f"{year}-{month - 1:02d}"
    except (ValueError, IndexError):
        return period
