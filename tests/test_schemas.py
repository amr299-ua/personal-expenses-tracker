"""Tests for Pydantic schema validation edge cases."""

from __future__ import annotations

from datetime import date

import pytest

from expenses_tracker.schemas import (
    BudgetInput,
    CategoryInput,
    TransactionInput,
)


class TestTransactionInputValidation:
    def test_strips_and_lowercases_type(self):
        tx = TransactionInput(100.0, "  INCOME  ", "Salary", date(2025, 1, 1))
        assert tx.transaction_type == "income"

    def test_currency_uppercases(self):
        tx = TransactionInput(100.0, "income", "Salary", date(2025, 1, 1), currency="eur")
        assert tx.currency == "EUR"

    def test_tags_none_when_empty(self):
        tx = TransactionInput(100.0, "income", "Salary", date(2025, 1, 1), tags="   ")
        assert tx.tags is None

    def test_tags_stripped(self):
        tx = TransactionInput(100.0, "income", "Salary", date(2025, 1, 1), tags="  tag1  ")
        assert tx.tags == "tag1"

    def test_invalid_type_raises(self):
        with pytest.raises(ValueError):
            TransactionInput(100.0, "transfer", "Bank", date(2025, 1, 1))

    def test_category_too_long_raises(self):
        with pytest.raises(ValueError):
            TransactionInput(10.0, "income", "x" * 121, date(2025, 1, 1))

    def test_description_too_long_raises(self):
        with pytest.raises(ValueError):
            TransactionInput(10.0, "income", "Cat", date(2025, 1, 1), "x" * 1001)

    def test_to_orm_dict(self):
        tx = TransactionInput(
            amount=100.0,
            transaction_type="income",
            category="Salary",
            transaction_date=date(2025, 1, 1),
            description="test",
            currency="EUR",
            tags="tag1",
            recurring=True,
        )
        d = tx.to_orm_dict()
        assert d["amount"] == 100.0
        assert d["transaction_type"] == "income"
        assert d["category"] == "Salary"
        assert d["transaction_date"] == date(2025, 1, 1)
        assert d["description"] == "test"
        assert d["currency"] == "EUR"
        assert d["tags"] == "tag1"
        assert d["recurring"] is True


class TestCategoryInputValidation:
    def test_name_stripped(self):
        cat = CategoryInput(name="  Food  ", transaction_type="expense")
        assert cat.name == "Food"

    def test_empty_name_raises(self):
        with pytest.raises(ValueError):
            CategoryInput(name="   ", transaction_type="expense")

    def test_invalid_type_raises(self):
        with pytest.raises(ValueError):
            CategoryInput(name="Food", transaction_type="transfer")

    def test_color_none_when_empty(self):
        cat = CategoryInput(name="Food", transaction_type="expense", color="   ")
        assert cat.color is None

    def test_color_stripped(self):
        cat = CategoryInput(name="Food", transaction_type="expense", color="#f00")
        assert cat.color == "#f00"


class TestBudgetInputValidation:
    def test_invalid_month_format_raises(self):
        with pytest.raises(ValueError):
            BudgetInput(category="Food", month="2025/01", planned_amount=100.0)

    def test_empty_category_raises(self):
        with pytest.raises(ValueError):
            BudgetInput(category="   ", month="2025-01", planned_amount=100.0)

    def test_zero_planned_amount_raises(self):
        with pytest.raises(ValueError):
            BudgetInput(category="Food", month="2025-01", planned_amount=0.0)

    def test_negative_planned_amount_raises(self):
        with pytest.raises(ValueError):
            BudgetInput(category="Food", month="2025-01", planned_amount=-10.0)
