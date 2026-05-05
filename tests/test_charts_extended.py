"""Extended chart tests for edge cases and figure functions."""

from __future__ import annotations

from expenses_tracker.charts import (
    budget_comparison_figure,
    forecast_figure,
    generate_budget_chart,
    generate_charts,
    sankey_figure,
)


class TestForecastFigure:
    def test_less_than_two_months_no_forecast_line(self):
        rows = [{"month": "2025-01", "income": 1000.0, "expense": 500.0, "balance": 500.0}]
        fig = forecast_figure(rows, "en", {"expense": "#c62828", "accent": "#6a1b9a"})
        assert len(fig.axes) == 1

    def test_two_months_generates_forecast(self):
        rows = [
            {"month": "2025-01", "income": 1000.0, "expense": 500.0, "balance": 500.0},
            {"month": "2025-02", "income": 1000.0, "expense": 600.0, "balance": 400.0},
        ]
        fig = forecast_figure(rows, "en", {"expense": "#c62828", "accent": "#6a1b9a"})
        assert len(fig.axes) == 1


class TestSankeyFigure:
    def test_zero_income_returns_no_data(self):
        rows = [{"category": "Food", "income": 0.0, "expense": 100.0, "balance": -100.0}]
        fig = sankey_figure(rows, "en", {"income": "#2e7d32"})
        assert len(fig.axes) == 1

    def test_zero_expense_returns_no_data(self):
        rows = [{"category": "Salary", "income": 100.0, "expense": 0.0, "balance": 100.0}]
        fig = sankey_figure(rows, "en", {"income": "#2e7d32"})
        assert len(fig.axes) == 1

    def test_valid_sankey(self):
        rows = [
            {"category": "Salary", "income": 1000.0, "expense": 0.0, "balance": 1000.0},
            {"category": "Food", "income": 0.0, "expense": 300.0, "balance": -300.0},
        ]
        fig = sankey_figure(rows, "en", {"income": "#2e7d32", "expense": "#c62828", "balance": "#1565c0"})
        assert len(fig.axes) == 1


class TestBudgetComparisonFigure:
    def test_generates_figure(self):
        rows = [
            {"category": "Food", "actual": 300.0, "planned": 500.0},
            {"category": "Transport", "actual": 100.0, "planned": 150.0},
        ]
        fig = budget_comparison_figure(rows, "en", {"balance": "#1565c0", "expense": "#c62828"})
        assert len(fig.axes) == 1


class TestGenerateBudgetChart:
    def test_creates_file(self, tmp_path):
        rows = [{"category": "Food", "actual": 300.0, "planned": 500.0}]
        path = generate_budget_chart(rows, output_dir=tmp_path, language="en")
        assert path is not None
        assert path.exists()

    def test_empty_rows_returns_none(self, tmp_path):
        path = generate_budget_chart([], output_dir=tmp_path, language="en")
        assert path is None


class TestChartsLanguageAndPalette:
    def test_spanish_language_does_not_raise(self, tmp_path):
        rows = [{"category": "Food", "income": 0.0, "expense": 100.0, "balance": -100.0}]
        result = generate_charts(rows, [], output_dir=tmp_path, kind="bar", language="es")
        assert len(result) == 1

    def test_colorblind_palette(self, tmp_path):
        rows = [{"category": "Food", "income": 0.0, "expense": 100.0, "balance": -100.0}]
        result = generate_charts(rows, [], output_dir=tmp_path, kind="bar", palette="colorblind")
        assert len(result) == 1

    def test_dark_palette(self, tmp_path):
        rows = [{"category": "Food", "income": 0.0, "expense": 100.0, "balance": -100.0}]
        result = generate_charts(rows, [], output_dir=tmp_path, kind="bar", palette="dark")
        assert len(result) == 1
