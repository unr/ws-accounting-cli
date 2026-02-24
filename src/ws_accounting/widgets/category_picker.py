"""Autocomplete category selector for transaction categorization."""

from textual.widgets import Input

from ws_accounting.config.defaults import DEFAULT_CATEGORIES


class CategoryPicker(Input):
    """Input with autocomplete for account categories."""

    DEFAULT_CSS = """
    CategoryPicker {
        height: 1;
    }
    """

    def __init__(self, categories: list[str] | None = None, **kwargs) -> None:
        self._categories = categories or DEFAULT_CATEGORIES
        kwargs.setdefault("placeholder", "Type to search categories...")
        super().__init__(**kwargs)

    @property
    def categories(self) -> list[str]:
        return self._categories
