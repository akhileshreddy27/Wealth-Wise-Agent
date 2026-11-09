from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db import get_db
from app.models import FinancialProfile, User
from app.schemas.profile import ProfileIn, ProfileOut
from app.services.risk import QUESTIONNAIRE, compute_risk, financial_snapshot

router = APIRouter(prefix="/profile", tags=["profile"])


def to_out(p: FinancialProfile) -> ProfileOut:
    return ProfileOut.model_validate(
        {
            **{c.name: getattr(p, c.name) for c in FinancialProfile.__table__.columns},
            "snapshot": financial_snapshot(p.monthly_income, p.monthly_expenses, p.current_savings),
        }
    )


@router.get("/questionnaire")
def questionnaire():
    return QUESTIONNAIRE


@router.get("", response_model=ProfileOut)
def get_profile(user: User = Depends(get_current_user)):
    if user.profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Profile not created yet")
    return to_out(user.profile)


@router.put("", response_model=ProfileOut)
def upsert_profile(body: ProfileIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        score, category = compute_risk(
            body.risk_answers, body.age, body.horizon_years, body.dependents,
            body.monthly_expenses, body.current_savings,
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e))

    profile = user.profile or FinancialProfile(user_id=user.id)
    for field, value in body.model_dump().items():
        setattr(profile, field, value)
    profile.risk_score = score
    profile.risk_category = category
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return to_out(profile)
