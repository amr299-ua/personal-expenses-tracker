# CLI Reference

The CLI provides full feature parity with the GUI.

## Basic syntax

```
python -m expenses_tracker --cli [--db-path PATH] [--lang CODE] [--list-languages] <command> [options]
```

## Global flags

| Flag | Description |
|------|-------------|
| `--cli` | Enable CLI mode (required) |
| `--db-path PATH` | Override database path |
| `--lang CODE` | Set language (en, es, fr, de, it, pt, ja, ar) |
| `--list-languages` | List supported languages and exit |

## Commands

### `init-db`

Create tables and indexes in the SQLite database.

```bash
python -m expenses_tracker --cli init-db
```

### `add`

Register a new transaction.

```bash
python -m expenses_tracker --cli add \
    --type income \
    --amount 2500 \
    --category Salario \
    --date 2026-05-11 \
    --description "Pago mensual" \
    --currency USD
```

| Option | Required | Description |
|--------|----------|-------------|
| `--type` | Yes | `income` or `expense` |
| `--amount` | Yes | Positive number |
| `--category` | Yes | Category name |
| `--date` | Yes | `YYYY-MM-DD` format |
| `--description` | No | Free text |
| `--currency` | No | 3-letter code (default: USD) |

### `list`

List recent transactions.

```bash
python -m expenses_tracker --cli list --limit 50
```

| Option | Default | Description |
|--------|---------|-------------|
| `--limit` | 20 | Max rows to show |

### `balance`

Show total balance (income minus expenses).

```bash
python -m expenses_tracker --cli balance
```

### `stats`

Summary statistics by category and month.

```bash
python -m expenses_tracker --cli stats
```

### `plot`

Generate chart images.

```bash
python -m expenses_tracker --cli plot --type all --output-dir reports
```

| Option | Description |
|--------|-------------|
| `--type` | Chart type: `bar`, `line`, `pie`, `scatter`, `bar3d`, `forecast`, `sankey`, `all` |
| `--output-dir` | Output directory (default: `reports`) |

### `export`

Generate report files.

```bash
python -m expenses_tracker --cli export --format all --output-dir reports
python -m expenses_tracker --cli export --format pdf --budget-month 2026-05
```

| Option | Description |
|--------|-------------|
| `--format` | `csv`, `excel`, `pdf`, `json`, `yaml`, `html`, `monthly_pdf`, `all` |
| `--output-dir` | Output directory (default: `reports`) |
| `--budget-month` | Include budget comparison for `YYYY-MM` |
