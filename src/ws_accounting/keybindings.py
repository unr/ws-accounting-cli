"""Vim-lite keyboard navigation for all screens."""

from textual.widgets import Input, TextArea, Select

# Widgets that consume printable keys (navigation disabled when focused)
INPUT_WIDGETS = (Input, TextArea, Select)


class VimNavigationMixin:
    """Mixin for screens to support vim-style navigation with Escape bridge."""

    def _is_navigating(self) -> bool:
        """True when no input widget has focus -- safe for vim keys."""
        focused = self.focused  # type: ignore[attr-defined]
        if focused is None:
            return True
        return not isinstance(focused, INPUT_WIDGETS)

    def _focus_primary_widget(self) -> None:
        """Override in each screen to focus the main navigable widget."""
        pass

    def action_escape_to_nav(self) -> None:
        """Defocus input widgets and return to primary navigation widget."""
        focused = self.focused  # type: ignore[attr-defined]
        if focused and isinstance(focused, INPUT_WIDGETS):
            focused.blur()  # type: ignore[attr-defined]
        self._focus_primary_widget()


# Help text constants for the ? overlay
GLOBAL_HELP = """
# Global Shortcuts

| Key | Action |
|-----|--------|
| Ctrl+1-7 | Switch screen |
| Ctrl+P / : | Command palette |
| ? | Help (this screen) |
| q | Quit |
| Escape | Return to navigation |
"""

TABLE_HELP = """
# List Navigation

| Key | Action |
|-----|--------|
| j / Down | Move down |
| k / Up | Move up |
| Home | First item |
| End / G | Last item |
| Ctrl+D | Page down |
| Ctrl+U | Page up |
| Enter / o | Open detail |
| Space | Toggle selection |
"""

TREE_HELP = """
# Tree Navigation

| Key | Action |
|-----|--------|
| j / Down | Next node |
| k / Up | Previous node |
| h / Left | Collapse / parent |
| l / Right | Expand / first child |
| Space | Toggle expand |
| Enter | Select node |
"""

TAB_HELP = """
# Tab Navigation

| Key | Action |
|-----|--------|
| h / [ | Previous tab |
| l / ] | Next tab |
| 1-4 | Jump to tab N |
"""
