# Testing

## Test suite

The project has 300+ tests across 24 test files.

### Running tests

```bash
# All tests with coverage
uv run pytest tests/ -q --cov=expenses_tracker

# Skip slow tests
uv run pytest tests/ -q -m "not slow"

# Run specific test file
uv run pytest tests/test_db.py -v

# Property-based tests only
uv run pytest tests/test_property_based.py -v
```

### Coverage

Coverage threshold: **90%** (enforced in CI and `pyproject.toml`).

Current coverage: ~92% (excluding GUI modules that require a display).

Excluded from coverage:
- GUI modules (`gui.py`, all tabs, dialogs, chart panels)
- `__main__.py` (entry point)
- `logging_config.py` (logging setup)

### Test files

| File | Tests | Scope |
|------|-------|-------|
| `test_db.py` | Core CRUD | Transaction, category, budget operations |
| `test_db_extended.py` | Extended CRUD | Edge cases, soft-delete, pagination |
| `test_cli.py` | CLI commands | init-db, add, list, balance, stats |
| `test_cli_extended.py` | Extended CLI | Export, plot, error handling |
| `test_charts.py` | Chart generation | All 8 chart types |
| `test_charts_extended.py` | Extended charts | Edge cases, empty data |
| `test_exporters.py` | Export formats | CSV, Excel, PDF, JSON, YAML, HTML |
| `test_i18n.py` | Internationalization | Translation loading, locale formatting |
| `test_security.py` | Core security | PIN, encryption, key derivation |
| `test_security_extended.py` | Extended security | Rate limiting, audit, backups |
| `test_models.py` | ORM models | Table creation, relationships |
| `test_schemas.py` | Pydantic schemas | Validation, edge cases |
| `test_automation.py` | Automation | Scheduler, email, config |
| `test_automation_extended.py` | Extended automation | Recurring processing |
| `test_cloud_sync.py` | Cloud sync | Provider interfaces, encryption |
| `test_cloud_sync_extended.py` | Extended sync | Conflict detection, persistence |
| `test_gui_logic.py` | GUI logic | Non-rendering logic tests |
| `test_transaction_service.py` | Service layer | Filter, sort, paginate (24 tests) |
| `test_database_service.py` | Database service | Backup, config |
| `test_di_integration.py` | DI container | Registration, resolution (4 tests) |
| `test_currency_service.py` | Currency | Exchange rate fetching |
| `test_category_suggestion.py` | Auto-categorization | Learning, suggestion |
| `test_property_based.py` | Hypothesis | Extreme amounts, date limits |
| `test_architecture.py` | Architecture | Module structure, import rules (14 tests) |

### Property-based testing

Uses **Hypothesis** to test extreme values:

```python
@given(
    amounts=lists(floats(min_value=0.01, max_value=1e9), min_size=1, max_size=50),
    dates_list=lists(dates(min_value=date(1900, 1, 1), max_value=date(2100, 12, 31))),
)
```

Tests verify that:
- Balance calculation is always correct (income - expense)
- Totals match individual transactions
- Extreme amounts and dates don't cause errors

## Type checking

**Mypy** runs in strict mode on all non-GUI modules:

```bash
uv run mypy expenses_tracker/
```

## Linting

**Ruff** enforces code style and catches issues:

```bash
uv run ruff check expenses_tracker/
uv run ruff format --check expenses_tracker/
```

## pre-commit hooks

Run automatically on `git commit`:

- Ruff (lint + format)
- Mypy (strict type checking)
- Whitespace and merge conflict checks
- JSON/YAML validation
- Large file detection
- Debug statement detection
