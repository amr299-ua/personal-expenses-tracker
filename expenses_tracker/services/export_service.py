"""Business logic for exporting reports in multiple formats.

Wraps the lower-level exporters module to provide a service-oriented
interface that can be injected into the GUI layer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

from expenses_tracker.exporters import (
    _compute_category_rows_from_transactions,
    _compute_month_rows_from_transactions,
    export_reports,
)


class ExportService:
    """Service layer for report generation and export."""

    @staticmethod
    def export(
        transactions: list[dict[str, Any]],
        *,
        output_dir: str = "reports",
        fmt: str = "all",
        language: str = "en",
        year_month: str | None = None,
    ) -> list[Path]:
        """Export filtered transactions to the requested format(s).

        Args:
            transactions: Filtered transaction rows.
            output_dir: Destination directory for generated files.
            fmt: Export format key (excel, csv, pdf, json, yaml, html, monthly_pdf, all).
            language: Current UI language for localized headers.
            year_month: Optional YYYY-MM string for monthly reports.

        Returns:
            List of generated file paths.
        """
        category_rows = _compute_category_rows_from_transactions(transactions)
        month_rows = _compute_month_rows_from_transactions(transactions)

        return export_reports(
            transactions=transactions,
            category_rows=category_rows,
            month_rows=month_rows,
            output_dir=output_dir,
            fmt=fmt,
            language=language,
            year_month=year_month,
        )

    @staticmethod
    def compute_category_rows(transactions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Compute aggregated category rows from raw transactions."""
        return _compute_category_rows_from_transactions(transactions)

    @staticmethod
    def compute_month_rows(transactions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Compute aggregated month rows from raw transactions."""
        return _compute_month_rows_from_transactions(transactions)
