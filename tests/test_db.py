"""Tests for the ExpenseDatabase and TransactionInput data layer."""

from __future__ import annotations

import sqlite3
from datetime import date

import pytest

from expenses_tracker.db import ExpenseDatabase, TransactionInput
from expenses_tracker.schemas import (
    MAX_CATEGORY_LENGTH,
    MAX_DESCRIPTION_LENGTH,
    VALID_TRANSACTION_TYPES,
)

# ---------------------------------------------------------------------------
# initialize()
# ---------------------------------------------------------------------------


class TestInitialize:
    def test_creates_transactions_table(self, tmp_path):
        db = ExpenseDatabase(tmp_path / "test.db")
        db.initialize()

        with sqlite3.connect(tmp_path / "test.db") as conn:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='transactions'"
            ).fetchone()
        assert row is not None

    def test_creates_date_type_index(self, tmp_path):
        db = ExpenseDatabase(tmp_path / "test.db")
        db.initialize()

        with sqlite3.connect(tmp_path / "test.db") as conn:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_transactions_date_type'"
            ).fetchone()
        assert row is not None

    def test_creates_category_index(self, tmp_path):
        db = ExpenseDatabase(tmp_path / "test.db")
        db.initialize()

        with sqlite3.connect(tmp_path / "test.db") as conn:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_transactions_category'"
            ).fetchone()
        assert row is not None

    def test_idempotent(self, tmp_path):
        db = ExpenseDatabase(tmp_path / "test.db")
        db.initialize()
        db.initialize()  # must not raise

    def test_creates_parent_directory(self, tmp_path):
        nested = tmp_path / "nested" / "dir" / "test.db"
        db = ExpenseDatabase(nested)
        db.initialize()
        assert nested.exists()


# ---------------------------------------------------------------------------
# add_transaction()
# ---------------------------------------------------------------------------


class TestAddTransaction:
    def test_returns_integer_id(self, db):
        tx = TransactionInput(100.0, "income", "Salario", date(2025, 1, 1))
        result = db.add_transaction(tx)
        assert isinstance(result, int)
        assert result >= 1

    def test_ids_are_sequential(self, db):
        t1 = TransactionInput(100.0, "income",  "Salario",     date(2025, 1, 1))
        t2 = TransactionInput(50.0,  "expense", "Alimentación", date(2025, 1, 2))
        id1 = db.add_transaction(t1)
        id2 = db.add_transaction(t2)
        assert id2 == id1 + 1

    def test_persists_all_fields(self, db):
        tx = TransactionInput(123.45, "expense", "Ocio", date(2025, 3, 10), "Cine")
        row_id = db.add_transaction(tx)
        rows = db.fetch_transactions(limit=None)
        row = next(r for r in rows if r["id"] == row_id)
        assert row["amount"] == 123.45
        assert row["transaction_type"] == "expense"
        assert row["category"] == "Ocio"
        assert row["transaction_date"] == "2025-03-10"
        assert row["description"] == "Cine"

    def test_strips_whitespace_from_category(self, db):
        tx = TransactionInput(50.0, "income", "  Salario  ", date(2025, 1, 1))
        row_id = db.add_transaction(tx)
        rows = db.fetch_transactions(limit=None)
        row = next(r for r in rows if r["id"] == row_id)
        assert row["category"] == "Salario"

    def test_strips_whitespace_from_description(self, db):
        tx = TransactionInput(50.0, "income", "Salario", date(2025, 1, 1), "  nota  ")
        row_id = db.add_transaction(tx)
        rows = db.fetch_transactions(limit=None)
        row = next(r for r in rows if r["id"] == row_id)
        assert row["description"] == "nota"

    def test_raises_for_invalid_type(self, db):
        with pytest.raises(ValueError):
            tx = TransactionInput(100.0, "transfer", "Banco", date(2025, 1, 1))
            db.add_transaction(tx)

    def test_raises_for_zero_amount(self, db):
        with pytest.raises(ValueError):
            TransactionInput(0.0, "income", "Salario", date(2025, 1, 1))

    def test_raises_for_negative_amount(self, db):
        with pytest.raises(ValueError):
            TransactionInput(-10.0, "expense", "Ocio", date(2025, 1, 1))

    def test_raises_for_nan_amount(self, db):
        with pytest.raises(ValueError):
            TransactionInput(float("nan"), "expense", "Ocio", date(2025, 1, 1))

    def test_raises_for_infinite_amount(self, db):
        tx = TransactionInput(float("inf"), "expense", "Ocio", date(2025, 1, 1))
        with pytest.raises(ValueError):
            db.add_transaction(tx)

    def test_raises_for_empty_category(self, db):
        tx = TransactionInput(10.0, "expense", "", date(2025, 1, 1))
        with pytest.raises(ValueError):
            db.add_transaction(tx)

    def test_raises_for_whitespace_only_category(self, db):
        tx = TransactionInput(10.0, "expense", "   ", date(2025, 1, 1))
        with pytest.raises(ValueError):
            db.add_transaction(tx)

    def test_raises_for_too_long_category(self, db):
        with pytest.raises(ValueError, match="category"):
            tx = TransactionInput(10.0, "expense", "x" * (MAX_CATEGORY_LENGTH + 1), date(2025, 1, 1))
            db.add_transaction(tx)

    def test_raises_for_too_long_description(self, db):
        with pytest.raises(ValueError, match="description"):
            tx = TransactionInput(
                10.0,
                "expense",
                "Ocio",
                date(2025, 1, 1),
                "x" * (MAX_DESCRIPTION_LENGTH + 1),
            )
            db.add_transaction(tx)

    def test_localized_error_message(self, db):
        with pytest.raises(ValueError):
            TransactionInput(0.0, "income", "Salario", date(2025, 1, 1))


