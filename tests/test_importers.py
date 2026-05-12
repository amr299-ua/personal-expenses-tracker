"""Tests for the importers module (CSV, Excel, JSON import)."""

from __future__ import annotations

import contextlib
import json
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from expenses_tracker.importers import (
    _col_val,
    _safe_date,
    _safe_float,
    import_and_save,
    import_transactions,
    parse_csv,
    parse_excel,
    parse_json,
)


class TestSafeFloat:
    def test_parses_integer_string(self) -> None:
        assert _safe_float("150") == 150.0

    def test_parses_float_string(self) -> None:
        assert _safe_float("150.75") == 150.75

    def test_handles_comma_separator(self) -> None:
        assert _safe_float("1,500") == 1500.0

    def test_handles_dollar_sign(self) -> None:
        assert _safe_float("$150") == 150.0

    def test_handles_dollar_and_comma(self) -> None:
        assert _safe_float("$1,500.50") == 1500.50

    def test_returns_none_for_empty_string(self) -> None:
        assert _safe_float("") is None

    def test_returns_none_for_invalid_text(self) -> None:
        assert _safe_float("abc") is None

    def test_handles_negative_amount(self) -> None:
        assert _safe_float("-50") == -50.0

    def test_handles_zero(self) -> None:
        assert _safe_float("0") == 0.0

    def test_handles_whitespace(self) -> None:
        assert _safe_float("  200  ") == 200.0


class TestSafeDate:
    def test_parses_iso_format(self) -> None:
        result = _safe_date("2026-05-11")
        assert result == date(2026, 5, 11)

    def test_parses_iso_with_time(self) -> None:
        result = _safe_date("2026-05-11T14:30:00")
        assert result == date(2026, 5, 11)

    def test_parses_dd_mm_yyyy_slash(self) -> None:
        # Use unambiguous date: 15th month doesn't exist, so 15/05 = May 15
        result = _safe_date("15/05/2026")
        assert result == date(2026, 5, 15)

    def test_parses_mm_dd_yyyy_slash_fallback(self) -> None:
        # "15/05" can only be parsed as DD/MM (month 15 doesn't exist),
        # so DD/MM succeeds, and MM/DD is never tried for this value.
        # For ambiguous dates like "05/01", DD/MM wins (tried first).
        result = _safe_date("05/01/2026")
        assert result == date(2026, 1, 5)

    def test_parses_dd_mm_yyyy_dash(self) -> None:
        result = _safe_date("15-05-2026")
        assert result == date(2026, 5, 15)

    def test_parses_yyyy_mm_dd_slash(self) -> None:
        result = _safe_date("2026/05/11")
        assert result == date(2026, 5, 11)

    def test_returns_none_for_empty_string(self) -> None:
        assert _safe_date("") is None

    def test_returns_none_for_invalid_date(self) -> None:
        assert _safe_date("not-a-date") is None

    def test_handles_whitespace(self) -> None:
        result = _safe_date("  2026-05-11  ")
        assert result == date(2026, 5, 11)

    def test_returns_none_for_none(self) -> None:
        assert _safe_date(None) is None  # type: ignore[arg-type]


class TestColVal:
    def test_extracts_value_by_key(self) -> None:
        headers = {"amount": 0, "category": 1, "date": 2}
        row = ("150.00", "Food", "2026-05-11")
        assert _col_val("amount", headers, row) == "150.00"

    def test_returns_empty_for_missing_key(self) -> None:
        headers = {"amount": 0}
        row = ("150.00",)
        assert _col_val("category", headers, row) == ""

    def test_returns_empty_for_out_of_range_index(self) -> None:
        headers = {"amount": 5}
        row = ("150.00",)
        assert _col_val("amount", headers, row) == ""

    def test_handles_none_cell_value(self) -> None:
        headers = {"amount": 0}
        row = (None,)
        assert _col_val("amount", headers, row) == ""

    def test_handles_empty_string_cell(self) -> None:
        headers = {"amount": 0}
        row = ("",)
        assert _col_val("amount", headers, row) == ""

    def test_strips_whitespace(self) -> None:
        headers = {"category": 0}
        row = ("  Food  ",)
        assert _col_val("category", headers, row) == "Food"


