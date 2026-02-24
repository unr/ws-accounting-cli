"""AI confidence indicator badge."""

from textual.widgets import Static


class ConfidenceBadge(Static):
    """Displays AI categorization confidence with icon + text label."""

    DEFAULT_CSS = """
    ConfidenceBadge {
        width: auto;
        height: 1;
    }
    """

    def __init__(self, confidence: float = 0.0, **kwargs) -> None:
        super().__init__(**kwargs)
        self._confidence = confidence

    def on_mount(self) -> None:
        self._render()

    def set_confidence(self, confidence: float) -> None:
        self._confidence = confidence
        self._render()

    def _render(self) -> None:
        self.remove_class("confidence--high", "confidence--medium", "confidence--low")
        if self._confidence >= 0.8:
            icon = "\u2713"
            self.add_class("confidence--high")
        elif self._confidence >= 0.5:
            icon = "?"
            self.add_class("confidence--medium")
        else:
            icon = "??"
            self.add_class("confidence--low")
        self.update(f"{icon} {self._confidence:.0%}")
