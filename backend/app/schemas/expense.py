from datetime import date as Date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.services.categories import EXPENSE_CATEGORIES, INCOME_CATEGORIES

Kind = Literal["expense", "income"]
PaymentMode = Literal["upi", "card", "cash", "netbanking", "other"]


class TransactionIn(BaseModel):
    kind: Kind = "expense"
    amount: float = Field(gt=0, le=1e9)
    category: str | None = None          # omitted -> auto-categorised from note
    date: Date
    note: str = Field(default="", max_length=255)
    payment_mode: PaymentMode = "upi"

    @model_validator(mode="after")
    def check_category(self):
        valid = EXPENSE_CATEGORIES if self.kind == "expense" else INCOME_CATEGORIES
        if self.category is not None and self.category not in valid:
            raise ValueError(f"Invalid {self.kind} category '{self.category}'")
        return self


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: Kind
    amount: float
    category: str
    date: Date
    note: str
    payment_mode: str


class ImportResult(BaseModel):
    imported: int
    skipped: int
    errors: list[str]


class BudgetIn(BaseModel):
    category: str
    monthly_limit: float = Field(ge=0)


class BudgetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    category: str
    monthly_limit: float
