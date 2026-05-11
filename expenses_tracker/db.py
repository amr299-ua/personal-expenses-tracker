from __future__ import annotations

import logging
import math
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, cast

logger = logging.getLogger(__name__)

from sqlalchemy import case, delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from expenses_tracker.i18n import tr
from expenses_tracker.models import AuditLogEntry, Base, Budget, Category, ExchangeRate, Transaction, init_engine
from expenses_tracker.schemas import (
    MAX_CATEGORY_LENGTH,
    MAX_DESCRIPTION_LENGTH,
    VALID_TRANSACTION_TYPES,
)
from expenses_tracker.schemas import (
    BudgetInput as _BudgetInput,
)
from expenses_tracker.schemas import (
    CategoryInput as _CategoryInput,
)
from expenses_tracker.schemas import (
    ExchangeRateInput as _ExchangeRateInput,
)
from expenses_tracker.schemas import (
    TransactionInput as _TransactionInput,
)
from expenses_tracker.security import AppCrypto, BackupManager, apply_private_permissions
from expenses_tracker.security import AuditLog as FileAuditLog

# Re-export constants and models for backward compatibility
TransactionInput = _TransactionInput
CategoryInput = _CategoryInput
BudgetInput = _BudgetInput
ExchangeRateInput = _ExchangeRateInput


