# Architecture

## High-level overview

The application follows a layered architecture with dependency injection:

```
GUI Layer (gui.py, tabs/*.py, gui_dialogs.py)
    ↓ uses
Service Layer (services/*.py)
    ↓ uses
Data Layer (db.py, models.py)
    ↓ uses
SQLAlchemy 2.0 ORM → SQLite (+ optional SQLCipher)
```

## Dependency Injection

`di.py` implements a lightweight DI container with singleton and factory registrations.
Services are wired in `gui.py:main()`.

```python
from expenses_tracker.di import Container

container = Container()
container.register_singleton(DatabaseService, lambda c: DatabaseService(db))
container.register_singleton(TransactionService, lambda c: TransactionService(db))
container.register_singleton(ExportService, lambda c: ExportService(db))
container.register_singleton(UIStateService, lambda c: UIStateService())
container.register_singleton(CurrencyService, lambda c: CurrencyService(db))
container.register_factory(CategorySuggestionService, lambda c: CategorySuggestionService())
```

## Key modules

### `models.py` — ORM Models (6 tables)

Defines SQLAlchemy 2.0 declarative models:
- `Category` — Income/expense categories with icons and colors
- `Transaction` — Financial records with soft-delete and recurring support
- `Budget` — Monthly budget plans per category
- `ExchangeRate` — Currency exchange rates
- `AuditLogEntry` — Database audit log
- `AutomationConfig` — Singleton scheduler configuration

### `db.py` — Data Access Layer

`ExpenseDatabase` class (862 lines) provides all CRUD operations:
- Transaction management (add, update, delete, soft-delete, restore, purge)
- Category management
- Budget operations
- Exchange rate CRUD
- Filtering, sorting, and pagination helpers
- Statistics aggregation queries

### `schemas.py` — Validation

Pydantic v2 models for input validation:
- `TransactionInput` — Amount, type, category, date, currency, tags, recurring
- `CategoryInput` — Name, type, active status
- `BudgetInput` — Category, month, planned amount
- `ExchangeRateInput` — Currency pair, rate, date

### `gui.py` — Main GUI

`ExpensesApp` class (989 lines, refactored from 2260):
- Window setup, menu bar, toolbar
- Tab container with 4 tabs
- KPI metric cards
- Language and theme switching
- Keyboard shortcut bindings

### `tabs/` — GUI Tab Components

Each tab is a self-contained component:
- `register_tab.py` — Transaction entry form with real-time validation
- `transactions_tab.py` — Table view with filters, sorting, pagination
- `stats_tab.py` — Embedded charts and statistics trees
- `budget_tab.py` — Budget CRUD with progress indicators

### `services/` — Business Logic

- `transaction_service.py` — Filter/sort/paginate/aggregate operations
- `database_service.py` — Backup, automation config management
- `export_service.py` — Report generation delegation
- `state_service.py` — UI state persistence (`data/ui_state.json`)
- `category_suggestion_service.py` — Keyword-frequency auto-categorization
- `currency_service.py` — Exchange rate fetching (frankfurter.app API)

### `exporters.py` — Report Generation

7 format exporters:
- `export_csv` — Standard CSV
- `export_excel` — Multi-sheet `.xlsx`
- `export_pdf` — Professional PDF with cover, KPI, charts, tables
- `export_json` — Structured JSON
- `export_yaml` — Structured YAML
- `export_html` — Interactive Plotly HTML
- `export_monthly_pdf` — Consolidated monthly report

### `security.py` — Cryptography and Locking

- `SQLCipherManager` — Key generation, validation, database encryption
- `LockManager` — PIN lock with PBKDF2 and rate limiting
- `PinValidator` — Weak PIN rejection
- `PinRateLimiter` — Exponential backoff
- `DatabaseEncryption` — Encrypt/decrypt database files
- `AppCrypto` — Fernet key management and file encryption
- `BackupManager` — Rotating backups with encryption
- `AuditLog` — JSONL file-based audit trail
- `CloudSyncSaltManager` — Per-app random salt for cloud sync

### `cloud_sync.py` — Cloud Providers

Abstract `CloudProvider` interface with three implementations:
- `WebDAVProvider` — WebDAV via `webdavclient3`
- `DropboxProvider` — Dropbox API v2
- `GoogleDriveProvider` — Google Drive API

`CloudSyncManager` handles encryption, conflict detection, and config persistence.

### `automation.py` — Scheduled Tasks

`ReportScheduler` runs in a daemon thread:
- Configurable schedule (daily/weekly/monthly)
- Actions: report generation, database backup, email delivery
- Recurring transaction processing at midnight
- SMTP email with TLS/SSL support
