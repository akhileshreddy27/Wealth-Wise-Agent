from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.transactions import month_range
from app.db import get_db
from app.models import Budget, Transaction, User
from app.schemas.expense import BudgetIn, BudgetOut
from app.services.categories import EXPENSE_CATEGORIES
from app.services.expenses import build_insights, build_summary, month_key, shift_month

router = APIRouter(tags=["expenses"])
MONTH = Query(None, pattern=r"^\d{4}-\d{2}$", description="YYYY-MM, defaults to the current month")


def load_expense_data(db: Session, user: User, month: str):
    start, _ = month_range(shift_month(month, -6))
    _, end = month_range(month)
    txns = list(db.scalars(select(Transaction).where(
        Transaction.user_id == user.id, Transaction.date >= start, Transaction.date < end)))
    budgets = {b.category: b.monthly_limit for b in db.scalars(select(Budget).where(Budget.user_id == user.id))}
    fallback_income = user.profile.monthly_income if user.profile else 0
    return txns, budgets, fallback_income


@router.get("/expenses/summary")
def summary(month: str | None = MONTH, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    month = month or month_key(date.today())
    txns, budgets, income = load_expense_data(db, user, month)
    return build_summary(txns, month, budgets, income)


@router.get("/expenses/insights")
def insights(month: str | None = MONTH, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    month = month or month_key(date.today())
    txns, budgets, income = load_expense_data(db, user, month)
    return build_insights(txns, month, budgets, income)


@router.get("/budgets", response_model=list[BudgetOut])
def list_budgets(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(select(Budget).where(Budget.user_id == user.id).order_by(Budget.category)).all()


@router.put("/budgets", response_model=list[BudgetOut])
def set_budgets(body: list[BudgetIn], user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Upsert budgets. A limit of 0 removes that category's budget."""
    existing = {b.category: b for b in db.scalars(select(Budget).where(Budget.user_id == user.id))}
    for item in body:
        if item.category not in EXPENSE_CATEGORIES:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Unknown category '{item.category}'")
        b = existing.get(item.category)
        if item.monthly_limit == 0:
            if b:
                db.delete(b)
        elif b:
            b.monthly_limit = item.monthly_limit
        else:
            db.add(Budget(user_id=user.id, category=item.category, monthly_limit=item.monthly_limit))
    db.commit()
    return list_budgets(user, db)
