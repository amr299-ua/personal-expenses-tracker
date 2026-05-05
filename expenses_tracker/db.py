from __future__ import annotations

import math
from pathlib import Path
from typing import Any, cast

from sqlalchemy import case, delete, func, select, update
from sqlalchemy.orm import sessionmaker

from expenses_tracker.i18n import tr
from expenses_tracker.models import AuditLogEntry, Base, Budget, Category, Transaction, init_engine
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
    TransactionInput as _TransactionInput,
)
from expenses_tracker.security import AuditLog as FileAuditLog
from expenses_tracker.security import BackupManager, apply_private_permissions

# Re-export constants and models for backward compatibility
TransactionInput = _TransactionInput
CategoryInput = _CategoryInput
BudgetInput = _BudgetInput


class ExpenseDatabase:
    def __init__(self, db_path: str | Path = "data/expenses.db", cipher_key: str | None = None) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        if self.db_path.parent != Path("."):
            apply_private_permissions(self.db_path.parent, directory=True)
        self.cipher_key = cipher_key
        self.engine = init_engine(str(self.db_path), cipher_key=cipher_key)
        self.Session = sessionmaker(bind=self.engine)

    def initialize(self) -> None:
        """Create all tables and run Alembic migrations if needed."""
        Base.metadata.create_all(self.engine)
        self._run_alembic_migrations()
        apply_private_permissions(self.db_path)

    def _run_alembic_migrations(self) -> None:
        """Run pending Alembic migrations programmatically."""
        from alembic import command
        from alembic.config import Config

        alembic_cfg = Config()
        alembic_cfg.set_main_option("script_location", "alembic")
        alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{self.db_path}")
        try:
            command.upgrade(alembic_cfg, "head")
        except Exception:
            # If Alembic fails (e.g., no versions yet), tables already created via metadata
            pass

    def _get_or_create_category(self, session: Any, name: str, transaction_type: str) -> Category:
        """Get existing category or create a new one."""
        category = session.execute(
            select(Category).where(Category.name == name)
        ).scalar_one_or_none()
        if category is None:
            category = Category(
                name=name,
                transaction_type=transaction_type,
                is_active=True,
            )
            session.add(category)
            session.flush()
        assert category is not None
        return cast(Category, category)

    def add_transaction(self, transaction: TransactionInput, language: str = "en") -> int:
        self._validate_transaction(transaction, language)
        with self.Session() as session:
            category_obj = self._get_or_create_category(
                session, transaction.category, transaction.transaction_type
            )
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
            )
            session.add(tx)
            session.commit()
            tx_id = int(tx.id)
        self.log_audit(FileAuditLog.ACTION_CREATE, entity="transaction", entity_id=tx_id, details=f"{transaction.transaction_type} {transaction.amount}")
        return tx_id

    def update_transaction(self, transaction_id: int, transaction: TransactionInput, language: str = "en") -> bool:
        self._validate_transaction(transaction, language)
        with self.Session() as session:
            tx = session.get(Transaction, transaction_id)
            if tx is None:
                return False

            category_obj = self._get_or_create_category(
                session, transaction.category, transaction.transaction_type
            )
            tx.amount = transaction.amount
            tx.transaction_type = transaction.transaction_type
            tx.category_id = category_obj.id
            tx.category = transaction.category.strip()
            tx.transaction_date = transaction.transaction_date
            tx.description = transaction.description.strip()
            tx.currency = transaction.currency
            tx.tags = transaction.tags
            tx.recurring = transaction.recurring
            session.commit()
        self.log_audit(FileAuditLog.ACTION_UPDATE, entity="transaction", entity_id=transaction_id, details=f"{transaction.transaction_type} {transaction.amount}")
        return True

    def fetch_transactions(self, limit: int | None = 50) -> list[dict[str, Any]]:
        if limit is not None and limit <= 0:
            raise ValueError("Limit must be greater than 0.")

        with self.Session() as session:
            stmt = (
                select(Transaction)
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
                "created_at": r.created_at.isoformat() if r.created_at else "",
            }
            for r in rows
        ]

    def get_balance(self) -> float:
        with self.Session() as session:
            income = session.execute(
                select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                    Transaction.transaction_type == "income"
                )
            ).scalar()
            expense = session.execute(
                select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                    Transaction.transaction_type == "expense"
                )
            ).scalar()
        return float(income or 0) - float(expense or 0)

    def get_totals_by_type(self) -> dict[str, float]:
        with self.Session() as session:
            income = session.execute(
                select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                    Transaction.transaction_type == "income"
                )
            ).scalar()
            expense = session.execute(
                select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                    Transaction.transaction_type == "expense"
                )
            ).scalar()
        income_f = float(income or 0)
        expense_f = float(expense or 0)
        return {
            "income": income_f,
            "expense": expense_f,
            "balance": income_f - expense_f,
        }

    def delete_transaction(self, transaction_id: int) -> bool:
        with self.Session() as session:
            result = session.execute(
                delete(Transaction).where(Transaction.id == transaction_id)
            )
            session.commit()
            deleted = cast(bool, cast(Any, result).rowcount > 0)
        if deleted:
            self.log_audit(FileAuditLog.ACTION_DELETE, entity="transaction", entity_id=transaction_id)
        return deleted

    def get_totals_by_category(self) -> list[dict[str, Any]]:
        with self.Session() as session:
            rows = session.execute(
                select(
                    Transaction.category,
                    func.coalesce(func.sum(
                        case((Transaction.transaction_type == "income", Transaction.amount), else_=0)
                    ), 0).label("income"),
                    func.coalesce(func.sum(
                        case((Transaction.transaction_type == "expense", Transaction.amount), else_=0)
                    ), 0).label("expense"),
                    func.coalesce(func.sum(
                        case((Transaction.transaction_type == "income", Transaction.amount), else_=-Transaction.amount)
                    ), 0).label("balance"),
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
        with self.Session() as session:
            rows = session.execute(
                select(
                    func.strftime("%Y-%m", Transaction.transaction_date).label("month"),
                    func.coalesce(func.sum(
                        case((Transaction.transaction_type == "income", Transaction.amount), else_=0)
                    ), 0).label("income"),
                    func.coalesce(func.sum(
                        case((Transaction.transaction_type == "expense", Transaction.amount), else_=0)
                    ), 0).label("expense"),
                    func.coalesce(func.sum(
                        case((Transaction.transaction_type == "income", Transaction.amount), else_=-Transaction.amount)
                    ), 0).label("balance"),
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
        with self.Session() as session:
            cat = session.get(Category, category_id)
            if cat is None:
                return False
            cat.name = category.name
            cat.transaction_type = category.transaction_type
            cat.is_active = category.is_active
            cat.icon = category.icon
            cat.color = category.color
            session.commit()
            return True

    def fetch_categories(
        self, transaction_type: str | None = None, active_only: bool = True
    ) -> list[dict[str, Any]]:
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
        with self.Session() as session:
            result = session.execute(
                delete(Category).where(Category.id == category_id)
            )
            session.commit()
            return cast(bool, cast(Any, result).rowcount > 0)

    # ------------------------------------------------------------------
    # Validation (kept for backward compat)
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Budget CRUD
    # ------------------------------------------------------------------

    def add_budget(self, budget: BudgetInput) -> int:
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
            session.commit()
            return int(b.id)

    def update_budget(self, budget_id: int, budget: BudgetInput) -> bool:
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
        with self.Session() as session:
            result = session.execute(delete(Budget).where(Budget.id == budget_id))
            session.commit()
            return cast(bool, cast(Any, result).rowcount > 0)

    def get_budget_vs_actual(self, month: str) -> list[dict[str, Any]]:
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
                select(Budget.category, Budget.planned_amount).where(Budget.month == month)
            ).all()

        actual_by_cat = {r.category: float(r.actual) for r in actual_rows}
        budget_by_cat = {r.category: float(r.planned_amount) for r in budget_rows}
        all_categories = sorted(set(actual_by_cat.keys()) | set(budget_by_cat.keys()))

        return [
            {
                "category": cat,
                "actual": round(actual_by_cat.get(cat, 0.0), 2),
                "planned": round(budget_by_cat.get(cat, 0.0), 2),
                "difference": round(budget_by_cat.get(cat, 0.0) - actual_by_cat.get(cat, 0.0), 2),
            }
            for cat in all_categories
        ]

    # ------------------------------------------------------------------
    # Automation config
    # ------------------------------------------------------------------

    def get_automation_config(self) -> dict[str, Any]:
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
                "smtp_password": row.smtp_password,
                "email_to": row.email_to,
                "email_subject": row.email_subject,
                "last_run": row.last_run.isoformat() if row.last_run else None,
            }

    def save_automation_config(self, data: dict[str, Any]) -> None:
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
            row.smtp_password = data.get("smtp_password") or None
            row.email_to = data.get("email_to") or None
            row.email_subject = data.get("email_subject") or None
            session.commit()

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
        FileAuditLog.log(FileAuditLog.ACTION_BACKUP, entity="database", details=f"Backup of {self.db_path}")
        return BackupManager.create_backup(self.db_path)

    def restore_backup(self, backup_name: str) -> Path:
        FileAuditLog.log(FileAuditLog.ACTION_RESTORE, entity="database", details=f"Restore from {backup_name}")
        return BackupManager.restore_backup(backup_name, self.db_path)

    def list_backups(self) -> list[dict[str, Any]]:
        return BackupManager.list_backups()
