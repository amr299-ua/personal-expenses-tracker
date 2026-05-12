# Personal Expenses Tracker

Desktop and CLI application to track personal income and expenses, with local SQLite storage
(optionally encrypted with SQLCipher), interactive charts, multi-format export, and cloud sync.

## Table of contents

- [Features](#features)
- [Tech stack](#tech-stack)
- [Project structure](#project-structure)
- [Requirements](#requirements)
- [Installation](#installation)
- [Quick start](#quick-start)
- [CLI reference](#cli-reference)
- [Security](#security)
- [Building executables](#building-executables)
- [Testing](#testing)
- [License](#license)

## Features

### GUI (Tkinter + ttkbootstrap)
- 4 tabs: Register, Transactions, Statistics, Budgets
- Light/dark theme with 3 color palettes (default, colorblind, dark)
- KPI cards: Balance, Total Income, Total Expense
- Real-time validation with visual indicators
- Keyboard shortcuts (`Ctrl+N`, `Ctrl+F`, `Ctrl+S`, `F5`, `Ctrl+G`, `Ctrl+E`, `Ctrl+1-4`)
- Visual calendar date picker
- Pagination (50 rows per page) and column sorting

### Transactions
- Full CRUD with double-click to edit
- Soft-delete with restore and permanent purge
- Live filters: text search, type, category, date range, tags
- Quick date presets: Today, This Week, This Month, This Year, All
- Multi-currency support with automatic exchange rates (frankfurter.app API)
- Recurring transactions: daily, weekly, monthly, yearly
- Smart auto-categorization based on previous descriptions

### Budgets
- Monthly planning per category
- Budget vs. Actual comparison with visual indicators (OK/Warning/Over)
- Color-coded progress bars

### Charts (8 types)
- Category bars, Monthly evolution line, Distribution pie
- Monthly scatter, 3D bars, Forecast (linear regression)
- Sankey diagram (income → expense flow), Budget comparison
- Interactive: scroll-to-zoom, hover tooltips
- Embedded in GUI and exportable to PNG

### Export (7 formats)
- CSV, Excel (.xlsx with 3 sheets)
- PDF (premium cover + KPI dashboard + trend analysis + 7 charts + paginated tables)
- JSON, YAML, interactive HTML (Plotly), consolidated monthly PDF
- Smart export based on active filters
- Quick export (all formats for latest month)

### Import
- CSV, Excel (.xlsx), JSON with auto-detection
- Automatic column mapping
- Preview before insert

### Security
- SQLCipher AES-256: database encryption at rest
- PIN lock with PBKDF2-HMAC-SHA256 (600k iterations)
- Exponential rate-limiting (3→5s, 4→15s, 5→30s, 6→60s, 7→permanent lockout)
- Weak PIN rejection (rejects `0000`, `1234`, etc.)
- Fernet encryption for backups, cloud sync, and SMTP password
- Private file permissions (600/700 on Unix)
- Dual audit logging: JSONL file + database table

### Cloud Sync
- Providers: WebDAV, Dropbox API v2, Google Drive API
- Encrypted sync (Fernet) before upload
- Conflict detection via metadata timestamp
- Persistent encrypted credential storage across sessions

### Automation
- Background scheduler for reports, backups, and email delivery
- Configurable: daily, weekly (pick day), monthly (pick day of month)
- SMTP with TLS (587) / SSL (465) support, test email button

### Internationalization (i18n)
- 8 languages: English, Español, Français, Deutsch, Italiano, Português, 日本語, العربية
- RTL support for Arabic with `arabic-reshaper` + `python-bidi`
- Regional date and number formatting per locale
- Hot-reload language switching without restart

### CLI
- Full parity with GUI: init-db, add, list, balance, stats, plot, export
- `--currency` flag on add, `--budget-month` on export
- 8 chart types and all export formats

## Tech stack

| Layer | Technology |
|------|------------|
| Language | Python 3.10+ |
| GUI | Tkinter + ttkbootstrap |
| ORM / DB | SQLAlchemy 2.0 + SQLite (+ optional SQLCipher) |
| Migrations | Alembic |
| Validation | Pydantic v2 |
| Charts | Matplotlib + NumPy + Plotly |
| Export | openpyxl, reportlab, PyYAML, CSV/JSON stdlib |
| Security | cryptography (Fernet + PBKDF2), pysqlcipher3, google-auth, dropbox |
| i18n | JSON locales + arabic-reshaper + python-bidi |
| Automation | schedule + smtplib |
| Testing | pytest + pytest-cov + Hypothesis + mypy (strict) + Ruff |
| Build | PyInstaller + uv + hatchling |
| CI/CD | GitHub Actions |

## Project structure

```text
personal-expenses-tracker/
├── .github/workflows/ci.yml
├── alembic/                         # Schema migrations
├── expenses_tracker/
│   ├── __main__.py                  # Entry point (GUI by default, CLI with --cli)
│   ├── gui.py                       # Main window and wiring
│   ├── cli.py                       # Console commands
│   ├── db.py                        # Data layer (CRUD)
│   ├── models.py                    # SQLAlchemy models (6 tables)
│   ├── schemas.py                   # Pydantic validation
│   ├── charts.py                    # Chart generation (8 types)
│   ├── exporters.py                 # Export (7 formats)
│   ├── importers.py                 # Import (CSV/Excel/JSON)
│   ├── security.py                  # SQLCipher, PIN, Fernet, audit
│   ├── cloud_sync.py                # WebDAV, Dropbox, Google Drive
│   ├── automation.py                # Scheduler + email
│   ├── i18n.py                      # Translation engine
│   ├── di.py                        # Dependency injection container
│   ├── theme.py                     # Theme manager (light/dark)
│   ├── utils.py                     # Shared utilities
│   ├── chart_panel.py               # Embedded chart panel
│   ├── chart_viewer.py              # Chart viewer popup
│   ├── gui_dialogs.py               # Dialogs (calendar, chart, PIN)
│   ├── cloud_sync_dialog.py         # Cloud sync configuration dialog
│   ├── automation_dialog.py         # Automation configuration dialog
│   ├── logging_config.py            # Structured logging (JSON + console)
│   ├── services/                    # Business service layer
│   │   ├── transaction_service.py
│   │   ├── database_service.py
│   │   ├── export_service.py
│   │   ├── state_service.py
│   │   ├── category_suggestion_service.py
│   │   └── currency_service.py
│   ├── tabs/                        # GUI tab components
│   │   ├── register_tab.py
│   │   ├── transactions_tab.py
│   │   ├── stats_tab.py
│   │   └── budget_tab.py
│   └── locales/                     # Translation files (8 languages)
│       ├── en.json, es.json, fr.json, de.json, it.json, pt.json, ja.json, ar.json
├── tests/                           # 24 test files, 300+ tests
├── scripts/                         # Build scripts + utilities
│   ├── build_linux.sh, build_macos.sh, build_windows.ps1
│   ├── build_deb.sh, build_rpm.sh
│   └── add_language.py
├── resources/expenses-tracker.desktop
├── pyproject.toml
├── uv.lock
├── run_gui.py                       # Alternative entry point for PyInstaller
├── seed_data.py                     # Test data (500 transactions)
└── CHANGELOG.md
```

## Requirements

- Python 3.10 or higher
- System dependencies: `libsqlcipher-dev`, `python3-tk` (Linux)

## Installation

```bash
git clone https://github.com/amr299-ua/personal-expenses-tracker.git
cd personal-expenses-tracker

# Using uv (recommended)
uv sync

# Or using pip
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Quick start

### GUI (default mode)

```bash
python -m expenses_tracker
# or
python run_gui.py
```

Change language:

```bash
python -m expenses_tracker --lang es
python -m expenses_tracker --list-languages
```

### CLI

```bash
# Initialize database
python -m expenses_tracker --cli init-db

# Add transactions
python -m expenses_tracker --cli add --type income --amount 2500 --category Salary --date 2026-05-11
python -m expenses_tracker --cli add --type expense --amount 120 --category Transport --date 2026-05-11 --currency MXN

# Query
python -m expenses_tracker --cli list --limit 20
python -m expenses_tracker --cli balance
python -m expenses_tracker --cli stats

# Charts and export
python -m expenses_tracker --cli plot --type all --output-dir reports
python -m expenses_tracker --cli export --format all --output-dir reports
```

### Test data

```bash
python seed_data.py
```

## CLI reference

```
python -m expenses_tracker --cli [--db-path PATH] [--lang CODE] <command> [options]
```

| Command | Description |
|---------|-------------|
| `init-db` | Create tables and indexes |
| `add` | Register transaction (`--type`, `--amount`, `--category`, `--date`, `--description`, `--currency`) |
| `list` | List transactions (`--limit`, default 20) |
| `balance` | Show total balance |
| `stats` | Summary by category and month |
| `plot` | Generate PNG charts (`--type`: bar/line/pie/scatter/bar3d/forecast/sankey/all) |
| `export` | Export reports (`--format`: csv/excel/pdf/json/yaml/html/monthly_pdf/all, `--budget-month YYYY-MM`) |

## Security

- **Database encryption**: Optional via SQLCipher AES-256. Enable from `Tools > Encrypt Database`.
- **PIN lock**: Configurable from `Tools > Set PIN Lock`. Protects the app at startup.
- **Encrypted backups**: Automatic and manual backups are encrypted with Fernet.
- **Encrypted cloud sync**: Database is encrypted before upload to any cloud provider.
- **File permissions**: Sensitive files (`data/.appkey`, `data/.cloud_salt`, `data/.lock`) use 600 permissions.

## Building executables

### Linux

```bash
./scripts/build_linux.sh        # Standalone binary (tar.gz)
./scripts/build_deb.sh          # .deb package
./scripts/build_rpm.sh          # .rpm package
```

### macOS

```bash
./scripts/build_macos.sh
```

### Windows

```powershell
./scripts/build_windows.ps1
```

## Testing

```bash
# Full tests with coverage
uv run pytest tests/ -q --cov=expenses_tracker

# Quick unit tests only
uv run pytest tests/ -q -m "not slow"

# Type checking
uv run mypy expenses_tracker/

# Linting
uv run ruff check expenses_tracker/
uv run ruff format --check expenses_tracker/
```

## License

Apache-2.0. See [LICENSE](LICENSE).
