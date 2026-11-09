from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class FinancialProfile(Base):
    __tablename__ = "financial_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)

    age: Mapped[int] = mapped_column(Integer)
    monthly_income: Mapped[float] = mapped_column(Float)
    monthly_expenses: Mapped[float] = mapped_column(Float)
    current_savings: Mapped[float] = mapped_column(Float, default=0)
    dependents: Mapped[int] = mapped_column(Integer, default=0)
    horizon_years: Mapped[int] = mapped_column(Integer)
    goals: Mapped[list] = mapped_column(JSON, default=list)          # e.g. ["retirement", "house"]
    risk_answers: Mapped[dict] = mapped_column(JSON, default=dict)   # questionnaire answers
    risk_score: Mapped[int] = mapped_column(Integer)                 # 1..10
    risk_category: Mapped[str] = mapped_column(String(20))           # conservative / moderate / aggressive

    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="profile")
