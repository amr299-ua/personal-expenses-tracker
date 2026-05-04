from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np
from matplotlib import colormaps as _colormaps
from matplotlib.figure import Figure
from matplotlib.sankey import Sankey

from expenses_tracker.i18n import tr
from expenses_tracker.security import apply_private_permissions

matplotlib.use("Agg")
import matplotlib.pyplot as plt


PALETTES: dict[str, dict[str, str | list[str]]] = {
    "default": {
        "income": "#2e7d32",
        "expense": "#c62828",
        "balance": "#1565c0",
        "accent": "#6a1b9a",
        "cmap": "tab10",
    },
    "colorblind": {
        "income": "#0173B2",
        "expense": "#DE8F05",
        "balance": "#029E73",
        "accent": "#D55E00",
        "cmap": "cividis",
    },
    "dark": {
        "income": "#4ade80",
        "expense": "#f87171",
        "balance": "#38bdf8",
        "accent": "#a78bfa",
        "cmap": "tab20",
    },
}


def get_palette(name: str) -> dict[str, str | list[str]]:
    return PALETTES.get(name, PALETTES["default"])


def generate_charts(
    category_rows: list[dict[str, Any]],
    month_rows: list[dict[str, Any]],
    output_dir: str | Path = "reports",
    kind: str = "all",
    language: str = "en",
    palette: str = "default",
) -> list[Path]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    generated_files: list[Path] = []
    colors = get_palette(palette)

    requested = _resolve_chart_kinds(kind)

    if "bar" in requested and category_rows:
        category_file = output_path / f"chart_category_{timestamp}.png"
        _plot_category_totals(category_rows, category_file, language, colors)
        generated_files.append(category_file)

    if "line" in requested and month_rows:
        month_file = output_path / f"chart_month_{timestamp}.png"
        _plot_month_totals(month_rows, month_file, language, colors)
        generated_files.append(month_file)

    if "pie" in requested and category_rows:
        pie_file = output_path / f"chart_pie_{timestamp}.png"
        _plot_category_pie(category_rows, pie_file, language, colors)
        generated_files.append(pie_file)

    if "scatter" in requested and month_rows:
        scatter_file = output_path / f"chart_scatter_{timestamp}.png"
        _plot_month_scatter(month_rows, scatter_file, language, colors)
        generated_files.append(scatter_file)

    if "bar3d" in requested and month_rows:
        bar_3d_file = output_path / f"chart_3d_{timestamp}.png"
        _plot_month_bars_3d(month_rows, bar_3d_file, language, colors)
        generated_files.append(bar_3d_file)

    if "forecast" in requested and month_rows:
        forecast_file = output_path / f"chart_forecast_{timestamp}.png"
        _plot_forecast(month_rows, forecast_file, language, colors)
        generated_files.append(forecast_file)

    if "sankey" in requested and category_rows:
        sankey_file = output_path / f"chart_sankey_{timestamp}.png"
        _plot_sankey(category_rows, sankey_file, language, colors)
        generated_files.append(sankey_file)

    if "budget" in requested:
        # budget chart is generated separately with its own data
        pass

    return generated_files


def generate_budget_chart(
    budget_rows: list[dict[str, Any]],
    output_dir: str | Path = "reports",
    language: str = "en",
    palette: str = "default",
) -> Path | None:
    if not budget_rows:
        return None
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    file_path = output_path / f"chart_budget_{timestamp}.png"
    colors = get_palette(palette)
    _plot_budget_comparison(budget_rows, file_path, language, colors)
    return file_path


def _resolve_chart_kinds(kind: str) -> set[str]:
    normalized = kind.strip().lower()
    mapping = {
        "all": {"bar", "line", "pie", "scatter", "bar3d", "forecast", "sankey"},
        "category": {"bar"},
        "month": {"line"},
        "bar": {"bar"},
        "line": {"line"},
        "pie": {"pie"},
        "scatter": {"scatter"},
        "bar3d": {"bar3d"},
        "forecast": {"forecast"},
        "sankey": {"sankey"},
        "budget": {"budget"},
        "barras": {"bar"},
        "lineas": {"line"},
        "pastel": {"pie"},
        "queso": {"pie"},
        "puntos": {"scatter"},
        "3d": {"bar3d"},
    }

    if normalized not in mapping:
        valid_values = ", ".join(sorted(mapping.keys()))
        raise ValueError(f"Tipo de grafica no soportado: {kind}. Opciones validas: {valid_values}")

    return mapping[normalized]


