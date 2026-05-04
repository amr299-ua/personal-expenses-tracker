"""Tests for GUI helper logic that does not require a Tk window."""

from __future__ import annotations

from datetime import date

from expenses_tracker.gui import category_options_for_type, filter_transaction_rows, safe_parse_date


ROWS = [
    {
        "id": 1,
        "amount": 1000.0,
        "transaction_type": "income",
        "category": "Salary",
        "transaction_date": "2026-04-01",
        "description": "Monthly payroll",
    },
    {
        "id": 2,
        "amount": 120.0,
        "transaction_type": "expense",
        "category": "Food",
        "transaction_date": "2026-04-10",
        "description": "Groceries",
    },
    {
        "id": 3,
        "amount": 50.0,
        "transaction_type": "expense",
        "category": "Transport",
        "transaction_date": "2026-05-02",
        "description": "Train",
    },
]


TYPE_LABELS = {"income": "Income", "expense": "Expense"}


def test_category_options_use_income_categories():
    options = category_options_for_type("en", "income")
    assert "Salary" in options
    assert "Food" not in options


def test_category_options_use_expense_categories_by_default():
    options = category_options_for_type("en", "expense")
    assert "Food" in options
    assert "Salary" not in options


def test_safe_parse_date_returns_date_for_iso_value():
    assert safe_parse_date("2026-04-29") == date(2026, 4, 29)


def test_safe_parse_date_returns_none_for_invalid_or_empty_values():
    assert safe_parse_date("") is None
    assert safe_parse_date("not-a-date") is None


def test_filter_transaction_rows_filters_by_type():
    result = filter_transaction_rows(ROWS, "", "expense", "All", "All", None, None, TYPE_LABELS)
    assert [row["id"] for row in result] == [2, 3]


def test_filter_transaction_rows_filters_by_category():
    result = filter_transaction_rows(ROWS, "", "", "Food", "All", None, None, TYPE_LABELS)
    assert [row["id"] for row in result] == [2]


def test_filter_transaction_rows_filters_by_date_range():
    result = filter_transaction_rows(
        ROWS,
        "",
        "",
        "All",
        "All",
        date(2026, 4, 1),
        date(2026, 4, 30),
        TYPE_LABELS,
    )
    assert [row["id"] for row in result] == [1, 2]


def test_filter_transaction_rows_searches_localized_type_and_description():
    result = filter_transaction_rows(ROWS, "expense", "", "All", "All", None, None, TYPE_LABELS)
    assert [row["id"] for row in result] == [2, 3]

    result = filter_transaction_rows(ROWS, "payroll", "", "All", "All", None, None, TYPE_LABELS)
    assert [row["id"] for row in result] == [1]
