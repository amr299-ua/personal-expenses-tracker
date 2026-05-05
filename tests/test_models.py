"""Tests for SQLAlchemy model definitions and repr."""

from __future__ import annotations

from datetime import date

from expenses_tracker.models import (
    AuditLogEntry,
    AutomationConfig,
    Budget,
    Category,
    Transaction,
)


class TestCategoryRepr:
    def test_repr(self):
        cat = Category(name="Food", transaction_type="expense")
        assert "Food" in repr(cat)
        assert "expense" in repr(cat)


class TestTransactionRepr:
    def test_repr(self):
        tx = Transaction(
            amount=100.0,
            transaction_type="income",
            category="Salary",
            transaction_date=date(2025, 1, 1),
        )
        assert "100" in repr(tx)
        assert "income" in repr(tx)


class TestBudgetRepr:
    def test_repr(self):
        b = Budget(category="Food", month="2025-01", planned_amount=500.0)
        assert "Food" in repr(b)
        assert "500" in repr(b)


class TestAuditLogEntryRepr:
    def test_repr(self):
        entry = AuditLogEntry(action="create", entity="transaction")
        assert "create" in repr(entry)
        assert "transaction" in repr(entry)


class TestAutomationConfigRepr:
    def test_repr(self):
        config = AutomationConfig(enabled=True, schedule_type="daily")
        assert "True" in repr(config)
        assert "daily" in repr(config)