# ---------------------------------------------------------------------------
# Figure factories (return Figure objects for embedding in GUI)
# ---------------------------------------------------------------------------


def category_totals_figure(
    rows: list[dict[str, Any]], language: str, colors: dict[str, Any]
) -> Figure:
    categories = [str(row["category"]) for row in rows]
    income = [float(row["income"]) for row in rows]
    expense = [float(row["expense"]) for row in rows]

    figure = Figure(figsize=(10, 5))
    axis = figure.add_subplot(111)
    positions = range(len(categories))

    axis.bar(positions, income, label=tr(language, "legend_income"), color=colors["income"])
    axis.bar(positions, expense, label=tr(language, "legend_expense"), color=colors["expense"], alpha=0.85)

    axis.set_title(tr(language, "chart_title_category"))
    axis.set_xlabel(tr(language, "chart_x_category"))
    axis.set_ylabel(tr(language, "chart_y_amount"))
    axis.set_xticks(list(positions))
    axis.set_xticklabels(categories, rotation=30, ha="right")
    axis.legend()

    figure.tight_layout()
    return figure


def month_totals_figure(
    rows: list[dict[str, Any]], language: str, colors: dict[str, Any]
) -> Figure:
    months = [str(row["month"]) for row in rows]
    income = [float(row["income"]) for row in rows]
    expense = [float(row["expense"]) for row in rows]
    balance = [float(row["balance"]) for row in rows]

    figure = Figure(figsize=(10, 5))
    axis = figure.add_subplot(111)

    axis.plot(months, income, marker="o", label=tr(language, "legend_income"), color=colors["income"])
    axis.plot(months, expense, marker="o", label=tr(language, "legend_expense"), color=colors["expense"])
    axis.plot(months, balance, marker="o", label=tr(language, "legend_balance"), color=colors["balance"])

    axis.set_title(tr(language, "chart_title_month"))
    axis.set_xlabel(tr(language, "chart_x_month"))
    axis.set_ylabel(tr(language, "chart_y_amount"))
    axis.grid(alpha=0.3)
    axis.legend()

    figure.tight_layout()
    return figure


def category_pie_figure(
    rows: list[dict[str, Any]], language: str, colors: dict[str, Any]
) -> Figure:
    categories = [str(row["category"]) for row in rows]
    income = [float(row["income"]) for row in rows]
    expense = [float(row["expense"]) for row in rows]

    total_income = sum(income)
    total_expense = sum(expense)

    figure = Figure(figsize=(12, 5))
    axes = [figure.add_subplot(1, 2, 1), figure.add_subplot(1, 2, 2)]
    cmap = _colormaps.get_cmap(str(colors["cmap"]))

    if total_income > 0:
        color_list = [cmap(i / len(categories)) for i in range(len(categories))]
        axes[0].pie(
            income,
            labels=categories,
            autopct="%1.1f%%",
            startangle=90,
            colors=color_list,
            wedgeprops={"linewidth": 1, "edgecolor": "white"},
        )
        axes[0].set_title(tr(language, "chart_title_income_distribution"))
    else:
        axes[0].text(0.5, 0.5, tr(language, "chart_no_income"), ha="center", va="center")
        axes[0].set_title(tr(language, "chart_title_income_distribution"))
        axes[0].axis("off")

    if total_expense > 0:
        color_list = [cmap(i / len(categories)) for i in range(len(categories))]
        axes[1].pie(
            expense,
            labels=categories,
            autopct="%1.1f%%",
            startangle=90,
            colors=color_list,
            wedgeprops={"linewidth": 1, "edgecolor": "white"},
        )
        axes[1].set_title(tr(language, "chart_title_expense_distribution"))
    else:
        axes[1].text(0.5, 0.5, tr(language, "chart_no_expense"), ha="center", va="center")
        axes[1].set_title(tr(language, "chart_title_expense_distribution"))
        axes[1].axis("off")

    figure.tight_layout()
    return figure