class ExpenseDatabase:
    """Central repository for all database operations."""

    def __init__(self, db_path: str | Path = "data/expenses.db", cipher_key: str | None = None) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        if self.db_path.parent != Path("."):
            apply_private_permissions(self.db_path.parent, directory=True)
        self.cipher_key = cipher_key
        self.engine = init_engine(str(self.db_path), cipher_key=cipher_key)
        self.Session = sessionmaker(bind=self.engine)

    def initialize(self) -> None:
        """Run Alembic migrations first, falling back to create_all on failure."""
        self._run_alembic_migrations()
        apply_private_permissions(self.db_path)

    def _run_alembic_migrations(self) -> None:
        """Run pending Alembic migrations programmatically.

        Handles existing databases created via create_all by detecting an
        empty alembic_version table (which Alembic normally stamps on first
        migration) and stamping it with the anchor revision before upgrading.
        """
        from alembic import command
        from alembic.config import Config

        alembic_ini = Path("alembic.ini")
        if not alembic_ini.exists():
            logger.info("alembic.ini not found — creating tables via create_all fallback")
            Base.metadata.create_all(self.engine)
            return

        alembic_cfg = Config(str(alembic_ini))
        alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{self.db_path}")

        try:
            command.upgrade(alembic_cfg, "head")
            logger.info("Alembic migrations applied successfully")
            return
        except Exception:
            pass

        # Upgrade failed — likely because the DB was created via create_all
        # and alembic_version is empty. Stamp with the anchor revision
        # (the last version before new migrations) and retry.
        try:
            command.stamp(alembic_cfg, "64a38d947f6f")
            command.upgrade(alembic_cfg, "head")
            logger.info("Alembic migrations applied after stamping")
        except Exception as exc:
            logger.warning("Alembic migration fully failed: %s", exc)
            Base.metadata.create_all(self.engine)

    def _get_or_create_category(self, session: Any, name: str, transaction_type: str) -> Category:
        """Get existing category or create a new one."""
        name = name.strip()
        category = session.execute(select(Category).where(Category.name == name)).scalar_one_or_none()
        if category is None:
            category = Category(
                name=name,
                transaction_type=transaction_type,
                is_active=True,
            )
            session.add(category)
            session.flush()
        assert category is not None
        return cast("Category", category)

    def add_transaction(self, transaction: TransactionInput, language: str = "en") -> int:
        """Insert a new transaction and return its ID."""
        self._validate_transaction(transaction, language)
        with self.Session() as session:
            category_obj = self._get_or_create_category(session, transaction.category, transaction.transaction_type)
            next_date = self._compute_next_recurring(transaction)
            tx = Transaction(
                amount=transaction.amount,
                transaction_type=transaction.transaction_type,
                category_id=category_obj.id,
                category=transaction.category.strip(),
                transaction_date=transaction.transaction_date,
                description=transaction.description.strip(),
                currency=transaction.currency,
                tags=transaction.tags,
                recurring=transaction.recurring,
                recurring_interval=transaction.recurring_interval,
                next_recurring_date=next_date,
            )
            session.add(tx)
            session.commit()
            tx_id = int(tx.id)
        details = f"{transaction.transaction_type} {transaction.amount}"
        self.log_audit(FileAuditLog.ACTION_CREATE, entity="transaction", entity_id=tx_id, details=details)
        return tx_id

    def update_transaction(self, transaction_id: int, transaction: TransactionInput, language: str = "en") -> bool:
        """Update an existing transaction by ID."""
        self._validate_transaction(transaction, language)
        with self.Session() as session:
            tx = session.get(Transaction, transaction_id)
            if tx is None:
                return False

            category_obj = self._get_or_create_category(session, transaction.category, transaction.transaction_type)
            tx.amount = transaction.amount
            tx.transaction_type = transaction.transaction_type
            tx.category_id = category_obj.id
            tx.category = transaction.category.strip()
            tx.transaction_date = transaction.transaction_date
            tx.description = transaction.description.strip()
            tx.currency = transaction.currency
            tx.tags = transaction.tags
            tx.recurring = transaction.recurring
            tx.recurring_interval = transaction.recurring_interval
            tx.next_recurring_date = self._compute_next_recurring(transaction)
            session.commit()
        details = f"{transaction.transaction_type} {transaction.amount}"
        self.log_audit(FileAuditLog.ACTION_UPDATE, entity="transaction", entity_id=transaction_id, details=details)
        return True

    def fetch_transactions(self, limit: int | None = 50) -> list[dict[str, Any]]:
        """Return recent transactions as dicts, optionally limited."""
        if limit is not None and limit <= 0:
            raise ValueError("Limit must be greater than 0.")

        with self.Session() as session:
            stmt = (
                select(Transaction)
                .where(Transaction.deleted_at.is_(None))
                .order_by(Transaction.transaction_date.desc(), Transaction.id.desc())
            )
            if limit is not None:
                stmt = stmt.limit(limit)
            rows = session.execute(stmt).scalars().all()

        return [
            {
                "id": r.id,
                "amount": float(r.amount),
                "transaction_type": r.transaction_type,
                "category": r.category,
                "transaction_date": r.transaction_date.isoformat(),
                "description": r.description,
                "currency": r.currency,
                "tags": r.tags,
                "recurring": r.recurring,
                "recurring_interval": r.recurring_interval,
                "next_recurring_date": r.next_recurring_date.isoformat() if r.next_recurring_date else "",
                "created_at": r.created_at.isoformat() if r.created_at else "",
            }
            for r in rows
        ]

    def get_balance(self) -> float:
        """Return the current balance (income minus expenses)."""
        with self.Session() as session:
            income = session.execute(
                select(func.coalesce(func.sum(Transaction.amount), 0)).where(Transaction.transaction_type == "income")
            ).scalar()
            expense = session.execute(
                select(func.coalesce(func.sum(Transaction.amount), 0)).where(Transaction.transaction_type == "expense")
            ).scalar()
        return float(income or 0) - float(expense or 0)

    def get_totals_by_type(self) -> dict[str, float]:
        """Return aggregated totals for income, expense and balance."""
        with self.Session() as session:
            income = session.execute(
                select(func.coalesce(func.sum(Transaction.amount), 0)).where(Transaction.transaction_type == "income")
            ).scalar()
            expense = session.execute(
                select(func.coalesce(func.sum(Transaction.amount), 0)).where(Transaction.transaction_type == "expense")
            ).scalar()
        income_f = float(income or 0)
        expense_f = float(expense or 0)
        return {
            "income": income_f,
            "expense": expense_f,
            "balance": income_f - expense_f,
        }

    def delete_transaction(self, transaction_id: int) -> bool:
        """Soft-delete a transaction by ID (sets deleted_at timestamp)."""
        with self.Session() as session:
            tx = session.get(Transaction, transaction_id)
            if tx is None:
                return False
            tx.deleted_at = datetime.now(timezone.utc)
            session.commit()
        self.log_audit(FileAuditLog.ACTION_DELETE, entity="transaction", entity_id=transaction_id)
        return True

    def restore_transaction(self, transaction_id: int) -> bool:
        """Restore a soft-deleted transaction by ID."""
        with self.Session() as session:
            tx = session.get(Transaction, transaction_id)
            if tx is None or tx.deleted_at is None:
                return False
            tx.deleted_at = None
            session.commit()
        return True

    def purge_deleted_transactions(self) -> int:
        """Permanently delete all soft-deleted transactions. Returns count."""
        with self.Session() as session:
            count = session.execute(delete(Transaction).where(Transaction.deleted_at.isnot(None)))
            session.commit()
            return cast("int", cast("Any", count).rowcount)

    def fetch_deleted_transactions(self) -> list[dict[str, Any]]:
        """Return soft-deleted transactions."""
        with self.Session() as session:
            rows = (
                session.execute(
                    select(Transaction)
                    .where(Transaction.deleted_at.isnot(None))
                    .order_by(Transaction.deleted_at.desc())
                )
                .scalars()
                .all()
            )

        return [
            {
                "id": r.id,
                "amount": float(r.amount),
                "transaction_type": r.transaction_type,
                "category": r.category,
                "transaction_date": r.transaction_date.isoformat(),
                "description": r.description,
                "currency": r.currency,
                "tags": r.tags,
                "recurring": r.recurring,
                "recurring_interval": r.recurring_interval,
                "next_recurring_date": r.next_recurring_date.isoformat() if r.next_recurring_date else "",
                "created_at": r.created_at.isoformat() if r.created_at else "",
                "deleted_at": r.deleted_at.isoformat() if r.deleted_at else "",
            }
            for r in rows
        ]

    def get_totals_by_category(self) -> list[dict[str, Any]]:
        """Return income, expense and balance grouped by category."""
        with self.Session() as session:
            rows = session.execute(
                select(
                    Transaction.category,
                    func.coalesce(
                        func.sum(case((Transaction.transaction_type == "income", Transaction.amount), else_=0)), 0
                    ).label("income"),
                    func.coalesce(
                        func.sum(case((Transaction.transaction_type == "expense", Transaction.amount), else_=0)), 0
                    ).label("expense"),
                    func.coalesce(
                        func.sum(
                            case(
                                (Transaction.transaction_type == "income", Transaction.amount),
                                else_=-Transaction.amount,
                            )
                        ),
                        0,
                    ).label("balance"),
                )
                .group_by(Transaction.category)
                .order_by(Transaction.category.asc())
            ).all()

        return [
            {
                "category": r.category,
                "income": round(float(r.income), 2),
                "expense": round(float(r.expense), 2),
                "balance": round(float(r.balance), 2),
            }
            for r in rows
        ]

    def get_totals_by_month(self) -> list[dict[str, Any]]:
        """Return income, expense and balance grouped by month."""
        with self.Session() as session:
            rows = session.execute(
                select(
                    func.strftime("%Y-%m", Transaction.transaction_date).label("month"),
                    func.coalesce(
                        func.sum(case((Transaction.transaction_type == "income", Transaction.amount), else_=0)), 0
                    ).label("income"),
                    func.coalesce(
                        func.sum(case((Transaction.transaction_type == "expense", Transaction.amount), else_=0)), 0
                    ).label("expense"),
                    func.coalesce(
                        func.sum(
                            case(
                                (Transaction.transaction_type == "income", Transaction.amount),
                                else_=-Transaction.amount,
                            )
                        ),
                        0,
                    ).label("balance"),
                )
                .group_by(func.strftime("%Y-%m", Transaction.transaction_date))
                .order_by(func.strftime("%Y-%m", Transaction.transaction_date).asc())
            ).all()

        return [
            {
                "month": r.month,
                "income": round(float(r.income), 2),
                "expense": round(float(r.expense), 2),
                "balance": round(float(r.balance), 2),
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Category CRUD
    # ------------------------------------------------------------------

    def add_category(self, category: CategoryInput) -> int:
        """Insert a new category and return its ID."""
        with self.Session() as session:
            cat = Category(
                name=category.name,
                transaction_type=category.transaction_type,
                is_active=category.is_active,
                icon=category.icon,
                color=category.color,
            )
            session.add(cat)
            session.commit()
            return int(cat.id)

    def update_category(self, category_id: int, category: CategoryInput) -> bool:
        """Update an existing category by ID."""
        with self.Session() as session:
            cat = session.get(Category, category_id)
            if cat is None:
                return False
            old_name = cat.name
            cat.name = category.name
            cat.transaction_type = category.transaction_type
            cat.is_active = category.is_active
            cat.icon = category.icon
            cat.color = category.color
            if old_name != category.name:
                session.execute(
                    update(Transaction).where(Transaction.category == old_name).values(category=category.name)
                )
            session.commit()
            return True

    def fetch_categories(self, transaction_type: str | None = None, active_only: bool = True) -> list[dict[str, Any]]:
        """Return categories, optionally filtered by type and active status."""
        with self.Session() as session:
            stmt = select(Category)
            if transaction_type is not None:
                stmt = stmt.where(Category.transaction_type == transaction_type)
            if active_only:
                stmt = stmt.where(Category.is_active.is_(True))
            stmt = stmt.order_by(Category.name.asc())
            rows = session.execute(stmt).scalars().all()

        return [
            {
                "id": r.id,
                "name": r.name,
                "transaction_type": r.transaction_type,
                "is_active": r.is_active,
                "icon": r.icon,
                "color": r.color,
            }
            for r in rows
        ]

    def delete_category(self, category_id: int) -> bool:
        """Delete a category by ID."""
        with self.Session() as session:
            cat = session.get(Category, category_id)
            if cat is None:
                return False
            session.delete(cat)
            session.commit()
            return True

    # ------------------------------------------------------------------
    # Validation (kept for backward compat)
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Budget CRUD
    # ------------------------------------------------------------------

    def add_budget(self, budget: BudgetInput) -> int:
        """Insert or update a budget entry and return its ID."""
        with self.Session() as session:
            existing = session.execute(
                select(Budget).where(
                    Budget.category == budget.category,
                    Budget.month == budget.month,
                )
            ).scalar_one_or_none()
            if existing is not None:
                existing.planned_amount = budget.planned_amount
                session.commit()
                return int(existing.id)
            b = Budget(
                category=budget.category,
                month=budget.month,
                planned_amount=budget.planned_amount,
            )
            session.add(b)
            try:
                session.commit()
                return int(b.id)
            except IntegrityError:
                session.rollback()
                existing = session.execute(
                    select(Budget).where(
                        Budget.category == budget.category,
                        Budget.month == budget.month,
                    )
                ).scalar_one_or_none()
                if existing is not None:
                    existing.planned_amount = budget.planned_amount
                    session.commit()
                    return int(existing.id)
                raise

    def update_budget(self, budget_id: int, budget: BudgetInput) -> bool:
        """Update an existing budget by ID."""
        with self.Session() as session:
            b = session.get(Budget, budget_id)
            if b is None:
                return False
            b.category = budget.category
            b.month = budget.month
            b.planned_amount = budget.planned_amount
            session.commit()
            return True

    def fetch_budgets(self, month: str | None = None) -> list[dict[str, Any]]:
        """Return budgets, optionally filtered by month."""
        with self.Session() as session:
            stmt = select(Budget).order_by(Budget.month.asc(), Budget.category.asc())
            if month is not None:
                stmt = stmt.where(Budget.month == month)
            rows = session.execute(stmt).scalars().all()
        return [
            {
                "id": r.id,
                "category": r.category,
                "month": r.month,
                "planned_amount": float(r.planned_amount),
            }
            for r in rows
        ]

    def delete_budget(self, budget_id: int) -> bool:
        """Delete a budget by ID."""
        with self.Session() as session:
            result = session.execute(delete(Budget).where(Budget.id == budget_id))
            session.commit()
            return cast("bool", cast("Any", result).rowcount > 0)

    def get_budget_vs_actual(self, month: str) -> list[dict[str, Any]]:
        """Compare planned budgets against actual spending for a month."""
        with self.Session() as session:
            actual_rows = session.execute(
                select(
                    Transaction.category,
                    func.coalesce(func.sum(Transaction.amount), 0).label("actual"),
                )
                .where(
                    Transaction.transaction_type == "expense",
                    func.strftime("%Y-%m", Transaction.transaction_date) == month,
                )
                .group_by(Transaction.category)
            ).all()

            budget_rows = session.execute(
                select(Budget.id, Budget.category, Budget.planned_amount).where(Budget.month == month)
            ).all()

        actual_by_cat: dict[str, float] = {r.category: float(r.actual) for r in actual_rows}
        budget_by_cat: dict[str, float] = {}
        budget_id_by_cat: dict[str, int] = {}
        for r in budget_rows:
            budget_by_cat[r.category] = float(r.planned_amount)
            budget_id_by_cat[r.category] = r.id
        all_categories = sorted(set(actual_by_cat.keys()) | set(budget_by_cat.keys()))

        return [
            {
                "category": cat,
                "actual": round(actual_by_cat.get(cat, 0.0), 2),
                "planned": round(budget_by_cat.get(cat, 0.0), 2),
                "difference": round(budget_by_cat.get(cat, 0.0) - actual_by_cat.get(cat, 0.0), 2),
                "id": budget_id_by_cat.get(cat),
            }
            for cat in all_categories
        ]

    # ------------------------------------------------------------------
    # ExchangeRate CRUD
    # ------------------------------------------------------------------

    def add_exchange_rate(self, rate_input: ExchangeRateInput) -> int:
        """Insert or update an exchange rate entry."""
        with self.Session() as session:
            existing = session.execute(
                select(ExchangeRate).where(
                    ExchangeRate.from_currency == rate_input.from_currency,
                    ExchangeRate.to_currency == rate_input.to_currency,
                    ExchangeRate.rate_date == rate_input.rate_date,
                )
            ).scalar_one_or_none()
            if existing is not None:
                existing.rate = rate_input.rate
                session.commit()
                return int(existing.id)
            er = ExchangeRate(
                from_currency=rate_input.from_currency,
                to_currency=rate_input.to_currency,
                rate=rate_input.rate,
                rate_date=rate_input.rate_date,
            )
            session.add(er)
            try:
                session.commit()
                return int(er.id)
            except IntegrityError:
                session.rollback()
                existing = session.execute(
                    select(ExchangeRate).where(
                        ExchangeRate.from_currency == rate_input.from_currency,
                        ExchangeRate.to_currency == rate_input.to_currency,
                        ExchangeRate.rate_date == rate_input.rate_date,
                    )
                ).scalar_one_or_none()
                if existing is not None:
                    existing.rate = rate_input.rate
                    session.commit()
                    return int(existing.id)
                raise

    def fetch_exchange_rates(
        self,
        from_currency: str | None = None,
        to_currency: str | None = None,
        rate_date: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return exchange rates, optionally filtered by currency and date."""
        with self.Session() as session:
            stmt = select(ExchangeRate).order_by(ExchangeRate.rate_date.desc(), ExchangeRate.from_currency.asc())
            if from_currency is not None:
                stmt = stmt.where(ExchangeRate.from_currency == from_currency)
            if to_currency is not None:
                stmt = stmt.where(ExchangeRate.to_currency == to_currency)
            if rate_date is not None:
                stmt = stmt.where(ExchangeRate.rate_date == rate_date)
            rows = session.execute(stmt).scalars().all()
        return [
            {
                "id": r.id,
                "from_currency": r.from_currency,
                "to_currency": r.to_currency,
                "rate": float(r.rate),
                "rate_date": r.rate_date.isoformat(),
            }
            for r in rows
        ]

    def get_exchange_rate(
        self,
        from_currency: str,
        to_currency: str,
        rate_date: str,
    ) -> float | None:
        """Return a single exchange rate or None if not found."""
        with self.Session() as session:
            row = session.execute(
                select(ExchangeRate.rate).where(
                    ExchangeRate.from_currency == from_currency,
                    ExchangeRate.to_currency == to_currency,
                    ExchangeRate.rate_date == rate_date,
                )
            ).scalar_one_or_none()
        if row is None:
            return None
        return float(cast("Any", row))

    def delete_exchange_rate(self, rate_id: int) -> bool:
        """Delete an exchange rate by ID."""
        with self.Session() as session:
            result = session.execute(delete(ExchangeRate).where(ExchangeRate.id == rate_id))
            session.commit()
            return cast("bool", cast("Any", result).rowcount > 0)

    # ------------------------------------------------------------------
    # Automation config
    # ------------------------------------------------------------------

    def get_automation_config(self) -> dict[str, Any]:
        """Return the automation configuration as a dict."""
        with self.Session() as session:
            from expenses_tracker.models import AutomationConfig

            row = session.execute(select(AutomationConfig)).scalar_one_or_none()
            if row is None:
                return {
                    "enabled": False,
                    "schedule_type": "monthly",
                    "schedule_day": 1,
                    "schedule_time": "08:00",
                    "export_format": "excel",
                    "backup_enabled": False,
                    "email_enabled": False,
                    "smtp_host": None,
                    "smtp_port": None,
                    "smtp_user": None,
                    "smtp_password": None,
                    "email_to": None,
                    "email_subject": None,
                    "last_run": None,
                }
            return {
                "enabled": bool(row.enabled),
                "schedule_type": row.schedule_type,
                "schedule_day": row.schedule_day,
                "schedule_time": row.schedule_time,
                "export_format": row.export_format,
                "backup_enabled": bool(row.backup_enabled),
                "email_enabled": bool(row.email_enabled),
                "smtp_host": row.smtp_host,
                "smtp_port": row.smtp_port,
                "smtp_user": row.smtp_user,
                "smtp_password": AppCrypto.decrypt(row.smtp_password),
                "email_to": row.email_to,
                "email_subject": row.email_subject,
                "last_run": row.last_run.isoformat() if row.last_run else None,
            }

    def save_automation_config(self, data: dict[str, Any]) -> None:
        """Persist the automation configuration."""
        from expenses_tracker.models import AutomationConfig

        with self.Session() as session:
            row = session.execute(select(AutomationConfig)).scalar_one_or_none()
            if row is None:
                row = AutomationConfig()
                session.add(row)
            row.enabled = bool(data.get("enabled", False))
            row.schedule_type = str(data.get("schedule_type", "monthly"))
            row.schedule_day = data.get("schedule_day")
            row.schedule_time = str(data.get("schedule_time", "08:00"))
            row.export_format = str(data.get("export_format", "excel"))
            row.backup_enabled = bool(data.get("backup_enabled", False))
            row.email_enabled = bool(data.get("email_enabled", False))
            row.smtp_host = data.get("smtp_host") or None
            row.smtp_port = data.get("smtp_port")
            row.smtp_user = data.get("smtp_user") or None
            smtp_password = data.get("smtp_password")
            row.smtp_password = AppCrypto.encrypt(smtp_password) if smtp_password else None
            row.email_to = data.get("email_to") or None
            row.email_subject = data.get("email_subject") or None
            session.commit()

    # ------------------------------------------------------------------
    # Recurring transactions
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_next_recurring(transaction: TransactionInput) -> date | None:
        """Compute the next recurring date based on interval and transaction date."""
        if not transaction.recurring or not transaction.recurring_interval:
            return None
        from datetime import timedelta

        dt = transaction.transaction_date
        interval = transaction.recurring_interval.strip().lower()
        if interval == "daily":
            return dt + timedelta(days=1)
        if interval == "weekly":
            return dt + timedelta(weeks=1)
        if interval == "monthly":
            if dt.month == 12:
                return dt.replace(year=dt.year + 1, month=1)
            return dt.replace(month=dt.month + 1)
        if interval == "yearly":
            return dt.replace(year=dt.year + 1)
        return None

    def process_recurring_transactions(self) -> int:
        """Create next occurrence for recurring transactions due today. Returns count created."""
        from datetime import date as date_type

        today = date_type.today()
        with self.Session() as session:
            due = (
                session.execute(
                    select(Transaction).where(
                        Transaction.recurring.is_(True),
                        Transaction.recurring_interval.isnot(None),
                        Transaction.next_recurring_date <= today,
                    )
                )
                .scalars()
                .all()
            )

            created = 0
            for tx in due:
                tx_input = TransactionInput(
                    amount=tx.amount,
                    transaction_type=tx.transaction_type,
                    category=tx.category,
                    transaction_date=tx.next_recurring_date,
                    description=tx.description,
                    currency=tx.currency,
                    tags=tx.tags,
                    recurring=True,
                    recurring_interval=tx.recurring_interval,
                )
                next_date = self._compute_next_recurring(tx_input)
                new_tx = Transaction(
                    amount=tx.amount,
                    transaction_type=tx.transaction_type,
                    category_id=tx.category_id,
                    category=tx.category,
                    transaction_date=tx.next_recurring_date,
                    description=tx.description,
                    currency=tx.currency,
                    tags=tx.tags,
                    recurring=True,
                    recurring_interval=tx.recurring_interval,
                    next_recurring_date=next_date,
                )
                session.add(new_tx)
                tx.next_recurring_date = next_date
                created += 1
            session.commit()
            return created

    # ------------------------------------------------------------------
    # Validation (kept for backward compat)
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_transaction(transaction: TransactionInput, language: str = "en") -> None:
        if transaction.transaction_type not in VALID_TRANSACTION_TYPES:
            raise ValueError(tr(language, "invalid_type", value=transaction.transaction_type))

        if not math.isfinite(transaction.amount) or transaction.amount <= 0:
            raise ValueError(tr(language, "amount_positive"))

        if not transaction.category.strip():
            raise ValueError(tr(language, "category_required"))

        if len(transaction.category.strip()) > MAX_CATEGORY_LENGTH:
            raise ValueError(tr(language, "category_too_long", limit=MAX_CATEGORY_LENGTH))

        if len(transaction.description.strip()) > MAX_DESCRIPTION_LENGTH:
            raise ValueError(tr(language, "description_too_long", limit=MAX_DESCRIPTION_LENGTH))

    # ------------------------------------------------------------------
    # Audit logging
    # ------------------------------------------------------------------

    def log_audit(self, action: str, entity: str = "", entity_id: int | None = None, details: str = "") -> None:
        """Record an audit log entry in the database."""
        with self.Session() as session:
            entry = AuditLogEntry(
                action=action,
                entity=entity,
                entity_id=entity_id,
                details=details,
            )
            session.add(entry)
            session.commit()

    def get_audit_log(self, limit: int = 100, action: str | None = None) -> list[dict[str, Any]]:
        """Return recent audit log entries."""
        with self.Session() as session:
            stmt = select(AuditLogEntry).order_by(AuditLogEntry.timestamp.desc())
            if action is not None:
                stmt = stmt.where(AuditLogEntry.action == action)
            if limit is not None:
                stmt = stmt.limit(limit)
            rows = session.execute(stmt).scalars().all()
        return [
            {
                "id": r.id,
                "action": r.action,
                "entity": r.entity,
                "entity_id": r.entity_id,
                "details": r.details,
                "timestamp": r.timestamp.isoformat() if r.timestamp else "",
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Backup
    # ------------------------------------------------------------------

    def create_backup(self) -> Path:
        """Create a timestamped backup of the database."""
        FileAuditLog.log(FileAuditLog.ACTION_BACKUP, entity="database", details=f"Backup of {self.db_path}")
        return BackupManager.create_backup(self.db_path)

    def restore_backup(self, backup_name: str) -> Path:
        """Restore the database from a named backup."""
        FileAuditLog.log(FileAuditLog.ACTION_RESTORE, entity="database", details=f"Restore from {backup_name}")
        return BackupManager.restore_backup(backup_name, self.db_path)

    def list_backups(self) -> list[dict[str, Any]]:
        """Return a list of available backups."""
        return BackupManager.list_backups()
