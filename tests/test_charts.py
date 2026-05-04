"""Tests for chart generation (charts.py)."""

from __future__ import annotations

import pytest

from expenses_tracker.charts import generate_charts, _resolve_chart_kinds
from tests.conftest import CATEGORY_ROWS, MONTH_ROWS


# ---------------------------------------------------------------------------
# _resolve_chart_kinds()
# ---------------------------------------------------------------------------


class TestResolveChartKinds:
    def test_all_returns_all_kinds(self):
        kinds = _resolve_chart_kinds("all")
        assert kinds == {"bar", "line", "pie", "scatter", "bar3d", "forecast", "sankey"}

    def test_category_alias_returns_bar(self):
        assert _resolve_chart_kinds("category") == {"bar"}

    def test_month_alias_returns_line(self):
        assert _resolve_chart_kinds("month") == {"line"}

    def test_explicit_bar(self):
        assert _resolve_chart_kinds("bar") == {"bar"}

    def test_explicit_line(self):
        assert _resolve_chart_kinds("line") == {"line"}

    def test_explicit_pie(self):
        assert _resolve_chart_kinds("pie") == {"pie"}

    def test_explicit_scatter(self):
        assert _resolve_chart_kinds("scatter") == {"scatter"}

    def test_explicit_bar3d(self):
        assert _resolve_chart_kinds("bar3d") == {"bar3d"}

    def test_case_insensitive(self):
        assert _resolve_chart_kinds("ALL") == _resolve_chart_kinds("all")
        assert _resolve_chart_kinds("BAR") == _resolve_chart_kinds("bar")

    def test_unknown_kind_raises_value_error(self):
        with pytest.raises(ValueError):
            _resolve_chart_kinds("unknown_chart_type")


# ---------------------------------------------------------------------------
# generate_charts() — output directory and returned paths
# ---------------------------------------------------------------------------


class TestGenerateChartsOutputDir:
    def test_creates_output_directory_if_missing(self, tmp_path):
        out = tmp_path / "new_subdir"
        assert not out.exists()
        generate_charts(CATEGORY_ROWS, MONTH_ROWS, output_dir=out, kind="bar")
        assert out.is_dir()

    def test_returns_list_of_paths(self, tmp_path):
        result = generate_charts(CATEGORY_ROWS, MONTH_ROWS, output_dir=tmp_path, kind="bar")
        assert isinstance(result, list)

    def test_returned_paths_exist_on_disk(self, tmp_path):
        result = generate_charts(CATEGORY_ROWS, MONTH_ROWS, output_dir=tmp_path, kind="all")
        for path in result:
            assert path.exists(), f"Expected file to exist: {path}"

    def test_returned_paths_are_png(self, tmp_path):
        result = generate_charts(CATEGORY_ROWS, MONTH_ROWS, output_dir=tmp_path, kind="all")
        for path in result:
            assert path.suffix == ".png"

    def test_invalid_kind_raises_value_error(self, tmp_path):
        with pytest.raises(ValueError):
            generate_charts(CATEGORY_ROWS, MONTH_ROWS, output_dir=tmp_path, kind="invalid_kind")


# ---------------------------------------------------------------------------
# generate_charts() — per-kind file generation
# ---------------------------------------------------------------------------


class TestGenerateChartsKinds:
    def test_bar_generates_one_file(self, tmp_path):
        result = generate_charts(CATEGORY_ROWS, MONTH_ROWS, output_dir=tmp_path, kind="bar")
        assert len(result) == 1
        assert "category" in result[0].name

    def test_line_generates_one_file(self, tmp_path):
        result = generate_charts(CATEGORY_ROWS, MONTH_ROWS, output_dir=tmp_path, kind="line")
        assert len(result) == 1
        assert "month" in result[0].name

    def test_pie_generates_one_file(self, tmp_path):
        result = generate_charts(CATEGORY_ROWS, MONTH_ROWS, output_dir=tmp_path, kind="pie")
        assert len(result) == 1
        assert "pie" in result[0].name

    def test_scatter_generates_one_file(self, tmp_path):
        result = generate_charts(CATEGORY_ROWS, MONTH_ROWS, output_dir=tmp_path, kind="scatter")
        assert len(result) == 1
        assert "scatter" in result[0].name

    def test_bar3d_generates_one_file(self, tmp_path):
        result = generate_charts(CATEGORY_ROWS, MONTH_ROWS, output_dir=tmp_path, kind="bar3d")
        assert len(result) == 1
        assert "3d" in result[0].name

    def test_all_generates_seven_files(self, tmp_path):
        result = generate_charts(CATEGORY_ROWS, MONTH_ROWS, output_dir=tmp_path, kind="all")
        assert len(result) == 7

    def test_category_alias_same_as_bar(self, tmp_path):
        r1 = generate_charts(CATEGORY_ROWS, MONTH_ROWS, output_dir=tmp_path / "a", kind="category")
        r2 = generate_charts(CATEGORY_ROWS, MONTH_ROWS, output_dir=tmp_path / "b", kind="bar")
        assert len(r1) == len(r2) == 1

    def test_month_alias_same_as_line(self, tmp_path):
        r1 = generate_charts(CATEGORY_ROWS, MONTH_ROWS, output_dir=tmp_path / "a", kind="month")
        r2 = generate_charts(CATEGORY_ROWS, MONTH_ROWS, output_dir=tmp_path / "b", kind="line")
        assert len(r1) == len(r2) == 1


# ---------------------------------------------------------------------------
# generate_charts() — empty data edge cases
# ---------------------------------------------------------------------------


class TestGenerateChartsEmptyData:
    def test_no_category_rows_skips_bar(self, tmp_path):
        result = generate_charts([], MONTH_ROWS, output_dir=tmp_path, kind="bar")
        assert result == []

    def test_no_month_rows_skips_line(self, tmp_path):
        result = generate_charts(CATEGORY_ROWS, [], output_dir=tmp_path, kind="line")
        assert result == []

    def test_both_empty_returns_empty_list(self, tmp_path):
        result = generate_charts([], [], output_dir=tmp_path, kind="all")
        assert result == []

    def test_no_category_rows_still_generates_line(self, tmp_path):
        result = generate_charts([], MONTH_ROWS, output_dir=tmp_path, kind="line")
        assert len(result) == 1


# ---------------------------------------------------------------------------
# generate_charts() — language support
# ---------------------------------------------------------------------------


class TestGenerateChartsLanguage:
    def test_spanish_language_does_not_raise(self, tmp_path):
        result = generate_charts(CATEGORY_ROWS, MONTH_ROWS, output_dir=tmp_path, kind="bar", language="es")
        assert len(result) == 1
