# Charts

The application generates 8 types of charts, all available in the GUI (embedded or popup viewer)
and via the CLI.

## Chart types

### Bar Chart (`bar`)
Grouped bars showing income and expenses by category for a selected period.

### Line Chart (`line`)
Monthly evolution of income, expenses, and balance over time.
Series can be toggled on/off with checkboxes.

### Pie Chart (`pie`)
Distribution of income sources and expense categories as pie charts.

### Scatter Chart (`scatter`)
Monthly income and expense points with a balance trend line.

### 3D Bar Chart (`bar3d`)
Three-dimensional grouped bars by month for dramatic presentation.

### Forecast (`forecast`)
Linear regression extrapolation predicting future balance based on historical data.
Shows confidence interval and trend direction.

### Sankey Diagram (`sankey`)
Flow diagram showing how income sources map to expense categories.
Useful for understanding spending patterns.

### Budget Comparison (`budget_comparison`)
Grouped bars comparing planned budget amounts vs. actual spending per category.
Only available when a budget month filter is active.

## Interactive features

All charts in the GUI support:

- **Scroll to zoom**: Mouse wheel over the chart area
- **Tooltips**: Hover over bars, points, and lines to see exact values
- **Series toggles**: Show/hide income, expense, or balance lines
- **Export to PNG**: Save individual charts as high-resolution images

## Color palettes

Three palettes available via the GUI palette selector:

- **Default**: Blue/red color scheme for income/expense
- **Colorblind**: Accessible palette using shapes and contrasting hues
- **Dark**: Optimized for dark theme backgrounds

## CLI chart generation

```bash
# Generate a specific chart type
python -m expenses_tracker --cli plot --type bar --output-dir reports

# Generate all chart types
python -m expenses_tracker --cli plot --type all --output-dir reports
```

Charts are saved as PNG files in the specified output directory.
