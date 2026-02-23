"""CLI entry point for ws-accounting."""

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="ws-accounting",
        description="Personal finance TUI built with Textual + hledger",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {_get_version()}",
    )
    parser.add_argument(
        "--web",
        action="store_true",
        help="Launch in web mode via textual serve",
    )
    args = parser.parse_args()

    if args.web:
        _run_web()
    else:
        _run_tui()


def _get_version() -> str:
    from ws_accounting import __version__

    return __version__


def _run_tui() -> None:
    from ws_accounting.app import WSAccountingApp

    app = WSAccountingApp()
    app.run()


def _run_web() -> None:
    import subprocess

    subprocess.run(
        [sys.executable, "-m", "textual", "serve", "ws_accounting.app:WSAccountingApp"],
        check=True,
    )


if __name__ == "__main__":
    main()
