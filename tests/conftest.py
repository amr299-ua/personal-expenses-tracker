"""Shared fixtures for the test suite."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from expenses_tracker.db import ExpenseDatabase, TransactionInput
from expenses_tracker.di import container as _di_container
from expenses_tracker.services import ExportService, TransactionService, UIStateService


@pytest.fixture
def db(tmp_path):
    """Isolated, initialized in-file database for each test."""
    database = ExpenseDatabase(tmp_path / "test.db")
    database.initialize()
    return database


@pytest.fixture
def sample_inputs() -> list[TransactionInput]:
    return [
        TransactionInput(1000.0, "income",  "Salario",      date(2025, 1, 15), "Nómina enero"),
        TransactionInput(500.0,  "income",  "Freelance",    date(2025, 2,  1), "Proyecto web"),
        TransactionInput(200.0,  "expense", "Alimentación", date(2025, 1, 20), "Supermercado"),
        TransactionInput(80.0,   "expense", "Transporte",   date(2025, 1, 25), "Bus mensual"),
        TransactionInput(150.0,  "expense", "Alimentación", date(2025, 2, 10), "Frutería"),
        TransactionInput(300.0,  "expense", "Vivienda",     date(2025, 2, 15), "Alquiler"),
    ]


@pytest.fixture
def populated_db(db, sample_inputs):
    """Database with sample_inputs already inserted."""
    for tx in sample_inputs:
        db.add_transaction(tx)
    return db


# ---------------------------------------------------------------------------
# Reusable row data for charts / exporters tests (no DB needed)
# ---------------------------------------------------------------------------

CATEGORY_ROWS: list[dict[str, Any]] = [
    {"category": "Alimentación", "income": 0.0,    "expense": 350.0, "balance": -350.0},
    {"category": "Freelance",    "income": 500.0,  "expense": 0.0,   "balance":  500.0},
    {"category": "Salario",      "income": 1000.0, "expense": 0.0,   "balance": 1000.0},
    {"category": "Transporte",   "income": 0.0,    "expense": 80.0,  "balance":  -80.0},
    {"category": "Vivienda",     "income": 0.0,    "expense": 300.0, "balance": -300.0},
]

MONTH_ROWS: list[dict[str, Any]] = [
    {"month": "2025-01", "income": 1000.0, "expense": 280.0, "balance":  720.0},
    {"month": "2025-02", "income":  500.0, "expense": 450.0, "balance":   50.0},
]

TRANSACTIONS: list[dict[str, Any]] = [
    {
        "id": 1, "amount": 1000.0, "transaction_type": "income",
        "category": "Salario",      "transaction_date": "2025-01-15",
        "description": "Nómina enero", "created_at": "2025-01-15 10:00:00",
    },
    {
        "id": 2, "amount": 200.0, "transaction_type": "expense",
        "category": "Alimentación", "transaction_date": "2025-01-20",
        "description": "Supermercado", "created_at": "2025-01-20 12:00:00",
    },
    {
        "id": 3, "amount": 500.0, "transaction_type": "income",
        "category": "Freelance",    "transaction_date": "2025-02-01",
        "description": "Proyecto web", "created_at": "2025-02-01 09:00:00",
    },
    {
        "id": 4, "amount": 300.0, "transaction_type": "expense",
        "category": "Vivienda",     "transaction_date": "2025-02-15",
        "description": "Alquiler",    "created_at": "2025-02-15 08:00:00",
    },
]


@pytest.fixture
def di_container(db):
    """Provide a clean DI container with test services registered."""
    _di_container._registry.clear()
    _di_container._singletons.clear()
    from expenses_tracker.services import DatabaseService

    _di_container.register("database", lambda: db, singleton=True)
    _di_container.register("transaction_service", lambda: TransactionService(db), singleton=True)
    _di_container.register("export_service", lambda: ExportService(), singleton=True)
    _di_container.register("state_service", lambda: UIStateService("data/ui_state.json"), singleton=True)
    _di_container.register("database_service", lambda: DatabaseService(db), singleton=True)
    yield _di_container
    _di_container._registry.clear()
    _di_container._singletons.clear()
