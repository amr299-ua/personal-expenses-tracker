from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

VALID_TRANSACTION_TYPES = {"income", "expense"}
MAX_CATEGORY_LENGTH = 120
MAX_DESCRIPTION_LENGTH = 1000
DEFAULT_CURRENCY = "USD"


class TransactionInput(BaseModel):
    """Validated input for creating or updating a transaction."""

    model_config = ConfigDict(frozen=True)

    amount: float
    transaction_type: str
    category: str = Field(max_length=MAX_CATEGORY_LENGTH)
    transaction_date: date
    description: str = Field(default="", max_length=MAX_DESCRIPTION_LENGTH)
    currency: str = Field(default=DEFAULT_CURRENCY, max_length=3)
    tags: str | None = Field(default=None, max_length=500)
    recurring: bool = Field(default=False)

    def __init__(
        self,
        amount: float,
        transaction_type: str,
        category: str,
        transaction_date: date,
        description: str = "",
        currency: str = DEFAULT_CURRENCY,
        tags: str | None = None,
        recurring: bool = False,
    ) -> None:
        try:
            super().__init__(
                amount=amount,
                transaction_type=transaction_type,
                category=category,
                transaction_date=transaction_date,
                description=description,
                currency=currency,
                tags=tags,
                recurring=recurring,
            )
        except ValidationError as exc:
            raise ValueError(str(exc)) from exc

    @field_validator("transaction_type")
    @classmethod
    def _check_type(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in VALID_TRANSACTION_TYPES:
            raise ValueError(f"Invalid transaction type: {value}. Must be income or expense.")
        return value

    @field_validator("currency")
    @classmethod
    def _check_currency(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("tags")
    @classmethod
    def _check_tags(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            return None
        return stripped

    def to_orm_dict(self) -> dict[str, Any]:
        return {
            "amount": self.amount,
            "transaction_type": self.transaction_type,
            "category": self.category,
            "transaction_date": self.transaction_date,
            "description": self.description.strip(),
            "currency": self.currency,
            "tags": self.tags,
            "recurring": self.recurring,
        }


class CategoryInput(BaseModel):
    """Validated input for creating or updating a category."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1, max_length=MAX_CATEGORY_LENGTH)
    transaction_type: str
    is_active: bool = Field(default=True)
    icon: str | None = Field(default=None, max_length=50)
    color: str | None = Field(default=None, max_length=7)

    @field_validator("transaction_type")
    @classmethod
    def _check_type(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in VALID_TRANSACTION_TYPES:
            raise ValueError(f"Invalid transaction type: {value}. Must be income or expense.")
        return value

    @field_validator("name")
    @classmethod
    def _check_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Category name is required.")
        return stripped

    @field_validator("color")
    @classmethod
    def _check_color(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            return None
        return stripped


class BudgetInput(BaseModel):
    """Validated input for creating or updating a budget."""

    model_config = ConfigDict(frozen=True)

    category: str = Field(min_length=1, max_length=MAX_CATEGORY_LENGTH)
    month: str = Field(min_length=7, max_length=7)  # YYYY-MM
    planned_amount: float = Field(gt=0)

    def __init__(
        self,
        category: str,
        month: str,
        planned_amount: float,
    ) -> None:
        try:
            super().__init__(
                category=category,
                month=month,
                planned_amount=planned_amount,
            )
        except ValidationError as exc:
            raise ValueError(str(exc)) from exc

    @field_validator("category")
    @classmethod
    def _check_category(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Category is required.")
        return stripped

    @field_validator("month")
    @classmethod
    def _check_month(cls, value: str) -> str:
        stripped = value.strip()
        if len(stripped) != 7 or stripped[4] != "-":
            raise ValueError("Month must be in YYYY-MM format.")
        return stripped
