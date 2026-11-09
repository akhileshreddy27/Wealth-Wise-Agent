from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Goal = Literal["emergency_fund", "retirement", "house", "education", "car", "travel", "wealth_creation"]


class ProfileIn(BaseModel):
    age: int = Field(ge=18, le=100)
    monthly_income: float = Field(ge=0)
    monthly_expenses: float = Field(ge=0)
    current_savings: float = Field(ge=0, default=0)
    dependents: int = Field(ge=0, le=20, default=0)
    horizon_years: int = Field(ge=1, le=50)
    goals: list[Goal] = Field(default_factory=list)
    risk_answers: dict[str, int]


class Snapshot(BaseModel):
    monthly_surplus: float
    savings_rate: float
    emergency_fund_target: float
    emergency_fund_months: float | None
    emergency_fund_ok: bool


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    age: int
    monthly_income: float
    monthly_expenses: float
    current_savings: float
    dependents: int
    horizon_years: int
    goals: list[str]
    risk_answers: dict[str, int]
    risk_score: int
    risk_category: str
    updated_at: datetime | None = None
    snapshot: Snapshot