def month_scatter_figure(
    rows: list[dict[str, Any]], language: str, colors: dict[str, Any]
) -> Figure:
    months = [str(row["month"]) for row in rows]
    income = [float(row["income"]) for row in rows]
    expense = [float(row["expense"]) for row in rows]
    balance = [float(row["balance"]) for row in rows]
    positions = np.arange(len(months))

    figure = Figure(figsize=(11, 5))
    axis = figure.add_subplot(111)

    axis.scatter(positions, income, s=80, c=colors["income"], label=tr(language, "legend_income"), alpha=0.9)
    axis.scatter(positions, expense, s=80, c=colors["expense"], label=tr(language, "legend_expense"), alpha=0.9)
    axis.plot(positions, balance, c=colors["balance"], linewidth=2.2, marker="o", label=tr(language, "legend_balance"))

    axis.set_xticks(positions)
    axis.set_xticklabels(months, rotation=30, ha="right")
    axis.set_title(tr(language, "chart_title_scatter"))
    axis.set_xlabel(tr(language, "chart_x_month"))
    axis.set_ylabel(tr(language, "chart_y_amount"))
    axis.grid(alpha=0.3)
    axis.legend()

    figure.tight_layout()
    return figure


def month_bars_3d_figure(
    rows: list[dict[str, Any]], language: str, colors: dict[str, Any]
) -> Figure:
    months = [str(row["month"]) for row in rows]
    income = np.array([float(row["income"]) for row in rows], dtype=float)
    expense = np.array([float(row["expense"]) for row in rows], dtype=float)

    x_positions = np.arange(len(months), dtype=float)
    dx = np.full_like(x_positions, 0.35)
    dy = np.full_like(x_positions, 0.35)

    figure = Figure(figsize=(11, 6))
    axis = figure.add_subplot(111, projection="3d")

    axis.bar3d(x_positions, np.zeros_like(x_positions), np.zeros_like(x_positions), dx, dy, income, color=colors["income"])
    axis.bar3d(x_positions, np.ones_like(x_positions), np.zeros_like(x_positions), dx, dy, expense, color=colors["expense"])

    axis.set_xticks(x_positions + 0.17)
    axis.set_xticklabels(months, rotation=25, ha="right")
    axis.set_yticks([0.17, 1.17])
    axis.set_yticklabels([tr(language, "legend_income"), tr(language, "legend_expense")])
    axis.set_xlabel(tr(language, "chart_x_month"))
    axis.set_ylabel(tr(language, "chart_y_type"))
    axis.set_zlabel(tr(language, "chart_z_amount"))
    axis.set_title(tr(language, "chart_title_bar3d"))

    figure.subplots_adjust(left=0.04, right=0.96, bottom=0.12, top=0.90)
    return figure


def forecast_figure(
    rows: list[dict[str, Any]], language: str, colors: dict[str, Any]
) -> Figure:
    months = [str(row["month"]) for row in rows]
    expense = np.array([float(row["expense"]) for row in rows], dtype=float)

    figure = Figure(figsize=(10, 5))
    axis = figure.add_subplot(111)
    x = np.arange(len(months))

    axis.plot(x, expense, marker="o", label=tr(language, "legend_expense"), color=colors["expense"])

    if len(x) >= 2:
        coeffs = np.polyfit(x, expense, 1)
        poly = np.poly1d(coeffs)
        next_x = len(x)
        forecast_x = np.append(x, next_x)
        forecast_y = poly(forecast_x)
        axis.plot(forecast_x, forecast_y, "--", label=tr(language, "legend_forecast"), color=colors["accent"])
        axis.scatter([next_x], [forecast_y[-1]], s=100, c=colors["accent"], zorder=5)
        axis.axvline(x=next_x - 0.5, color="gray", linestyle=":", alpha=0.5)

    axis.set_xticks(list(x))
    axis.set_xticklabels(months, rotation=30, ha="right")
    axis.set_title(tr(language, "chart_title_forecast"))
    axis.set_xlabel(tr(language, "chart_x_month"))
    axis.set_ylabel(tr(language, "chart_y_amount"))
    axis.grid(alpha=0.3)
    axis.legend()

    figure.tight_layout()
    return figure


