"""Shared utility functions used by GUI and services.

Moving these here breaks the circular dependency between gui.py
and the services layer.
"""

from __future__ import annotations

from datetime import date

INCOME_CATEGORY_KEYS = [
    "salary",
    "business_income",
    "freelance",
    "interest",
    "dividends",
    "sale",
    "refund",
    "gift",
    "extra_income",
    "investment",
    "other",
]

EXPENSE_CATEGORY_KEYS = [
    "food",
    "electricity",
    "water",
    "gas",
    "transport",
    "rent",
    "internet",
    "phone",
    "health",
    "education",
    "leisure",
    "taxes",
    "home",
    "pets",
    "subscriptions",
    "investment",
    "other",
]


def category_options_for_type(language: str, type_key: str) -> list[str]:
    """Return translated category names for a transaction type."""
    from expenses_tracker.i18n import tr

    keys = INCOME_CATEGORY_KEYS if type_key == "income" else EXPENSE_CATEGORY_KEYS
    return [tr(language, f"category_{key}") for key in keys]


def safe_parse_date(raw_value: str) -> date | None:
    """Safely parse an ISO date string, returning None on failure."""
    value = raw_value.strip()
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def filter_transaction_rows(
    rows: list[dict[str, object]],
    search: str,
    selected_type_db: str,
    selected_category: str,
    all_label: str,
    date_from: date | None,
    date_to: date | None,
    type_db_to_display: dict[str, str],
) -> list[dict[str, object]]:
    """Filter transaction rows by search, type, category and date range."""
    normalized_search = search.strip().lower()
    normalized_category = selected_category.strip().lower()
    normalized_all_label = all_label.strip().lower()

    filtered: list[dict[str, object]] = []
    for row in rows:
        row_type = str(row["transaction_type"]).lower()
        row_category = str(row["category"]).strip().lower()
        row_date = safe_parse_date(str(row["transaction_date"]))

        if selected_type_db and row_type != selected_type_db:
            continue
        if normalized_category != normalized_all_label and row_category != normalized_category:
            continue
        if date_from and not row_date:
            continue
        if date_to and not row_date:
            continue
        if date_from and row_date and row_date < date_from:
            continue
        if date_to and row_date and row_date > date_to:
            continue

        if normalized_search:
            searchable = " ".join(
                [
                    str(row["id"]),
                    str(row["transaction_date"]),
                    type_db_to_display.get(str(row["transaction_type"]), str(row["transaction_type"])),
                    str(row["category"]),
                    str(row["amount"]),
                    str(row["description"]),
                ]
            ).lower()
            if normalized_search not in searchable:
                continue

        filtered.append(row)

    return filtered