# ---------------------------------------------------------------------------
# update_transaction()
# ---------------------------------------------------------------------------


class TestUpdateTransaction:
    def test_updates_existing_transaction(self, db):
        row_id = db.add_transaction(TransactionInput(100.0, "income", "Salario", date(2025, 1, 1)))

        updated = db.update_transaction(
            row_id,
            TransactionInput(75.0, "expense", "Food", date(2025, 1, 2), "Lunch"),
        )

        rows = db.fetch_transactions(limit=None)
        assert updated is True
        assert len(rows) == 1
        assert rows[0]["amount"] == 75.0
        assert rows[0]["transaction_type"] == "expense"
        assert rows[0]["category"] == "Food"
        assert rows[0]["transaction_date"] == "2025-01-02"
        assert rows[0]["description"] == "Lunch"

    def test_returns_false_for_missing_transaction(self, db):
        updated = db.update_transaction(
            999,
            TransactionInput(75.0, "expense", "Food", date(2025, 1, 2)),
        )
        assert updated is False

    def test_validates_updated_transaction(self, db):
        row_id = db.add_transaction(TransactionInput(100.0, "income", "Salario", date(2025, 1, 1)))

        with pytest.raises(ValueError):
            db.update_transaction(row_id, TransactionInput(0.0, "expense", "Food", date(2025, 1, 2)))


# ---------------------------------------------------------------------------
# fetch_transactions()
# ---------------------------------------------------------------------------


