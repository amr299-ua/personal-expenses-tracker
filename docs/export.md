# Export

The application supports 7 export formats with smart filtering.

## Formats

### CSV (`.csv`)
Plain comma-separated values. Universal compatibility.

### Excel (`.xlsx`)
Multi-sheet workbook with:
- **Sheet 1 — Transactions**: Full transaction list
- **Sheet 2 — By Category**: Aggregated totals per category
- **Sheet 3 — By Month**: Monthly income/expense summary

### PDF (`.pdf`)
Premium professional report including:
- Cover page with title, date, and summary
- KPI dashboard (balance, total income, total expense)
- Executive summary
- Trend analysis section
- 7 embedded charts
- Paginated transaction tables
- Budget vs. actual analysis (when budget month specified)

### JSON (`.json`)
Structured array of transaction objects for API consumption or data portability.

### YAML (`.yaml`)
Human-readable structured data, same content as JSON.

### HTML (`.html`)
Self-contained interactive report with Plotly charts.
Open in any browser — no server required.

### Monthly PDF
Consolidated monthly report with all sections for a specific month.

### Quick Export
Exports all applicable formats for the latest month at once (`Ctrl+E`).

## Smart export

Exports respect the current filters in the Transactions tab:
- Text search
- Transaction type (income/expense)
- Category
- Date range
- Tags

This lets you export exactly what you see on screen.

## CLI export

```bash
# Export all formats
python -m expenses_tracker --cli export --format all --output-dir reports

# Export PDF with budget comparison for May 2026
python -m expenses_tracker --cli export --format pdf --budget-month 2026-05
```