class TestParseCSV:
    def test_parses_valid_csv(self) -> None:
        content = (
            "amount,type,category,date,description\n"
            "2500,income,Salary,2026-05-11,Monthly\n"
            "120,expense,Food,2026-05-10,Lunch\n"
        )
        with _temp_csv(content) as path:
            rows = parse_csv(path)
        assert len(rows) == 2
        assert rows[0]["amount"] == 2500.0
        assert rows[0]["transaction_type"] == "income"
        assert rows[0]["category"] == "Salary"
        assert rows[1]["amount"] == 120.0
        assert rows[1]["transaction_type"] == "expense"

    def test_skips_rows_with_invalid_amount(self) -> None:
        content = (
            "amount,type,category,date\n"
            "abc,expense,Food,2026-05-11\n"
            "-10,expense,Food,2026-05-11\n"
            "0,expense,Food,2026-05-11\n"
        )
        with _temp_csv(content) as path:
            rows = parse_csv(path)
        assert len(rows) == 0

    def test_defaults_missing_type_to_expense(self) -> None:
        content = "amount,category,date\n100,Food,2026-05-11\n"
        with _temp_csv(content) as path:
            rows = parse_csv(path)
        assert rows[0]["transaction_type"] == "expense"

    def test_skips_rows_with_invalid_date(self) -> None:
        content = "amount,type,category,date\n100,expense,Food,invalid\n"
        with _temp_csv(content) as path:
            rows = parse_csv(path)
        assert len(rows) == 0

    def test_parses_non_iso_date_format(self) -> None:
        content = "amount,type,category,date\n100,expense,Food,15/05/2026\n"
        with _temp_csv(content) as path:
            rows = parse_csv(path)
        assert rows[0]["transaction_date"] == "2026-05-15"

    def test_parses_currency_field(self) -> None:
        content = "amount,type,category,date,currency\n100,expense,Food,2026-05-11,MXN\n"
        with _temp_csv(content) as path:
            rows = parse_csv(path)
        assert rows[0]["currency"] == "MXN"

    def test_defaults_currency_to_usd(self) -> None:
        content = "amount,type,category,date\n100,expense,Food,2026-05-11\n"
        with _temp_csv(content) as path:
            rows = parse_csv(path)
        assert rows[0]["currency"] == "USD"

    def test_parses_tags(self) -> None:
        content = "amount,type,category,date,tags\n100,expense,Food,2026-05-11,groceries\n"
        with _temp_csv(content) as path:
            rows = parse_csv(path)
        assert rows[0]["tags"] == "groceries"

    def test_parses_recurring_flag(self) -> None:
        content = (
            "amount,type,category,date,recurring\n"
            "100,expense,Food,2026-05-11,true\n"
            "50,expense,Food,2026-05-11,false\n"
        )
        with _temp_csv(content) as path:
            rows = parse_csv(path)
        assert rows[0]["recurring"] is True
        assert rows[1]["recurring"] is False

    def test_skips_empty_amount(self) -> None:
        content = "amount,type,category,date\n,expense,Food,2026-05-11\n"
        with _temp_csv(content) as path:
            rows = parse_csv(path)
        assert len(rows) == 0

    def test_defaults_empty_category_to_other(self) -> None:
        content = "amount,type,category,date\n100,expense,,2026-05-11\n"
        with _temp_csv(content) as path:
            rows = parse_csv(path)
        assert rows[0]["category"] == "other"

    def test_parses_alternate_column_names(self) -> None:
        content = "Amount,Type,Category,Date\n2500,income,Salary,2026-05-11\n"
        with _temp_csv(content) as path:
            rows = parse_csv(path)
        assert len(rows) == 1
        assert rows[0]["amount"] == 2500.0

    def test_handles_bom_csv(self) -> None:
        # Write with BOM using utf-8-sig, omitting the explicit \ufeff prefix
        content = "amount,type,category,date\n100,expense,Food,2026-05-11\n"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8-sig"
        ) as f:
            f.write(content)
            path = Path(f.name)
        try:
            rows = parse_csv(path)
            assert len(rows) == 1
        finally:
            path.unlink()