class TestFetchTransactions:
    def test_empty_database_returns_empty_list(self, db):
        assert db.fetch_transactions() == []

    def test_returns_list_of_dicts(self, populated_db):
        rows = populated_db.fetch_transactions()
        assert isinstance(rows, list)
        assert all(isinstance(r, dict) for r in rows)

    def test_dict_has_expected_keys(self, populated_db):
        expected = {
            "id", "amount", "transaction_type", "category",
            "transaction_date", "description", "currency",
            "tags", "recurring", "created_at",
        }
        row = populated_db.fetch_transactions(limit=1)[0]
        assert set(row.keys()) == expected

    def test_default_limit_is_50(self, db):
        for _ in range(60):
            db.add_transaction(TransactionInput(1.0, "income", "Cat", date(2025, 1, 1)))
        assert len(db.fetch_transactions()) == 50

    def test_custom_limit(self, populated_db):
        rows = populated_db.fetch_transactions(limit=3)
        assert len(rows) == 3

    def test_zero_limit_raises_value_error(self, populated_db):
        with pytest.raises(ValueError, match="greater than 0"):
            populated_db.fetch_transactions(limit=0)

    def test_negative_limit_raises_value_error(self, populated_db):
        with pytest.raises(ValueError, match="greater than 0"):
            populated_db.fetch_transactions(limit=-1)

    def test_none_limit_returns_all(self, populated_db):
        rows = populated_db.fetch_transactions(limit=None)
        assert len(rows) == 6  # sample_inputs has 6 entries

    def test_ordered_newest_first(self, db):
        db.add_transaction(TransactionInput(10.0, "income", "A", date(2025, 1, 1)))
        db.add_transaction(TransactionInput(20.0, "income", "B", date(2025, 3, 1)))
        db.add_transaction(TransactionInput(30.0, "income", "C", date(2025, 2, 1)))
        rows = db.fetch_transactions(limit=None)
        dates = [r["transaction_date"] for r in rows]
        assert dates == sorted(dates, reverse=True)


# ---------------------------------------------------------------------------
# get_balance()
# ---------------------------------------------------------------------------


class TestGetBalance:
    def test_empty_database_returns_zero(self, db):
        assert db.get_balance() == 0.0

    def test_returns_float(self, populated_db):
        assert isinstance(populated_db.get_balance(), float)

    def test_correct_calculation(self, db):
        db.add_transaction(TransactionInput(1000.0, "income",  "Salario",     date(2025, 1, 1)))
        db.add_transaction(TransactionInput(200.0,  "expense", "Alimentación", date(2025, 1, 2)))
        db.add_transaction(TransactionInput(300.0,  "expense", "Vivienda",    date(2025, 1, 3)))
        assert db.get_balance() == pytest.approx(500.0)

    def test_only_income(self, db):
        db.add_transaction(TransactionInput(500.0, "income", "Salario", date(2025, 1, 1)))
        assert db.get_balance() == pytest.approx(500.0)

    def test_only_expenses(self, db):
        db.add_transaction(TransactionInput(200.0, "expense", "Ocio", date(2025, 1, 1)))
        assert db.get_balance() == pytest.approx(-200.0)


# ---------------------------------------------------------------------------
# get_totals_by_type()
# ---------------------------------------------------------------------------


class TestGetTotalsByType:
    def test_empty_database_returns_zeroes(self, db):
        totals = db.get_totals_by_type()
        assert totals["income"] == pytest.approx(0.0)
        assert totals["expense"] == pytest.approx(0.0)
        assert totals["balance"] == pytest.approx(0.0)

    def test_returns_expected_keys(self, populated_db):
        totals = populated_db.get_totals_by_type()
        assert set(totals.keys()) == {"income", "expense", "balance"}

    def test_correct_totals(self, populated_db):
        totals = populated_db.get_totals_by_type()
        assert totals["income"] == pytest.approx(1500.0)
        assert totals["expense"] == pytest.approx(730.0)
        assert totals["balance"] == pytest.approx(770.0)


# ---------------------------------------------------------------------------
# get_totals_by_category()
# ---------------------------------------------------------------------------