def sankey_figure(
    rows: list[dict[str, Any]], language: str, colors: dict[str, Any]
) -> Figure:
    total_income = sum(float(row["income"]) for row in rows)
    total_expense = sum(float(row["expense"]) for row in rows)

    if total_income <= 0 or total_expense <= 0:
        figure = Figure(figsize=(8, 4))
        axis = figure.add_subplot(111)
        axis.text(0.5, 0.5, tr(language, "chart_no_data"), ha="center", va="center", fontsize=14)
        axis.axis("off")
        return figure

    figure = Figure(figsize=(12, 6))
    axis = figure.add_subplot(111)
    sankey = Sankey(ax=axis, scale=total_income / 1000, offset=0.3)

    sankey.add(
        flows=[total_income, -total_expense, -(total_income - total_expense)],
        labels=[tr(language, "legend_income"), tr(language, "legend_expense"), tr(language, "legend_balance")],
        orientations=[0, -1, 1],
        pathlengths=[0.25, 0.25, 0.25],
        facecolor=colors["income"],
    )
    sankey.finish()
    axis.set_title(tr(language, "chart_title_sankey"))
    axis.axis("off")

    figure.tight_layout()
    return figure


def budget_comparison_figure(
    rows: list[dict[str, Any]], language: str, colors: dict[str, Any]
) -> Figure:
    categories = [str(row["category"]) for row in rows]
    actual = [float(row["actual"]) for row in rows]
    planned = [float(row["planned"]) for row in rows]

    figure = Figure(figsize=(10, 5))
    axis = figure.add_subplot(111)
    positions = np.arange(len(categories))
    width = 0.35

    axis.bar(positions - width / 2, planned, width, label=tr(language, "legend_planned"), color=colors["balance"])
    axis.bar(positions + width / 2, actual, width, label=tr(language, "legend_actual"), color=colors["expense"])

    axis.set_title(tr(language, "chart_title_budget"))
    axis.set_xlabel(tr(language, "chart_x_category"))
    axis.set_ylabel(tr(language, "chart_y_amount"))
    axis.set_xticks(positions)
    axis.set_xticklabels(categories, rotation=30, ha="right")
    axis.legend()
    axis.grid(axis="y", alpha=0.3)

    figure.tight_layout()
    return figure


# ---------------------------------------------------------------------------
# PNG wrappers (keep existing interface for CLI / backward compat)
# ---------------------------------------------------------------------------


def _save_figure(figure: Figure, output_file: Path) -> None:
    figure.savefig(output_file, dpi=150)
    apply_private_permissions(output_file)


def _plot_category_totals(
    rows: list[dict[str, Any]], output_file: Path, language: str, colors: dict[str, Any]
) -> None:
    figure = category_totals_figure(rows, language, colors)
    _save_figure(figure, output_file)
    plt.close(figure)


def _plot_month_totals(
    rows: list[dict[str, Any]], output_file: Path, language: str, colors: dict[str, Any]
) -> None:
    figure = month_totals_figure(rows, language, colors)
    _save_figure(figure, output_file)
    plt.close(figure)


def _plot_category_pie(
    rows: list[dict[str, Any]], output_file: Path, language: str, colors: dict[str, Any]
) -> None:
    figure = category_pie_figure(rows, language, colors)
    _save_figure(figure, output_file)
    plt.close(figure)


def _plot_month_scatter(
    rows: list[dict[str, Any]], output_file: Path, language: str, colors: dict[str, Any]
) -> None:
    figure = month_scatter_figure(rows, language, colors)
    _save_figure(figure, output_file)
    plt.close(figure)


def _plot_month_bars_3d(
    rows: list[dict[str, Any]], output_file: Path, language: str, colors: dict[str, Any]
) -> None:
    figure = month_bars_3d_figure(rows, language, colors)
    _save_figure(figure, output_file)
    plt.close(figure)


def _plot_forecast(
    rows: list[dict[str, Any]], output_file: Path, language: str, colors: dict[str, Any]
) -> None:
    figure = forecast_figure(rows, language, colors)
    _save_figure(figure, output_file)
    plt.close(figure)


def _plot_sankey(
    rows: list[dict[str, Any]], output_file: Path, language: str, colors: dict[str, Any]
) -> None:
    figure = sankey_figure(rows, language, colors)
    _save_figure(figure, output_file)
    plt.close(figure)


def _plot_budget_comparison(
    rows: list[dict[str, Any]], output_file: Path, language: str, colors: dict[str, Any]
) -> None:
    figure = budget_comparison_figure(rows, language, colors)
    _save_figure(figure, output_file)
    plt.close(figure)
