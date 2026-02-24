"""Confidence badge widget for AI categorization results."""

from __future__ import annotations

from textual.widgets import Static


class ConfidenceBadge(Static):
    """Display AI confidence level with accessible icon + text.

    Confidence thresholds (not color-only for accessibility):
        High (>85%):   checkmark + account name (default color)
        Medium (50-85%): ? + account name (accent color)
        Low (<50%):    ?? + account name (warning color + bold)
    """

    DEFAULT_CSS = """
    ConfidenceBadge {
        width: auto;
        height: 1;
    }
    ConfidenceBadge.confidence-high {
        color: $success;
    }
    ConfidenceBadge.confidence-medium {
        color: $accent;
    }
    ConfidenceBadge.confidence-low {
        color: $warning;
        text-style: bold;
    }
    """

    def __init__(
        self,
        account: str = "",
        confidence: float = 0.0,
        **kwargs,
    ) -> None:
        self._account = account
        self._confidence = confidence
        super().__init__(**kwargs)

    def on_mount(self) -> None:
        """Render the badge on mount."""
        self._update_display()

    def set_confidence(
        self, account: str, confidence: float
    ) -> None:
        """Update the displayed account and confidence level."""
        self._account = account
        self._confidence = confidence
        self._update_display()

    def _update_display(self) -> None:
        """Re-render the badge text and CSS class."""
        self.remove_class(
            "confidence-high",
            "confidence-medium",
            "confidence-low",
        )

        if self._confidence > 0.85:
            icon = "ok"
            self.add_class("confidence-high")
            pct = f"{self._confidence:.0%}"
        elif self._confidence >= 0.50:
            icon = "?"
            self.add_class("confidence-medium")
            pct = f"{self._confidence:.0%}"
        else:
            icon = "??"
            self.add_class("confidence-low")
            pct = f"{self._confidence:.0%}"

        self.update(f"[{icon}] {self._account} ({pct})")
