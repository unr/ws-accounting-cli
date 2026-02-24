"""Autocomplete category/account picker widget."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Input, OptionList
from textual.widgets.option_list import Option

from ws_accounting.config.defaults import ALL_DEFAULT_ACCOUNTS


def _fuzzy_match(query: str, candidate: str) -> bool:
    """Simple fuzzy match: all query chars appear in order in candidate."""
    query = query.lower()
    candidate = candidate.lower()
    # First check simple substring
    if query in candidate:
        return True
    # Then check fuzzy char-by-char
    qi = 0
    for ch in candidate:
        if qi < len(query) and ch == query[qi]:
            qi += 1
    return qi == len(query)


def _match_score(query: str, candidate: str) -> int:
    """Score a match: lower is better. Prefix match scores highest."""
    q = query.lower()
    c = candidate.lower()
    if c.startswith(q):
        return 0
    # Check if any segment starts with query
    for segment in c.split(":"):
        if segment.startswith(q):
            return 1
    if q in c:
        return 2
    return 3


class CategoryPicker(Widget):
    """Input with dropdown autocomplete for account/category selection."""

    DEFAULT_CSS = """
    CategoryPicker {
        height: auto;
        width: 1fr;
    }
    CategoryPicker #category-input {
        width: 1fr;
    }
    CategoryPicker #category-options {
        max-height: 10;
        display: none;
        border: round $primary;
        width: 1fr;
    }
    CategoryPicker #category-options.visible {
        display: block;
    }
    """

    value: reactive[str] = reactive("")

    class CategorySelected(Message):
        """Emitted when a category is confirmed."""

        def __init__(self, category: str) -> None:
            self.category = category
            super().__init__()

    def __init__(
        self,
        categories: list[str] | None = None,
        placeholder: str = "Type to search accounts...",
        **kwargs,
    ) -> None:
        self._categories = categories or list(ALL_DEFAULT_ACCOUNTS)
        self._placeholder = placeholder
        super().__init__(**kwargs)

    def compose(self) -> ComposeResult:
        yield Input(
            placeholder=self._placeholder,
            id="category-input",
        )
        yield OptionList(id="category-options")

    def on_mount(self) -> None:
        """Populate the option list with all categories initially."""
        self._update_options("")

    def on_input_changed(self, event: Input.Changed) -> None:
        """Filter options as user types."""
        if event.input.id != "category-input":
            return
        query = event.value.strip()
        self._update_options(query)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Confirm the current input value or highlighted option."""
        if event.input.id != "category-input":
            return
        option_list = self.query_one("#category-options", OptionList)
        # If an option is highlighted, use that
        if (
            option_list.has_class("visible")
            and option_list.highlighted is not None
        ):
            opt = option_list.get_option_at_index(
                option_list.highlighted
            )
            self._select_category(str(opt.prompt))
        elif event.value.strip():
            self._select_category(event.value.strip())

    def on_option_list_option_selected(
        self, event: OptionList.OptionSelected
    ) -> None:
        """Handle click/enter on an option."""
        if event.option_list.id != "category-options":
            return
        self._select_category(str(event.option.prompt))

    def _select_category(self, category: str) -> None:
        """Set the selected category and emit message."""
        self.value = category
        inp = self.query_one("#category-input", Input)
        inp.value = category
        option_list = self.query_one("#category-options", OptionList)
        option_list.remove_class("visible")
        self.post_message(self.CategorySelected(category))

    def _update_options(self, query: str) -> None:
        """Update the dropdown options based on the query."""
        option_list = self.query_one("#category-options", OptionList)
        option_list.clear_options()

        if not query:
            # Show all categories when empty
            for cat in self._categories[:20]:
                option_list.add_option(Option(cat))
            if self._categories:
                option_list.add_class("visible")
            else:
                option_list.remove_class("visible")
            return

        # Filter and sort by match quality
        matches: list[tuple[int, str]] = []
        for cat in self._categories:
            if _fuzzy_match(query, cat):
                score = _match_score(query, cat)
                matches.append((score, cat))

        matches.sort(key=lambda x: (x[0], x[1]))

        if matches:
            for _score, cat in matches[:15]:
                option_list.add_option(Option(cat))
            option_list.add_class("visible")
        else:
            option_list.remove_class("visible")

    def set_value(self, value: str) -> None:
        """Programmatically set the input value."""
        self.value = value
        try:
            inp = self.query_one("#category-input", Input)
            inp.value = value
        except Exception:
            pass
