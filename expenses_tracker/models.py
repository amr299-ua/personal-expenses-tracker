from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    create_engine,
    event,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker


class Base(DeclarativeBase):
    """SQLAlchemy declarative base class."""


class Category(Base):
    """Expense or income category."""

    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    transaction_type: Mapped[str] = mapped_column(
        String(10), nullable=False, default="expense"
    )  # 'income' or 'expense'
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)
    color: Mapped[str | None] = mapped_column(String(7), nullable=True)  # hex color e.g. #ff0000

    transactions: Mapped[list[Transaction]] = relationship(
        "Transaction", back_populates="category_obj", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        """Return developer-friendly representation."""
        return f"<Category(id={self.id}, name={self.name}, type={self.transaction_type})>"


class Transaction(Base):
    """Financial transaction record."""

    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    amount: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    transaction_type: Mapped[str] = mapped_column(
        String(10), nullable=False
    )  # 'income' or 'expense'
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id"), nullable=True
    )
    # Keep denormalized category name for backwards compatibility and quick reads
    category: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    tags: Mapped[str | None] = mapped_column(String(500), nullable=True)
    recurring: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    category_obj: Mapped[Category | None] = relationship(
        "Category", back_populates="transactions"
    )

    __table_args__ = (
        Index("idx_transactions_date_type", "transaction_date", "transaction_type"),
        Index("idx_transactions_category", "category"),
    )

    def __repr__(self) -> str:
        """Return developer-friendly representation."""
        return (
            f"<Transaction(id={self.id}, amount={self.amount}, "
            f"type={self.transaction_type}, date={self.transaction_date})>"
        )


class Budget(Base):
    """Monthly budget planning entry."""

    __tablename__ = "budgets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(120), nullable=False)
    month: Mapped[str] = mapped_column(String(7), nullable=False)  # YYYY-MM
    planned_amount: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index("idx_budgets_category_month", "category", "month", unique=True),
    )

    def __repr__(self) -> str:
        """Return developer-friendly representation."""
        return f"<Budget(id={self.id}, category={self.category}, month={self.month}, planned={self.planned_amount})>"


class AuditLogEntry(Base):
    """Database-stored audit log record."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    entity: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    details: Mapped[str] = mapped_column(Text, nullable=False, default="")
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index("idx_audit_log_action", "action"),
        Index("idx_audit_log_entity", "entity", "entity_id"),
        Index("idx_audit_log_timestamp", "timestamp"),
    )

    def __repr__(self) -> str:
        """Return developer-friendly representation."""
        return f"<AuditLogEntry(id={self.id}, action={self.action}, entity={self.entity})>"


class ExchangeRate(Base):
    """Currency exchange rate for a specific date."""

    __tablename__ = "exchange_rates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    from_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    to_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    rate: Mapped[float] = mapped_column(Numeric(15, 6), nullable=False)
    rate_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index("idx_exchange_rate_lookup", "from_currency", "to_currency", "rate_date"),
    )

    def __repr__(self) -> str:
        """Return developer-friendly representation."""
        return (
            f"<ExchangeRate(id={self.id}, {self.from_currency}->{self.to_currency}, "
            f"rate={self.rate}, date={self.rate_date})>"
        )


class AutomationConfig(Base):
    """Singleton configuration for scheduled tasks."""

    __tablename__ = "automation_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    schedule_type: Mapped[str] = mapped_column(String(10), nullable=False, default="monthly")
    schedule_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    schedule_time: Mapped[str] = mapped_column(String(5), nullable=False, default="08:00")
    export_format: Mapped[str] = mapped_column(String(10), nullable=False, default="excel")
    backup_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    email_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    smtp_host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    smtp_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    smtp_user: Mapped[str | None] = mapped_column(String(255), nullable=True)
    smtp_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email_to: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email_subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_run: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    def __repr__(self) -> str:
        """Return developer-friendly representation."""
        return f"<AutomationConfig(id={self.id}, enabled={self.enabled}, schedule_type={self.schedule_type})>"


def init_engine(db_path: str, cipher_key: str | None = None) -> Any:
    """Create a SQLAlchemy engine, optionally with SQLCipher encryption."""
    if cipher_key:
        try:
            from pysqlcipher3 import dbapi2 as sqlite
        except ImportError as exc:
            raise ImportError(
                "pysqlcipher3 is required for encrypted databases. "
                "Install it with: pip install pysqlcipher3"
            ) from exc

        def _connect() -> Any:
            conn = sqlite.connect(db_path)
            safe_key = cipher_key.replace("'", "''")
            conn.execute(f"PRAGMA key = '{safe_key}'")
            return conn

        engine = create_engine("sqlite://", creator=_connect, echo=False)
    else:
        engine = create_engine(f"sqlite:///{db_path}", echo=False)

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn: Any, connection_record: Any) -> None:
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()

    return engine


def create_session_maker(engine: Any) -> Any:
    """Return a SQLAlchemy session factory bound to the engine."""
    return sessionmaker(bind=engine)
