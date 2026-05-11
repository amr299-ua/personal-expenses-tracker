# Changelog

All notable changes to Personal Expenses Tracker are documented in this file.

## [0.2.0] — 2026-05-11

### Security
- **Fixed critical**: Hardcoded fixed salt in cloud sync key derivation replaced with random per-app salt stored in `data/.cloud_salt` (`CloudSyncSaltManager`)
- **Fixed high**: SMTP password now encrypted at rest using `AppCrypto` Fernet key stored in `data/.appkey` with `ENC:` prefix marker
- **Added**: PIN strength validator (`PinValidator`) requiring minimum 4 characters, rejecting weak/trivial PINs (`0000`, `1234`, `password`, etc.)
- **Added**: Exponential backoff rate limiting for PIN attempts (`PinRateLimiter`): 3→5s, 4→15s, 5→30s, 6→60s, 7→permanent lockout
- **Fixed**: SQLCipher PRAGMA key now validated as hex-only (64 chars) before use, eliminating SQL injection vector

### Bug fixes
- **Fixed**: Unified SQLAlchemy 2.0 API — replaced deprecated `session.query()` with `session.execute(select())` in automation
- **Fixed**: Budget deletion now uses direct ID lookup instead of O(n) search across all budgets
- **Fixed**: Matplotlib memory leak — figures now properly closed with `plt.close()` after conversion in PDF exports
- **Fixed**: WebDAV `list_files()` now returns structured metadata (size, modified) with graceful fallback
- **Fixed**: Pydantic `ValidationError` details preserved in custom `__init__` via `_format_pydantic_error()` helper

### New features
- **CI/CD**: GitHub Actions workflow (`lint`, `type-check`, `test` with Python 3.10/3.11/3.12 matrix + Codecov)
- **Cloud sync persistence**: Provider credentials and auto-sync flag encrypted and persisted across sessions via `CloudSyncConfigManager`
- **Recurring transactions**: `recurring_interval` field (`daily`/`weekly`/`monthly`/`yearly`), auto-creation of next occurrences via scheduler
- **Tag filtering**: Search/filter transactions by comma-separated tags in the GUI transactions tab
- **Import**: CSV, Excel (`.xlsx`/`.xls`), and JSON import with auto-detection, column mapping, and GUI file dialog
- **Soft-delete**: Transactions are now soft-deleted (`deleted_at` timestamp) with restore and permanent purge support
- **Cloud sync conflict detection**: `sync_up()` checks remote metadata timestamp before uploading, returns False if remote is newer

### Schema changes
- Added `recurring_interval` (String) and `next_recurring_date` (Date) to `transactions`
- Added `deleted_at` (DateTime) to `transactions`
- Alembic migrations: `a1b2c3d4e5f6`, `b2c3d4e5f6a7`

## [0.1.0] — 2026-05-02

### Core
- SQLAlchemy 2.0 ORM with 7 models: `Category`, `Transaction`, `Budget`, `ExchangeRate`, `AuditLogEntry`, `AutomationConfig`
- Alembic migrations with 7 revisions for schema evolution
- Pydantic v2 validation schemas (`TransactionInput`, `CategoryInput`, `BudgetInput`, `ExchangeRateInput`)
- Dependency injection container for service wiring

### GUI (Tkinter + ttkbootstrap)
- 4 tabs: Register, Transactions (filterable/sortable/paginated), Statistics (embedded charts), Budgets (progress indicators)
- Light/dark theme (`flatly`/`darkly`) with 3 color palettes (default, colorblind, dark)
- Real-time form validation with visual indicators
- Keyboard shortcuts (`Ctrl+N`, `Ctrl+F`, `Ctrl+S`, `F5`, `Ctrl+G`, `Ctrl+E`, `Ctrl+1-4`)
- Calendar date picker dialog
- Chart type selector dialog
- PIN lock screen with set/unlock modes

### Charts
- 8 chart types: bar, line, pie, scatter, 3D bar, forecast (linear regression), Sankey flow diagram, budget comparison
- Matplotlib figures embedded in GUI via `FigureCanvasTkAgg`
- Export charts as PNG to `reports/`

### Export
- Formats: Excel (`.xlsx`), CSV, PDF (premium cover + KPI dashboard + charts + paginated tables), JSON, YAML, HTML (Plotly interactive)
- Monthly consolidated PDF report
- Smart export based on current filters
- Quick export (all formats for latest month)

### Security
- SQLCipher AES-256 database encryption with key management
- PIN lock with PBKDF2-HMAC-SHA256 (600k iterations)
- Fernet file encryption for backups and cloud sync
- Audit logging (file JSONL + database table)
- Private file permissions (600/700 on Unix)

### Cloud sync
- Providers: WebDAV, Dropbox API v2, Google Drive API
- Encrypted upload/download with Fernet
- Auto-sync support via scheduler

### Automation
- Background scheduler for reports, backups, and email delivery
- Configurable daily/weekly/monthly schedules
- SMTP email with TLS/SSL support (port 587/465)

### Internationalization
- 8 languages: English, Spanish, French, German, Italian, Portuguese, Japanese, Arabic (RTL)
- RTL support with `arabic-reshaper` + `python-bidi`
- Regional number/date formatting
- Hot-reload language switching without restart

### CLI
- Full feature parity: add, list, balance, stats, plot, export
- `--currency` flag on add command
- Budget month filter on export

### Testing
- 300+ tests with pytest
- Property-based testing with Hypothesis
- Coverage threshold: 90%

### Build & CI
- PyInstaller packaging (onefile, windowed) for Linux/macOS/Windows
- uv package management with lockfile
- pre-commit hooks (Ruff lint/format, Mypy strict, trailing-whitespace, etc.)
