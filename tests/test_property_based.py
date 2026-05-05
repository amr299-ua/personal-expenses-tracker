"""Property-based tests for the financial engine using Hypothesis."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from expenses_tracker.db import ExpenseDatabase, TransactionInput
from expenses_tracker.schemas import VALID_TRANSACTION_TYPES

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_valid_amounts = st.floats(
    min_value=0.01,
    max_value=1e6,
    allow_nan=False,
    allow_infinity=False,
)

_extreme_amounts = st.one_of(
    st.floats(min_value=0.01, max_value=1.0, allow_nan=False, allow_infinity=False),
    st.floats(min_value=1e6, max_value=1e9, allow_nan=False, allow_infinity=False),
)

_dates = st.dates(
    min_value=date(1900, 1, 1),
    max_value=date(2100, 12, 31),
)

_categories = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N")),
    min_size=1,
    max_size=50,
)

_transaction_types = st.sampled_from(list(VALID_TRANSACTION_TYPES))

_prop_counter = 0


def _prop_db(tmp_path: Path) -> ExpenseDatabase:
    global _prop_counter
    _prop_counter += 1
    db_path = tmp_path / f"prop_{_prop_counter}.db"
    db = ExpenseDatabase(db_path)
    db.initialize()
    return db


# ---------------------------------------------------------------------------
# TransactionInput round-trip properties
# ---------------------------------------------------------------------------


class TestTransactionInputProperties:
    @given(amount=_valid_amounts, tx_date=_dates, category=_categories)
    @settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_any_valid_amount_and_date_creates_input(
        self, amount: float, tx_date: date, category: str
    ):
        tx = TransactionInput(
            amount=amount,
            transaction_type="income",
            category=category,
            transaction_date=tx_date,
        )
        assert tx.amount == pytest.approx(amount)
        assert tx.transaction_date == tx_date

    @given(
        amount=_valid_amounts,
        tx_type=_transaction_types,
        category=_categories,
        tx_date=_dates,
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_round_trip_persists_all_fields(
        self, tmp_path, amount: float, tx_type: str, category: str, tx_date: date
    ):
        db = _prop_db(tmp_path)
        tx = TransactionInput(
            amount=amount,
            transaction_type=tx_type,
            category=category,
            transaction_date=tx_date,
            description="prop test",
        )
        db.add_transaction(tx)
        rows = db.fetch_transactions(limit=None)
        assert len(rows) == 1
        row = rows[0]
        assert row["amount"] == pytest.approx(float(round(amount, 2)))
        assert row["transaction_type"] == tx_type
        assert row["transaction_date"] == tx_date.isoformat()
        assert row["description"] == "prop test"


# ---------------------------------------------------------------------------
# Financial engine extremes
# ---------------------------------------------------------------------------


class TestFinancialEngineProperties:
    @given(amounts=st.lists(_extreme_amounts, min_size=1, max_size=20))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_balance_is_sum_of_income_minus_expense(self, tmp_path, amounts: list[float]):
        db = _prop_db(tmp_path)
        expected_balance = 0.0
        for i, amount in enumerate(amounts):
            tx_type = "income" if i % 2 == 0 else "expense"
            db.add_transaction(
                TransactionInput(
                    amount=amount,
                    transaction_type=tx_type,
                    category="Prop",
                    transaction_date=date(2025, 1, 1),
                )
            )
            if tx_type == "income":
                expected_balance += amount
            else:
                expected_balance -= amount

        balance = db.get_balance()
        assert balance == pytest.approx(expected_balance, rel=1e-2, abs=10.0)

    @given(amounts=st.lists(_extreme_amounts, min_size=1, max_size=20))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_totals_by_type_match_individual_sums(self, tmp_path, amounts: list[float]):
        db = _prop_db(tmp_path)
        expected_income = 0.0
        expected_expense = 0.0
        for i, amount in enumerate(amounts):
            tx_type = "income" if i % 2 == 0 else "expense"
            db.add_transaction(
                TransactionInput(
                    amount=amount,
                    transaction_type=tx_type,
                    category="Prop",
                    transaction_date=date(2025, 1, 1),
                )
            )
            if tx_type == "income":
                expected_income += amount
            else:
                expected_expense += amount

        totals = db.get_totals_by_type()
        assert totals["income"] == pytest.approx(expected_income, rel=1e-2, abs=10.0)
        assert totals["expense"] == pytest.approx(expected_expense, rel=1e-2, abs=10.0)
        assert totals["balance"] == pytest.approx(expected_income - expected_expense, rel=1e-2, abs=10.0)

    @given(
        dates=st.lists(_dates, min_size=1, max_size=15),
        amounts=_extreme_amounts,
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_monthly_grouping_never_crashes(
        self, tmp_path, dates: list[date], amounts: float
    ):
        db = _prop_db(tmp_path)
        for tx_date in dates:
            db.add_transaction(
                TransactionInput(
                    amount=amounts,
                    transaction_type="expense",
                    category="Prop",
                    transaction_date=tx_date,
                )
            )
        month_rows = db.get_totals_by_month()
        assert isinstance(month_rows, list)
        for row in month_rows:
            assert "month" in row
            assert "income" in row
            assert "expense" in row
            assert "balance" in row

    @given(
        start=_dates,
        delta=st.integers(min_value=0, max_value=365 * 200),
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_date_limits_never_crash(self, tmp_path, start: date, delta: int):
        db = _prop_db(tmp_path)
        tx_date = start + timedelta(days=delta)
        db.add_transaction(
            TransactionInput(
                amount=1.0,
                transaction_type="income",
                category="DateTest",
                transaction_date=tx_date,
            )
        )
        rows = db.fetch_transactions(limit=None)
        assert len(rows) == 1
        assert rows[0]["transaction_date"] == tx_date.isoformat()


# ---------------------------------------------------------------------------
# Validation via database layer (schemas alone do not reject these)
# ---------------------------------------------------------------------------


class TestDatabaseValidationProperties:
    @given(
        amount=st.one_of(
            st.floats(max_value=0.0, allow_nan=False, allow_infinity=False),
            st.just(float("nan")),
            st.just(float("inf")),
        )
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_invalid_amount_rejected_by_db(self, tmp_path, amount: float):
        db = _prop_db(tmp_path)
        with pytest.raises(ValueError):
            db.add_transaction(
                TransactionInput(
                    amount=amount,
                    transaction_type="income",
                    category="Test",
                    transaction_date=date(2025, 1, 1),
                )
            )
