"""AI provider protocol and Claude implementation."""

from __future__ import annotations

import os
from typing import AsyncIterator, Protocol, runtime_checkable


@runtime_checkable
class AIProvider(Protocol):
    """Protocol for AI providers -- allows swapping Claude for other models."""

    async def complete(self, prompt: str, system: str = "") -> str:
        """Get a completion from the AI model."""
        ...

    async def stream(self, prompt: str, system: str = "") -> AsyncIterator[str]:
        """Stream a completion token by token."""
        ...


class ClaudeProvider:
    """Anthropic Claude API provider with lazy client initialization."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 4096,
    ) -> None:
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.model = model
        self.max_tokens = max_tokens
        self._client = None

    @property
    def is_configured(self) -> bool:
        """Return True if an API key is available."""
        return bool(self.api_key)

    def _get_client(self):
        """Lazy-init the Anthropic async client."""
        if not self.is_configured:
            raise RuntimeError("Anthropic API key not configured")
        if self._client is None:
            import anthropic

            self._client = anthropic.AsyncAnthropic(api_key=self.api_key)
        return self._client

    async def complete(self, prompt: str, system: str = "") -> str:
        """Send a prompt to Claude and return the completion text."""
        client = self._get_client()
        kwargs: dict = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system

        response = await client.messages.create(**kwargs)
        return response.content[0].text

    async def stream(self, prompt: str, system: str = "") -> AsyncIterator[str]:
        """Stream a completion token by token."""
        client = self._get_client()
        kwargs: dict = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system

        async with client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield text
