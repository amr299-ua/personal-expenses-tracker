from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

VALID_TRANSACTION_TYPES = {"income", "expense"}


@dataclass(frozen=True)
class TransactionInput:
    amount: float
    transaction_type: str
    category: str
    transaction_date: date
    description: str = ""


class ExpenseDatabase:
    def __init__(self, db_path: str | Path = "data/expenses.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON;")
        return connection

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    amount REAL NOT NULL CHECK(amount > 0),
                    transaction_type TEXT NOT NULL CHECK(transaction_type IN ('income', 'expense')),
                    category TEXT NOT NULL,
                    transaction_date TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_transactions_date
                    ON transactions(transaction_date);

                CREATE INDEX IF NOT EXISTS idx_transactions_category
                    ON transactions(category);
                """
            )

    def add_transaction(self, transaction: TransactionInput) -> int:
        self._validate_transaction(transaction)
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO transactions (
                    amount,
                    transaction_type,
                    category,
                    transaction_date,
                    description
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    transaction.amount,
                    transaction.transaction_type,
                    transaction.category.strip(),
                    transaction.transaction_date.isoformat(),
                    transaction.description.strip(),
                ),
            )
            return int(cursor.lastrowid)

    def fetch_transactions(self, limit: int | None = 50) -> list[dict[str, Any]]:
        with self._connect() as connection:
            if limit is None:
                rows = connection.execute(
                    """
                    SELECT
                        id,
                        amount,
                        transaction_type,
                        category,
                        transaction_date,
                        description,
                        created_at
                    FROM transactions
                    ORDER BY transaction_date DESC, id DESC
                    """
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT
                        id,
                        amount,
                        transaction_type,
                        category,
                        transaction_date,
                        description,
                        created_at
                    FROM transactions
                    ORDER BY transaction_date DESC, id DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
        return [dict(row) for row in rows]

    def get_balance(self) -> float:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT COALESCE(
                    SUM(CASE
                        WHEN transaction_type = 'income' THEN amount
                        ELSE -amount
                    END),
                    0
                ) AS balance
                FROM transactions
                """
            ).fetchone()
        return float(row["balance"])

    def get_totals_by_category(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    category,
                    ROUND(SUM(CASE
                        WHEN transaction_type = 'income' THEN amount
                        ELSE 0
                    END), 2) AS income,
                    ROUND(SUM(CASE
                        WHEN transaction_type = 'expense' THEN amount
                        ELSE 0
                    END), 2) AS expense,
                    ROUND(SUM(CASE
                        WHEN transaction_type = 'income' THEN amount
                        ELSE -amount
                    END), 2) AS balance
                FROM transactions
                GROUP BY category
                ORDER BY category ASC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def get_totals_by_month(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    SUBSTR(transaction_date, 1, 7) AS month,
                    ROUND(SUM(CASE
                        WHEN transaction_type = 'income' THEN amount
                        ELSE 0
                    END), 2) AS income,
                    ROUND(SUM(CASE
                        WHEN transaction_type = 'expense' THEN amount
                        ELSE 0
                    END), 2) AS expense,
                    ROUND(SUM(CASE
                        WHEN transaction_type = 'income' THEN amount
                        ELSE -amount
                    END), 2) AS balance
                FROM transactions
                GROUP BY SUBSTR(transaction_date, 1, 7)
                ORDER BY month ASC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _validate_transaction(transaction: TransactionInput) -> None:
        if transaction.transaction_type not in VALID_TRANSACTION_TYPES:
            raise ValueError(
                f"Tipo invalido: {transaction.transaction_type}. Usa income o expense."
            )

        if transaction.amount <= 0:
            raise ValueError("El monto debe ser mayor a 0.")

        if not transaction.category.strip():
            raise ValueError("La categoria es obligatoria.")
