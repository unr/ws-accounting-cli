# ws-accounting

A keyboard-driven personal finance TUI built with [Textual](https://textual.textualize.io/) and [hledger](https://hledger.org/). Runs in your terminal and browser.

Plain-text accounting meets a modern interface: import bank CSVs, track budgets, view reports with charts, and get AI-powered transaction categorization — all without leaving the terminal.

## Features

- **Dashboard** — net worth, monthly income/expenses, budget status, recent transactions at a glance
- **Transactions** — searchable list with vim-style navigation (j/k/gg/G), split editing, review workflow
- **CSV Import** — 4-step wizard with auto-detection, AI categorization, duplicate/transfer detection
- **Budgets** — category tracking with rollover, savings goals, upcoming recurring bills
- **Reports** — net worth, spending breakdown, cash flow, period comparison (plotext charts)
- **AI Insights** — Claude-powered spending analysis with caching and offline fallback
- **Accounts** — hierarchical tree view with reconciliation support
- **Settings** — journal path, AI config, import rules, theme toggle
- **Onboarding** — first-run wizard for hledger setup, journal creation, sample data

### Design Principles

- **Privacy-first** — all data stays local in plain-text hledger journals + SQLite sidecar
- **Accessible** — blue/orange color scheme (not red/green), all color-coded info has text/icon indicators
- **Keyboard-driven** — modifier keys for navigation (Ctrl+1-7), vim bindings in tables, command shortcuts
- **Offline capable** — AI features are optional; everything else works without an API key

## Requirements

- Python 3.12+
- [hledger](https://hledger.org/install.html) 1.30+ (for the accounting backend)
- Optional: [Anthropic API key](https://console.anthropic.com/) for AI categorization and insights

## Installation

```bash
# Clone the repository
git clone https://github.com/your-username/ws-accounting-cli.git
cd ws-accounting-cli

# Install with uv (recommended)
uv sync

# Or with pip
pip install -e .
```

## Usage

```bash
# Run in terminal
ws-accounting

# Run in browser
ws-accounting --web

# Show version
ws-accounting --version
```

On first launch, the onboarding wizard walks you through hledger setup, journal creation, and optional sample data loading.

## Keyboard Shortcuts

### Global Navigation

| Key | Action |
|-----|--------|
| `Ctrl+1` | Dashboard |
| `Ctrl+2` | Transactions |
| `Ctrl+3` | CSV Import |
| `Ctrl+4` | Budgets |
| `Ctrl+5` | Reports |
| `Ctrl+6` | AI Insights |
| `Ctrl+7` | Accounts |
| `?` | Help overlay |
| `n` | New transaction |
| `/` | Focus search |
| `q` | Quit |

### Transaction Table

| Key | Action |
|-----|--------|
| `j` / `k` | Move down / up |
| `gg` / `G` | Jump to top / bottom |
| `Enter` | Open detail modal |
| `Space` | Toggle selection |
| `a` | Accept (mark reviewed) |

## Project Structure

```
src/ws_accounting/
├── app.py                 # Main Textual app, screen registry, keybindings
├── theme.py               # Accessible financial themes (dark + light)
├── config/                # Settings (Pydantic + TOML), XDG paths, defaults
├── core/                  # hledger gateway, domain models, journal I/O, CSV import, budget math
├── ai/                    # Claude API client, privacy sanitizer, categorizer, insights
├── db/                    # SQLite manager, migrations, queries
├── screens/               # 9 Textual screens (dashboard, transactions, csv_import, ...)
├── widgets/               # 11 reusable widgets (transaction table, budget bar, ...)
├── styles/                # TCSS stylesheets
└── data/                  # Default accounts, sample journal, sample import rules
```

## Development

```bash
# Install dev dependencies
uv sync --extra dev

# Run tests
uv run pytest tests/ -x -q

# Lint
uv run ruff check src/ tests/

# Launch with Textual dev tools
uv run textual run --dev ws_accounting.app:WSAccountingApp
```

## Configuration

Config is stored in `~/.config/ws-accounting/config.toml` (XDG). Key settings:

- `journal_path` — path to your hledger journal
- `currency` — default commodity (e.g., `$`, `EUR`)
- `theme` — `financial-dark` or `financial-light`
- `ai.api_key` — Anthropic API key for AI features
- `ai.enabled` — toggle AI on/off

The SQLite sidecar database lives at `~/.local/share/ws-accounting/metadata.db` and stores budgets, goals, import history, categorization cache, and insights cache.

## Tech Stack

| Component | Technology |
|-----------|-----------|
| TUI framework | [Textual](https://textual.textualize.io/) (terminal + web via `textual serve`) |
| Accounting | [hledger](https://hledger.org/) (plain-text, double-entry) |
| AI | [Anthropic Claude API](https://docs.anthropic.com/) |
| Config | [Pydantic](https://docs.pydantic.dev/) + TOML |
| Charts | [textual-plotext](https://github.com/Textualize/textual-plotext) |
| Database | SQLite (WAL mode, TEXT for monetary values) |
| Paths | [platformdirs](https://github.com/tox-dev/platformdirs) (XDG) |

## License

MIT
