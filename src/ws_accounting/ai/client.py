"""AI provider abstraction -- protocol + Claude implementation."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import anthropic


@runtime_checkable
class AIProvider(Protocol):
    """Protocol for AI providers (Claude, future: OpenRouter, etc.)."""

    async def complete(
        self, prompt: str, system: str | None = None
    ) -> str:
        """Send a prompt and return the completion text."""
        ...


class ClaudeProvider:
    """Claude API provider using the Anthropic SDK."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-5-20250929",
        max_tokens: int = 4096,
    ) -> None:
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens

    async def complete(
        self, prompt: str, system: str | None = None
    ) -> str:
        """Send a prompt to Claude and return the completion text."""
        kwargs: dict = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system

        response = await self.client.messages.create(**kwargs)
        return response.content[0].text
