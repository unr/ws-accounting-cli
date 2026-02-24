"""CLI entry point for ws-accounting."""

from ws_accounting.app import WsAccountingApp


def main() -> None:
    """Run the ws-accounting TUI application."""
    app = WsAccountingApp()
    app.run()


if __name__ == "__main__":
    main()
