"""Main Textual application for ws-accounting."""

from textual.app import App, ComposeResult
from textual.widgets import Footer, Header, Static


class WSAccountingApp(App):
    """Personal finance TUI built with Textual + hledger."""

    TITLE = "ws-accounting"
    CSS = """
    Screen {
        align: center middle;
    }

    #welcome {
        width: auto;
        height: auto;
        padding: 2 4;
        border: round $primary;
        text-align: center;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(
            "Welcome to ws-accounting\n\n"
            "Personal finance TUI — powered by hledger\n\n"
            "Press [bold]q[/bold] to quit",
            id="welcome",
        )
        yield Footer()
