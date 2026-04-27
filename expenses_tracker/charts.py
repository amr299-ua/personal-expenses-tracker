from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def generate_charts(
    category_rows: list[dict[str, Any]],
    month_rows: list[dict[str, Any]],
    output_dir: str | Path = "reports",
    kind: str = "all",
) -> list[Path]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    generated_files: list[Path] = []

    requested = _resolve_chart_kinds(kind)

    if "bar" in requested and category_rows:
        category_file = output_path / f"chart_category_{timestamp}.png"
        _plot_category_totals(category_rows, category_file)
        generated_files.append(category_file)

    if "line" in requested and month_rows:
        month_file = output_path / f"chart_month_{timestamp}.png"
        _plot_month_totals(month_rows, month_file)
        generated_files.append(month_file)

    if "pie" in requested and category_rows:
        pie_file = output_path / f"chart_pie_{timestamp}.png"
        _plot_category_pie(category_rows, pie_file)
        generated_files.append(pie_file)

    if "scatter" in requested and month_rows:
        scatter_file = output_path / f"chart_scatter_{timestamp}.png"
        _plot_month_scatter(month_rows, scatter_file)
        generated_files.append(scatter_file)

    if "bar3d" in requested and month_rows:
        bar_3d_file = output_path / f"chart_3d_{timestamp}.png"
        _plot_month_bars_3d(month_rows, bar_3d_file)
        generated_files.append(bar_3d_file)

    return generated_files


def _resolve_chart_kinds(kind: str) -> set[str]:
    normalized = kind.strip().lower()
    mapping = {
        "all": {"bar", "line", "pie", "scatter", "bar3d"},
        "category": {"bar"},
        "month": {"line"},
        "bar": {"bar"},
        "line": {"line"},
        "pie": {"pie"},
        "scatter": {"scatter"},
        "bar3d": {"bar3d"},
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


def _plot_category_totals(rows: list[dict[str, Any]], output_file: Path) -> None:
    categories = [str(row["category"]) for row in rows]
    income = [float(row["income"]) for row in rows]
    expense = [float(row["expense"]) for row in rows]

    figure, axis = plt.subplots(figsize=(10, 5))
    positions = range(len(categories))

    axis.bar(positions, income, label="Ingresos", color="#2e7d32")
    axis.bar(positions, expense, label="Gastos", color="#c62828", alpha=0.85)

    axis.set_title("Ingresos y gastos por categoria")
    axis.set_xlabel("Categoria")
    axis.set_ylabel("Monto")
    axis.set_xticks(list(positions))
    axis.set_xticklabels(categories, rotation=30, ha="right")
    axis.legend()

    figure.tight_layout()
    figure.savefig(output_file, dpi=150)
    plt.close(figure)


def _plot_month_totals(rows: list[dict[str, Any]], output_file: Path) -> None:
    months = [str(row["month"]) for row in rows]
    income = [float(row["income"]) for row in rows]
    expense = [float(row["expense"]) for row in rows]
    balance = [float(row["balance"]) for row in rows]

    figure, axis = plt.subplots(figsize=(10, 5))

    axis.plot(months, income, marker="o", label="Ingresos", color="#1565c0")
    axis.plot(months, expense, marker="o", label="Gastos", color="#ef6c00")
    axis.plot(months, balance, marker="o", label="Balance", color="#6a1b9a")

    axis.set_title("Evolucion mensual")
    axis.set_xlabel("Mes")
    axis.set_ylabel("Monto")
    axis.grid(alpha=0.3)
    axis.legend()

    figure.tight_layout()
    figure.savefig(output_file, dpi=150)
    plt.close(figure)


def _plot_category_pie(rows: list[dict[str, Any]], output_file: Path) -> None:
    categories = [str(row["category"]) for row in rows]
    income = [float(row["income"]) for row in rows]
    expense = [float(row["expense"]) for row in rows]

    total_income = sum(income)
    total_expense = sum(expense)

    figure, axes = plt.subplots(1, 2, figsize=(12, 5))

    if total_income > 0:
        axes[0].pie(
            income,
            labels=categories,
            autopct="%1.1f%%",
            startangle=90,
            wedgeprops={"linewidth": 1, "edgecolor": "white"},
        )
        axes[0].set_title("Distribucion de ingresos")
    else:
        axes[0].text(0.5, 0.5, "Sin ingresos", ha="center", va="center")
        axes[0].set_title("Distribucion de ingresos")
        axes[0].axis("off")

    if total_expense > 0:
        axes[1].pie(
            expense,
            labels=categories,
            autopct="%1.1f%%",
            startangle=90,
            wedgeprops={"linewidth": 1, "edgecolor": "white"},
        )
        axes[1].set_title("Distribucion de gastos")
    else:
        axes[1].text(0.5, 0.5, "Sin gastos", ha="center", va="center")
        axes[1].set_title("Distribucion de gastos")
        axes[1].axis("off")

    figure.tight_layout()
    figure.savefig(output_file, dpi=150)
    plt.close(figure)


def _plot_month_scatter(rows: list[dict[str, Any]], output_file: Path) -> None:
    months = [str(row["month"]) for row in rows]
    income = [float(row["income"]) for row in rows]
    expense = [float(row["expense"]) for row in rows]
    balance = [float(row["balance"]) for row in rows]
    positions = np.arange(len(months))

    figure, axis = plt.subplots(figsize=(11, 5))

    axis.scatter(positions, income, s=80, c="#2e7d32", label="Ingresos", alpha=0.9)
    axis.scatter(positions, expense, s=80, c="#c62828", label="Gastos", alpha=0.9)
    axis.plot(positions, balance, c="#1565c0", linewidth=2.2, marker="o", label="Balance")

    axis.set_xticks(positions)
    axis.set_xticklabels(months, rotation=30, ha="right")
    axis.set_title("Grafico de puntos mensual")
    axis.set_xlabel("Mes")
    axis.set_ylabel("Monto")
    axis.grid(alpha=0.3)
    axis.legend()

    figure.tight_layout()
    figure.savefig(output_file, dpi=150)
    plt.close(figure)


def _plot_month_bars_3d(rows: list[dict[str, Any]], output_file: Path) -> None:
    months = [str(row["month"]) for row in rows]
    income = np.array([float(row["income"]) for row in rows], dtype=float)
    expense = np.array([float(row["expense"]) for row in rows], dtype=float)

    x_positions = np.arange(len(months), dtype=float)
    dx = np.full_like(x_positions, 0.35)
    dy = np.full_like(x_positions, 0.35)

    figure = plt.figure(figsize=(11, 6))
    axis = figure.add_subplot(111, projection="3d")

    axis.bar3d(x_positions, np.zeros_like(x_positions), np.zeros_like(x_positions), dx, dy, income, color="#2e7d32")
    axis.bar3d(x_positions, np.ones_like(x_positions), np.zeros_like(x_positions), dx, dy, expense, color="#c62828")

    axis.set_xticks(x_positions + 0.17)
    axis.set_xticklabels(months, rotation=25, ha="right")
    axis.set_yticks([0.17, 1.17])
    axis.set_yticklabels(["Ingresos", "Gastos"])
    axis.set_xlabel("Mes")
    axis.set_ylabel("Tipo")
    axis.set_zlabel("Monto")
    axis.set_title("Barras 3D por mes")

    figure.subplots_adjust(left=0.04, right=0.96, bottom=0.12, top=0.90)
    figure.savefig(output_file, dpi=150)
    plt.close(figure)
