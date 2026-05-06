"""Tests for TransactionService business logic."""

from __future__ import annotations

from datetime import date

import pytest

from expenses_tracker.db import TransactionInput
from expenses_tracker.services import TransactionService


@pytest.fixture
def svc(db):
    return TransactionService(db)


@pytest.fixture
def populated_svc(populated_db):
    return TransactionService(populated_db)


class TestTransactionServiceDataAccess:
    def test_fetch_all_empty_db(self, svc):
        assert svc.fetch_all() == []

    def test_fetch_all_returns_rows(self, populated_svc):
        rows = populated_svc.fetch_all()
        assert len(rows) == 6

    def test_add_transaction(self, svc):
        tx = TransactionInput(50.0, "expense", "Coffee", date(2025, 3, 1), "Morning")
        tx_id = svc.add(tx)
        assert tx_id == 1
        rows = svc.fetch_all()
        assert len(rows) == 1
        assert rows[0]["amount"] == 50.0

    def test_update_existing(self, populated_svc):
        rows = populated_svc.fetch_all()
        first_id = rows[0]["id"]
        tx = TransactionInput(999.0, "income", "Bonus", date(2025, 3, 1), "Updated")
        assert populated_svc.update(first_id, tx) is True
        updated = populated_svc.fetch_all()
        assert any(r["id"] == first_id and r["amount"] == 999.0 for r in updated)

    def test_update_missing_returns_false(self, populated_svc):
        tx = TransactionInput(1.0, "expense", "X", date(2025, 3, 1), "")
        assert populated_svc.update(9999, tx) is False

    def test_delete_existing(self, populated_svc):
        rows = populated_svc.fetch_all()
        first_id = rows[0]["id"]
        assert populated_svc.delete(first_id) is True
        assert len(populated_svc.fetch_all()) == 5

    def test_delete_missing_returns_false(self, populated_svc):
        assert populated_svc.delete(9999) is False


class TestTransactionServiceAggregation:
    def test_get_totals_by_type(self, populated_svc):
        totals = populated_svc.get_totals_by_type()
        assert totals["income"] == 1500.0
        assert totals["expense"] == 730.0
        assert totals["balance"] == 770.0

    def test_get_totals_by_category(self, populated_svc):
        rows = populated_svc.get_totals_by_category()
        assert len(rows) == 5
        food = next(r for r in rows if r["category"] == "Alimentación")
        assert food["expense"] == 350.0

    def test_get_totals_by_month(self, populated_svc):
        rows = populated_svc.get_totals_by_month()
        assert len(rows) == 2
        jan = next(r for r in rows if r["month"] == "2025-01")
        assert jan["income"] == 1000.0
        assert jan["expense"] == 280.0


class TestTransactionServiceFiltering:
    ROWS = [
        {
            "id": 1,
            "transaction_date": "2025-01-01",
            "transaction_type": "income",
            "category": "Salary",
            "amount": 1000.0,
            "description": "Pay",
        },
        {
            "id": 2,
            "transaction_date": "2025-01-02",
            "transaction_type": "expense",
            "category": "Food",
            "amount": 20.0,
            "description": "Lunch",
        },
        {
            "id": 3,
            "transaction_date": "2025-02-01",
            "transaction_type": "expense",
            "category": "Rent",
            "amount": 500.0,
            "description": "Home",
        },
    ]

    def test_filter_by_type(self):
        result = TransactionService.filter_rows(self.ROWS, selected_type_db="expense")
        assert [r["id"] for r in result] == [2, 3]

    def test_filter_by_category(self):
        result = TransactionService.filter_rows(self.ROWS, selected_category="Food", all_label="All")
        assert [r["id"] for r in result] == [2]

    def test_filter_by_date_range(self):
        result = TransactionService.filter_rows(
            self.ROWS,
            date_from=date(2025, 1, 1),
            date_to=date(2025, 1, 31),
        )
        assert [r["id"] for r in result] == [1, 2]

    def test_filter_by_search(self):
        result = TransactionService.filter_rows(self.ROWS, search="lunch")
        assert [r["id"] for r in result] == [2]


class TestTransactionServiceSorting:
    ROWS = [
        {
            "id": 3,
            "transaction_date": "2025-01-01",
            "transaction_type": "expense",
            "category": "Z",
            "amount": 10.0,
            "description": "B",
        },
        {
            "id": 1,
            "transaction_date": "2025-01-02",
            "transaction_type": "income",
            "category": "A",
            "amount": 100.0,
            "description": "A",
        },
        {
            "id": 2,
            "transaction_date": "2025-01-03",
            "transaction_type": "expense",
            "category": "M",
            "amount": 50.0,
            "description": "C",
        },
    ]

    def test_sort_by_id_ascending(self):
        result = TransactionService.sort_rows(self.ROWS, "id", descending=False)
        assert [r["id"] for r in result] == [1, 2, 3]

    def test_sort_by_amount_descending(self):
        result = TransactionService.sort_rows(self.ROWS, "amount", descending=True)
        assert [r["amount"] for r in result] == [100.0, 50.0, 10.0]

    def test_sort_by_date(self):
        result = TransactionService.sort_rows(self.ROWS, "date", descending=False)
        assert [r["id"] for r in result] == [3, 1, 2]

    def test_sort_by_category(self):
        result = TransactionService.sort_rows(self.ROWS, "category", descending=False)
        assert [r["category"] for r in result] == ["A", "M", "Z"]

    def test_sort_by_description(self):
        result = TransactionService.sort_rows(self.ROWS, "description", descending=False)
        assert [r["description"] for r in result] == ["A", "B", "C"]


class TestTransactionServicePagination:
    ROWS = [{"id": i, "amount": 10.0} for i in range(25)]

    def test_paginate_first_page(self):
        rows, total_pages, page = TransactionService.paginate(self.ROWS, page=0, page_size=10)
        assert rows == [{"id": i, "amount": 10.0} for i in range(10)]
        assert total_pages == 3
        assert page == 0

    def test_paginate_clamps_page(self):
        rows, total_pages, page = TransactionService.paginate(self.ROWS, page=99, page_size=10)
        assert page == 2
        assert rows == [{"id": i, "amount": 10.0} for i in range(20, 25)]

    def test_paginate_empty(self):
        rows, total_pages, page = TransactionService.paginate([], page=0, page_size=10)
        assert rows == []
        assert total_pages == 1
        assert page == 0


class TestTransactionServiceHelpers:
    def test_parse_date_valid(self):
        assert TransactionService.parse_date("2025-04-01") == date(2025, 4, 1)

    def test_parse_date_invalid(self):
        assert TransactionService.parse_date("bad") is None
        assert TransactionService.parse_date("") is None
