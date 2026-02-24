"""Main Textual application."""

from textual.app import App
from textual.widgets import Footer, Static


class WsAccountingApp(App):
    """ws-accounting TUI personal finance manager."""

    TITLE = "ws-accounting"
    CSS = """
    Screen {
        align: center middle;
    }
    #welcome {
        width: auto;
        height: auto;
        padding: 2 4;
        border: heavy $primary;
        text-align: center;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
    ]

    def compose(self):
        yield Static(
            "ws-accounting v0.1.0\n\nPersonal finance manager\nPowered by hledger + Textual",
            id="welcome",
        )
        yield Footer()
