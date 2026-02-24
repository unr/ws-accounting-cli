"""Linear step indicator widget for multi-step wizards."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static


STEP_INCOMPLETE = "[ ]"
STEP_CURRENT = "[*]"
STEP_COMPLETE = "[x]"
STEP_CONNECTOR = " --> "


class ImportStepper(Widget):
    """A horizontal step indicator showing wizard progress.

    Renders something like:
        [x] Select File --> [*] Map Fields --> [ ] Review --> [ ] Import
    """

    DEFAULT_CSS = """
    ImportStepper {
        height: 3;
        width: 1fr;
        content-align: center middle;
        padding: 1 0;
    }
    ImportStepper #stepper-display {
        width: 1fr;
        text-align: center;
        text-style: bold;
    }
    """

    current_step: reactive[int] = reactive(0)

    class StepChanged(Message):
        """Emitted when the active step changes."""

        def __init__(self, step: int) -> None:
            self.step = step
            super().__init__()

    def __init__(
        self,
        steps: list[str] | None = None,
        **kwargs,
    ) -> None:
        self._steps = steps or [
            "Select File",
            "Map Fields",
            "Review",
            "Import",
        ]
        super().__init__(**kwargs)

    def compose(self) -> ComposeResult:
        yield Static(id="stepper-display")

    def on_mount(self) -> None:
        """Render the initial stepper display."""
        self._render_steps()

    def watch_current_step(self, value: int) -> None:
        """Re-render when step changes."""
        if self.is_mounted:
            self._render_steps()

    def advance(self) -> None:
        """Move to the next step if possible."""
        if self.current_step < len(self._steps) - 1:
            self.current_step += 1
            self.post_message(self.StepChanged(self.current_step))

    def go_back(self) -> None:
        """Move to the previous step if possible."""
        if self.current_step > 0:
            self.current_step -= 1
            self.post_message(self.StepChanged(self.current_step))

    def set_step(self, step: int) -> None:
        """Jump to a specific step."""
        if 0 <= step < len(self._steps):
            self.current_step = step
            self.post_message(self.StepChanged(self.current_step))

    def _render_steps(self) -> None:
        """Build the textual representation of the stepper."""
        parts: list[str] = []
        for i, label in enumerate(self._steps):
            if i < self.current_step:
                marker = STEP_COMPLETE
            elif i == self.current_step:
                marker = STEP_CURRENT
            else:
                marker = STEP_INCOMPLETE
            parts.append(f"{marker} {label}")

        text = STEP_CONNECTOR.join(parts)
        try:
            display = self.query_one("#stepper-display", Static)
            display.update(text)
        except Exception:
            pass