class TestParseJSON:
    def test_parses_list_format(self) -> None:
        data = [
            {"amount": 100, "type": "expense", "category": "Food", "date": "2026-05-11"},
            {"amount": 2500, "type": "income", "category": "Salary", "date": "2026-05-10"},
        ]
        with _temp_json(data) as path:
            rows = parse_json(path)
        assert len(rows) == 2
        assert rows[0]["amount"] == 100.0
        assert rows[1]["transaction_type"] == "income"

    def test_parses_transactions_key(self) -> None:
        data = {
            "transactions": [
                {"amount": 100, "type": "expense", "category": "Food", "date": "2026-05-11"}
            ]
        }
        with _temp_json(data) as path:
            rows = parse_json(path)
        assert len(rows) == 1

    def test_parses_data_key(self) -> None:
        data = {
            "data": [
                {"amount": 100, "type": "expense", "category": "Food", "date": "2026-05-11"}
            ]
        }
        with _temp_json(data) as path:
            rows = parse_json(path)
        assert len(rows) == 1

    def test_skips_invalid_items(self) -> None:
        data = [
            {"amount": 100, "type": "expense", "category": "Food", "date": "2026-05-11"},
            "not a dict",
            {"amount": -10, "type": "expense", "category": "Food", "date": "2026-05-11"},
        ]
        with _temp_json(data) as path:
            rows = parse_json(path)
        assert len(rows) == 1

    def test_parses_currency_and_tags(self) -> None:
        data = [
            {
                "amount": 100,
                "type": "expense",
                "category": "Food",
                "date": "2026-05-11",
                "currency": "EUR",
                "tags": "lunch",
            }
        ]
        with _temp_json(data) as path:
            rows = parse_json(path)
        assert rows[0]["currency"] == "EUR"
        assert rows[0]["tags"] == "lunch"

    def test_parses_recurring_boolean(self) -> None:
        data = [
            {
                "amount": 100,
                "type": "expense",
                "category": "Food",
                "date": "2026-05-11",
                "recurring": True,
            }
        ]
        with _temp_json(data) as path:
            rows = parse_json(path)
        assert rows[0]["recurring"] is True


class TestParseExcel:
    def test_parses_valid_excel(self) -> None:
        content = [
            ["amount", "type", "category", "date", "description"],
            [2500, "income", "Salary", "2026-05-11", "Monthly"],
            [120, "expense", "Food", "2026-05-10", "Lunch"],
        ]
        with _temp_excel(content) as path:
            rows = parse_excel(path)
        assert len(rows) == 2
        assert rows[0]["amount"] == 2500.0
        assert rows[0]["transaction_type"] == "income"
        assert rows[0]["category"] == "Salary"
        assert rows[1]["amount"] == 120.0

    def test_handles_alternate_headers(self) -> None:
        content = [
            ["Amount", "Transaction_Type", "Category", "Transaction_Date"],
            [100, "expense", "Food", "2026-05-11"],
        ]
        with _temp_excel(content) as path:
            rows = parse_excel(path)
        assert len(rows) == 1

    def test_skips_rows_with_invalid_data(self) -> None:
        content = [
            ["amount", "type", "category", "date"],
            ["abc", "expense", "Food", "2026-05-11"],
        ]
        with _temp_excel(content) as path:
            rows = parse_excel(path)
        assert len(rows) == 0

    def test_skips_rows_without_headers(self) -> None:
        content = [
            ["not_a_header", "also_not", "nope"],
            [100, "expense", "Food"],
        ]
        with _temp_excel(content) as path:
            rows = parse_excel(path)
        assert len(rows) == 0

    def test_parses_currency_and_tags(self) -> None:
        content = [
            ["amount", "type", "category", "date", "currency", "tags"],
            [100, "expense", "Food", "2026-05-11", "EUR", "lunch,quick"],
        ]
        with _temp_excel(content) as path:
            rows = parse_excel(path)
        assert rows[0]["currency"] == "EUR"
        assert rows[0]["tags"] == "lunch,quick"

    def test_parses_recurring(self) -> None:
        content = [
            ["amount", "type", "category", "date", "recurring"],
            [100, "expense", "Food", "2026-05-11", "true"],
        ]
        with _temp_excel(content) as path:
            rows = parse_excel(path)
        assert rows[0]["recurring"] is True

    def test_defaults_empty_category_to_other(self) -> None:
        content = [
            ["amount", "type", "category", "date"],
            [100, "expense", "", "2026-05-11"],
        ]
        with _temp_excel(content) as path:
            rows = parse_excel(path)
        assert rows[0]["category"] == "other"


