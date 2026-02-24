"""Headless screenshot tool for ws-accounting screens.

Usage:
    uv run python dev/screenshot.py dashboard
    uv run python dev/screenshot.py transactions --size 120x40
    uv run python dev/screenshot.py --all
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

SCREENS = [
    "dashboard",
    "transactions",
    "csv_import",
    "budgets",
    "reports",
    "insights",
    "accounts",
    "settings",
]

OUTPUT_DIR = Path(__file__).parent / "screenshots"


async def take_screenshot(
    screen_name: str, width: int = 100, height: int = 36
) -> Path:
    """Boot the app headlessly on a specific screen and save an SVG."""
    from ws_accounting.app import WsAccountingApp

    # Patch the default mode so the app starts directly on the target screen
    original_mode = WsAccountingApp.DEFAULT_MODE
    WsAccountingApp.DEFAULT_MODE = screen_name
    try:
        app = WsAccountingApp()
        app._config.first_run = False

        async with app.run_test(headless=True, size=(width, height)) as pilot:
            await pilot.pause()
            await pilot.pause()  # Extra pause for async workers

            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            svg = app.export_screenshot()
            out_path = OUTPUT_DIR / f"{screen_name}.svg"
            out_path.write_text(svg)
            print(f"  {screen_name} -> {out_path}")
            return out_path
    finally:
        WsAccountingApp.DEFAULT_MODE = original_mode


async def screenshot_all(width: int, height: int) -> None:
    """Screenshot every screen sequentially."""
    print(f"Taking screenshots at {width}x{height}...")
    failed = []
    for name in SCREENS:
        try:
            await take_screenshot(name, width, height)
        except Exception as exc:
            failed.append((name, str(exc)))
            print(f"  {name} -> FAILED: {exc}")
    total = len(SCREENS)
    ok = total - len(failed)
    print(f"Done. {ok}/{total} screenshots in {OUTPUT_DIR}/")
    if failed:
        print("Failed:")
        for name, err in failed:
            print(f"  {name}: {err}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Screenshot ws-accounting screens")
    parser.add_argument("screen", nargs="?", choices=SCREENS, help="Screen to capture")
    parser.add_argument("--all", action="store_true", help="Capture all screens")
    parser.add_argument(
        "--size", default="100x36", help="Terminal size as WIDTHxHEIGHT (default: 100x36)"
    )
    args = parser.parse_args()

    if not args.screen and not args.all:
        parser.error("Provide a screen name or --all")

    w, h = (int(x) for x in args.size.split("x"))

    if args.all:
        asyncio.run(screenshot_all(w, h))
    else:
        asyncio.run(take_screenshot(args.screen, w, h))


if __name__ == "__main__":
    main()
