# ws-accounting

A terminal-based personal finance manager built with [Textual](https://textual.textualize.io/) and [hledger](https://hledger.org/).

Plain-text accounting with AI-powered categorization, interactive budgets, and rich reports — all from your terminal (or browser via `textual serve`).

## Features

- **Dashboard** — Net worth, monthly income/expenses, budget status, and recent transactions at a glance
- **Transactions** — Searchable, filterable transaction list with inline editing, splitting, and review workflow
- **CSV Import** — Step-by-step wizard with AI-assisted column detection, duplicate/transfer detection, and batch categorization
- **Budgets** — Category tracking with progress bars, savings goals, and upcoming bills
- **Reports** — Net worth, spending breakdown, cash flow, and period comparisons with terminal charts
- **AI Insights** — Ask questions about your finances, get spending analysis and anomaly detection (Claude API)
- **Accounts** — Tree view with inline balances and reconciliation
- **Vim-style navigation** — `j`/`k`, `/` to search, `Ctrl+1-7` to switch screens

## Prerequisites

- Python 3.13+
- [hledger](https://hledger.org/install.html) 1.51+
- [uv](https://docs.astral.sh/uv/) (recommended)

## Install

```bash
git clone https://github.com/unr/ws-accounting-cli.git
cd ws-accounting-cli
uv sync
```

## Usage

```bash
# Run in terminal
uv run ws-accounting

# Or serve in browser
uv run textual serve ws_accounting.app:WsAccountingApp
```

On first launch, an onboarding wizard walks you through journal setup, currency preferences, and optional AI configuration.

### AI Features (optional)

Copy `.env.example` to `.env` and add your Anthropic API key for AI-powered transaction categorization and financial insights:

```bash
cp .env.example .env
# Edit .env with your key
```

AI features degrade gracefully — everything works without an API key.

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Ctrl+1-7` | Switch between screens |
| `j` / `k` | Navigate up/down in lists |
| `Enter` | Open detail view |
| `/` | Focus search |
| `n` | New transaction |
| `?` | Help overlay |
| `q` | Quit |

## Data Storage

- **Journals** — Plain-text hledger files in `~/finances/` (configurable)
- **Metadata** — SQLite sidecar at `~/.local/share/ws-accounting/metadata.db` for caches, budgets, and settings
- **Config** — TOML file at `~/.config/ws-accounting/config.toml`

All monetary values are stored as text, never floating point.

## Development

```bash
# Install with dev dependencies
uv sync --group dev

# Run tests
uv run pytest

# Lint
uv run ruff check src/

# Live reload during development
uv run textual-dev run ws_accounting.app:WsAccountingApp
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| TUI Framework | Textual 8.x |
| Accounting | hledger (subprocess, JSON output) |
| AI | Claude API via `anthropic` SDK |
| Config | Pydantic + TOML |
| Database | SQLite (sidecar metadata) |
| Charts | textual-plotext |
| Theme | Accessible blue/orange (not red/green) |

## License

MIT
