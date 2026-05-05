"""Business logic for transaction filtering, sorting and pagination.

Decouples GUI presentation from data manipulation rules.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from expenses_tracker.db import ExpenseDatabase  # noqa: TC001
from expenses_tracker.utils import filter_transaction_rows as _filter_transaction_rows
from expenses_tracker.utils import safe_parse_date


class TransactionService:
    """Service layer for transaction-related business rules."""

    def __init__(self, database: ExpenseDatabase) -> None:
        self._database = database

    # ------------------------------------------------------------------
    # Data access
    # ------------------------------------------------------------------

    def fetch_all(self) -> list[dict[str, Any]]:
        """Return all transactions from the database."""
        return self._database.fetch_transactions(limit=None)

    def add(self, transaction: Any, language: str = "en") -> int:
        """Add a new transaction and return its ID."""
        return self._database.add_transaction(transaction, language=language)

    def update(self, transaction_id: int, transaction: Any, language: str = "en") -> bool:
        """Update an existing transaction."""
        return self._database.update_transaction(transaction_id, transaction, language=language)

    def delete(self, transaction_id: int) -> bool:
        """Delete a transaction by ID."""
        return self._database.delete_transaction(transaction_id)

    def get_totals_by_type(self) -> dict[str, float]:
        """Return aggregated income, expense and balance totals."""
        return self._database.get_totals_by_type()

    def get_totals_by_category(self) -> list[dict[str, Any]]:
        """Return totals grouped by category."""
        return self._database.get_totals_by_category()

    def get_totals_by_month(self) -> list[dict[str, Any]]:
        """Return totals grouped by month."""
        return self._database.get_totals_by_month()

    # ------------------------------------------------------------------
    # Filtering / sorting / pagination
    # ------------------------------------------------------------------

    @staticmethod
    def filter_rows(
        rows: list[dict[str, Any]],
        *,
        search: str = "",
        selected_type_db: str = "",
        selected_category: str = "All",
        all_label: str = "All",
        date_from: date | None = None,
        date_to: date | None = None,
        type_db_to_display: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        """Apply search, type, category and date filters to transaction rows."""
        return _filter_transaction_rows(
            rows=rows,
            search=search,
            selected_type_db=selected_type_db,
            selected_category=selected_category,
            all_label=all_label,
            date_from=date_from,
            date_to=date_to,
            type_db_to_display=type_db_to_display or {},
        )

    @staticmethod
    def sort_rows(
        rows: list[dict[str, Any]],
        column: str,
        descending: bool,
    ) -> list[dict[str, Any]]:
        """Sort rows by a given column."""

        def _key(row: dict[str, Any]) -> tuple[int, Any]:
            if column == "id":
                return (0, int(row["id"]))
            if column == "amount":
                return (0, float(row["amount"]))
            if column == "date":
                parsed = safe_parse_date(str(row["transaction_date"]))
                return (0, parsed or date.min)
            if column == "type":
                return (0, str(row["transaction_type"]).lower())
            if column == "category":
                return (0, str(row["category"]).lower())
            if column == "description":
                return (0, str(row["description"]).lower())
            return (0, str(row))

        return sorted(rows, key=_key, reverse=descending)

    @staticmethod
    def paginate(
        rows: list[dict[str, Any]],
        page: int,
        page_size: int,
    ) -> tuple[list[dict[str, Any]], int, int]:
        """Return a single page, total pages and clamped page index.

        Returns:
            (page_rows, total_pages, clamped_page)
        """
        total = len(rows)
        total_pages = max(1, (total + page_size - 1) // page_size)
        clamped_page = min(page, total_pages - 1)
        start = clamped_page * page_size
        end = start + page_size
        return rows[start:end], total_pages, clamped_page

    # ------------------------------------------------------------------
    # Date helpers
    # ------------------------------------------------------------------

    @staticmethod
    def parse_date(raw_value: str) -> date | None:
        """Safely parse an ISO date string."""
        return safe_parse_date(raw_value)

    def get_budget_vs_actual(self, month: str) -> list[dict[str, Any]]:
        """Return budget vs actual rows for a given month."""
        return self._database.get_budget_vs_actual(month)
