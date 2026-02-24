# CLAUDE.md

## Commands

- **Run app**: `uv run ws-accounting`
- **Run tests**: `uv run pytest`
- **Run single test file**: `uv run pytest tests/test_models.py`
- **Lint**: `uv run ruff check src/`
- **Format**: `uv run ruff format src/`
- **Dev live reload**: `uv run textual-dev run ws_accounting.app:WsAccountingApp`

## Architecture

- `src/ws_accounting/` — Main package (src layout)
- `app.py` — Textual App with MODES for screen management (not push_screen)
- `screens/` — One screen per mode (dashboard, transactions, csv_import, budgets, reports, insights, accounts, settings, onboarding)
- `widgets/` — Reusable Textual widgets (transaction_table, summary_card, budget_bar, etc.)
- `core/` — Framework-agnostic domain logic (hledger gateway, models, parser, journal, budget, csv_import)
- `ai/` — Claude API integration (categorizer, insights, privacy filtering, prompts)
- `db/` — SQLite sidecar (database manager, queries, migrations)
- `config/` — Pydantic AppConfig with TOML persistence, XDG paths via platformdirs
- `styles/` — TCSS files per screen, uses `:dark`/`:light` selectors
- `keybindings.py` — VimNavigationMixin, INPUT_WIDGETS tuple, help text constants
- `theme.py` — Accessible financial-dark/financial-light themes (blue/orange, not red/green)

## Key Patterns

- **Screens are MODES** — `switch_mode()`, not `push_screen()`. Each mode has its own screen stack.
- **`_resolve_conn()`** — All db query functions accept both `Database` objects and raw `sqlite3.Connection`
- **Monetary values** — Always `Decimal` in Python, `TEXT` in SQLite, never float/REAL
- **hledger interaction** — All via `HLedgerGateway` async subprocess calls with JSON output
- **Workers** — `@work(exclusive=True)` for cancellable operations (search, period changes)
- **Loading states** — `.loading = True` on widgets during data fetch, always unset in `finally`

## Code Style

- Python 3.13+, ruff for lint/format, 100 char line length
- Frozen dataclasses for domain models (`core/models.py`)
- Pydantic BaseModel for config
- Component CSS classes for styling (`.amount--positive`, `.amount--negative`, `.confidence--high`)
