# Contributing

## Getting started

1. Fork and clone the repository
2. Set up the development environment:
   ```bash
   uv sync
   uv run pre-commit install
   ```
3. Run the test suite to verify everything works:
   ```bash
   uv run pytest tests/ -q
   ```

## Development guidelines

### Code style

- Follow existing patterns and conventions in the codebase
- All public functions must have docstrings (Google style)
- Maximum line length: 120 characters
- Use type annotations everywhere (mypy strict mode enforced)
- No `# TODO` or `# FIXME` comments — create an issue instead

### Before submitting

Run the full quality pipeline:

```bash
# Lint
uv run ruff check expenses_tracker/

# Format
uv run ruff format --check expenses_tracker/

# Type check
uv run mypy expenses_tracker/

# Tests with coverage
uv run pytest tests/ -q --cov=expenses_tracker --cov-fail-under=90
```

### Commit messages

- Use present tense ("Add feature" not "Added feature")
- Keep first line under 72 characters
- Reference issues when applicable

### Adding tests

- Every new feature needs corresponding tests
- Place tests in `tests/` with the prefix `test_`
- Use `conftest.py` fixtures when possible
- Mark slow tests with `@pytest.mark.slow`

### Adding languages

Use the `scripts/add_language.py` tool:

```bash
python scripts/add_language.py --code zh --name 中文
```

This creates a new locale file from the English template.

## Project structure conventions

```
expenses_tracker/
├── models.py       # SQLAlchemy ORM models
├── schemas.py      # Pydantic validation schemas
├── db.py           # Data access layer
├── services/       # Business logic (DI-ready)
├── tabs/           # GUI tab components
├── locales/        # Translation JSON files
└── ...
```

Services should be registered in `di.py` and not import GUI modules directly.
GUI modules import services through the DI container.