class TestImportTransactions:
    def test_dispatches_csv(self) -> None:
        content = "amount,type,category,date\n100,expense,Food,2026-05-11\n"
        with _temp_csv(content) as path:
            rows = import_transactions(path)
        assert len(rows) == 1

    def test_dispatches_excel(self) -> None:
        content = [["amount", "type", "category", "date"], [100, "expense", "Food", "2026-05-11"]]
        with _temp_excel(content) as path:
            rows = import_transactions(path)
        assert len(rows) == 1

    def test_dispatches_json(self) -> None:
        data = [{"amount": 100, "type": "expense", "category": "Food", "date": "2026-05-11"}]
        with _temp_json(data) as path:
            rows = import_transactions(path)
        assert len(rows) == 1

    def test_raises_for_unsupported_format(self) -> None:
        with pytest.raises(ValueError, match="Unsupported file format"):
            import_transactions(Path("/tmp/foo.txt"))

    def test_accepts_string_path(self) -> None:
        content = "amount,type,category,date\n100,expense,Food,2026-05-11\n"
        with _temp_csv(content) as tmp:
            rows = import_transactions(str(tmp))
        assert len(rows) == 1


class TestImportAndSave:
    def test_saves_transactions_to_database(self, db: Any) -> None:
        content = (
            "amount,type,category,date\n"
            "2500,income,Salary,2026-05-11\n"
            "120,expense,Food,2026-05-10\n"
        )
        with _temp_csv(content) as path:
            count = import_and_save(path, db)
        assert count == 2
        transactions = db.fetch_transactions()
        assert len(transactions) == 2

    def test_skips_invalid_rows(self, db: Any) -> None:
        content = (
            "amount,type,category,date\n"
            "2500,income,Salary,2026-05-11\n"
            "invalid,expense,Food,2026-05-10\n"
        )
        with _temp_csv(content) as path:
            count = import_and_save(path, db)
        assert count == 1

    def test_returns_zero_for_empty_file(self, db: Any) -> None:
        content = "amount,type,category,date\n"
        with _temp_csv(content) as path:
            count = import_and_save(path, db)
        assert count == 0

    def test_preserves_categories_in_db(self, db: Any) -> None:
        content = "amount,type,category,date\n100,expense,NewCustomCat,2026-05-11\n"
        with _temp_csv(content) as path:
            count = import_and_save(path, db)
        assert count == 1
        transactions = db.fetch_transactions()
        assert transactions[0]["category"] == "NewCustomCat"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _temp_csv(content: str) -> Any:
    """Context manager that creates a temporary CSV file."""

    @contextlib.contextmanager
    def _ctx() -> Any:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write(content)
            path = Path(f.name)
        yield path
        path.unlink()

    return _ctx()


def _temp_json(data: Any) -> Any:
    """Context manager that creates a temporary JSON file."""

    @contextlib.contextmanager
    def _ctx() -> Any:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(data, f)
            path = Path(f.name)
        yield path
        path.unlink()

    return _ctx()


def _temp_excel(rows: list[list[Any]]) -> Any:
    """Context manager that creates a temporary Excel file."""
    import openpyxl

    @contextlib.contextmanager
    def _ctx() -> Any:
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            path = Path(f.name)
        wb = openpyxl.Workbook()
        ws = wb.active
        for row in rows:
            ws.append(row)
        wb.save(path)
        wb.close()
        yield path
        path.unlink()

    return _ctx()
