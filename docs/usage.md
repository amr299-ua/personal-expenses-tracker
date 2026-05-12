# Quick Start

## First run

1. Launch the GUI:
   ```bash
   python -m expenses_tracker
   ```

2. The application creates a SQLite database at `data/expenses.db`.
   The first run automatically initializes the schema.

3. Start adding transactions in the **Register** tab.

## Seed test data

For exploring features with realistic data:

```bash
python seed_data.py
```

This creates 500 test transactions spanning income and expenses across
multiple categories, currencies, and date ranges.

## Basic workflow

### 1. Add transactions

Use the **Register** tab to add income and expense transactions.
Fields are validated in real-time:

- Amount (positive number)
- Date (pick from calendar or type)
- Category (predefined or custom)
- Description (optional, enables auto-categorization)
- Currency (USD by default)
- Tags (comma-separated, optional)
- Recurring flag (daily/weekly/monthly/yearly)

### 2. Browse and filter

The **Transactions** tab shows all records in a sortable table.
Filter by:

- Text search (searches all fields)
- Transaction type (income/expense)
- Category
- Date range (with presets: Today, This Week, This Month, This Year)
- Tags (comma-separated)

### 3. Analyze with charts

The **Statistics** tab shows:

- Embedded interactive charts (8 types)
- Summary statistics by category and month
- Export individual charts as PNG

Open the full chart viewer via **Tools > Charts** or `Ctrl+G`.

### 4. Manage budgets

The **Budgets** tab lets you:

- Set monthly budget amounts per category
- Compare planned vs. actual spending
- See status indicators: OK (green), Warning >80% (yellow), Over (red)

### 5. Export reports

Use the toolbar or **File > Export** to generate reports.
Formats available:

- **CSV**: Plain text, universal
- **Excel**: `.xlsx` with 3 sheets (transactions, by category, by month)
- **PDF**: Premium report with cover page, KPI dashboard, trend analysis,
  embedded charts, and paginated tables
- **JSON / YAML**: Structured data for portability
- **HTML**: Interactive Plotly charts embedded

**Smart export** respects your current filters.
**Quick export** (`Ctrl+E`) exports all formats for the latest month.
