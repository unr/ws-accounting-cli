"""Linear step indicator for the CSV import wizard."""

from textual.widgets import Static


class ImportStepper(Static):
    """1-row horizontal step indicator for the import wizard.

    Displays: [done] File  -->  [done] Structure  -->  [current] Preview  -->  [ ] Import
    """

    DEFAULT_CSS = """
    ImportStepper {
        height: 1;
        padding: 0 1;
        color: $text-muted;
    }
    """

    STEPS = ["File", "Structure", "Preview", "Import"]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._current = 0

    def on_mount(self) -> None:
        self._refresh_steps()

    def set_step(self, step: int) -> None:
        """Set the current step (0-indexed)."""
        self._current = max(0, min(step, len(self.STEPS) - 1))
        self._refresh_steps()

    def _refresh_steps(self) -> None:
        parts = []
        for i, name in enumerate(self.STEPS):
            if i < self._current:
                parts.append(f"[\u2713] {name}")
            elif i == self._current:
                parts.append(f"[\u25cf] {name}")
            else:
                parts.append(f"[ ] {name}")
        self.update("  \u2500\u2500>  ".join(parts))