class TestGetTotalsByCategory:
    def test_empty_database_returns_empty_list(self, db):
        assert db.get_totals_by_category() == []

    def test_returns_expected_keys(self, populated_db):
        rows = populated_db.get_totals_by_category()
        expected_keys = {"category", "income", "expense", "balance"}
        assert all(set(r.keys()) == expected_keys for r in rows)

    def test_groups_by_category(self, populated_db):
        rows = populated_db.get_totals_by_category()
        categories = {r["category"] for r in rows}
        assert categories == {"Salario", "Freelance", "Alimentación", "Transporte", "Vivienda"}

    def test_alimentacion_sums_both_months(self, populated_db):
        rows = populated_db.get_totals_by_category()
        ali = next(r for r in rows if r["category"] == "Alimentación")
        assert ali["expense"] == pytest.approx(350.0)  # 200 + 150
        assert ali["income"] == pytest.approx(0.0)

    def test_balance_is_income_minus_expense(self, populated_db):
        rows = populated_db.get_totals_by_category()
        for row in rows:
            assert row["balance"] == pytest.approx(row["income"] - row["expense"], abs=0.01)

    def test_ordered_alphabetically(self, populated_db):
        rows = populated_db.get_totals_by_category()
        cats = [r["category"] for r in rows]
        assert cats == sorted(cats)


# ---------------------------------------------------------------------------
# get_totals_by_month()
# ---------------------------------------------------------------------------


class TestGetTotalsByMonth:
    def test_empty_database_returns_empty_list(self, db):
        assert db.get_totals_by_month() == []

    def test_returns_expected_keys(self, populated_db):
        rows = populated_db.get_totals_by_month()
        expected_keys = {"month", "income", "expense", "balance"}
        assert all(set(r.keys()) == expected_keys for r in rows)

    def test_groups_by_yyyy_mm(self, populated_db):
        rows = populated_db.get_totals_by_month()
        months = {r["month"] for r in rows}
        assert months == {"2025-01", "2025-02"}

    def test_month_format_is_yyyy_mm(self, populated_db):
        rows = populated_db.get_totals_by_month()
        import re
        for row in rows:
            assert re.match(r"^\d{4}-\d{2}$", row["month"])

    def test_january_totals(self, populated_db):
        rows = populated_db.get_totals_by_month()
        jan = next(r for r in rows if r["month"] == "2025-01")
        assert jan["income"] == pytest.approx(1000.0)
        assert jan["expense"] == pytest.approx(280.0)   # 200 + 80
        assert jan["balance"] == pytest.approx(720.0)

    def test_ordered_chronologically(self, populated_db):
        rows = populated_db.get_totals_by_month()
        months = [r["month"] for r in rows]
        assert months == sorted(months)


# ---------------------------------------------------------------------------
# delete_transaction()
# ---------------------------------------------------------------------------


class TestDeleteTransaction:
    def test_returns_false_when_missing(self, db):
        assert db.delete_transaction(9999) is False

    def test_deletes_existing_transaction(self, db):
        tx = TransactionInput(120.0, "expense", "Ocio", date(2025, 4, 20))
        tx_id = db.add_transaction(tx)
        assert db.delete_transaction(tx_id) is True
        assert db.fetch_transactions(limit=None) == []

    def test_deletes_only_target(self, db):
        id_a = db.add_transaction(TransactionInput(10.0, "income", "Salario", date(2025, 1, 1)))
        id_b = db.add_transaction(TransactionInput(20.0, "expense", "Ocio", date(2025, 1, 2)))
        assert db.delete_transaction(id_a) is True
        rows = db.fetch_transactions(limit=None)
        assert len(rows) == 1
        assert rows[0]["id"] == id_b


# ---------------------------------------------------------------------------
# TransactionInput dataclass
# ---------------------------------------------------------------------------


class TestTransactionInput:
    def test_is_frozen(self):
        tx = TransactionInput(100.0, "income", "Salario", date(2025, 1, 1))
        with pytest.raises((AttributeError, TypeError, ValueError)):
            tx.amount = 200.0

    def test_default_description_is_empty(self):
        tx = TransactionInput(100.0, "income", "Salario", date(2025, 1, 1))
        assert tx.description == ""


# ---------------------------------------------------------------------------
# VALID_TRANSACTION_TYPES constant
# ---------------------------------------------------------------------------


def test_valid_transaction_types_contains_income_and_expense():
    assert {"income", "expense"} == VALID_TRANSACTION_TYPES
