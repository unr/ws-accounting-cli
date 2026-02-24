"""CLI entry point for ws-accounting."""

import argparse
import sys


def main() -> None:
    """Run the ws-accounting TUI application."""
    parser = argparse.ArgumentParser(prog="ws-accounting")
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Reset config and database, then re-run onboarding",
    )
    args = parser.parse_args()

    if args.fresh:
        from ws_accounting.config.paths import get_config_file, get_db_path

        for path in (get_config_file(), get_db_path()):
            if path.exists():
                path.unlink()
                print(f"Removed {path}")

    from ws_accounting.app import WsAccountingApp

    app = WsAccountingApp()
    app.run()


if __name__ == "__main__":
    main()
