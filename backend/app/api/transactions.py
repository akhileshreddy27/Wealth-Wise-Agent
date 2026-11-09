from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.categorizer import ai_categorize
from app.api.deps import get_current_user
from app.db import get_db
from app.models import Transaction, User
from app.schemas.expense import ImportResult, TransactionIn, TransactionOut
from app.services.categories import EXPENSE_CATEGORIES, INCOME_CATEGORIES, categorize
from app.services.csv_import import parse_csv

router = APIRouter(prefix="/transactions", tags=["transactions"])

MAX_UPLOAD_BYTES = 2 * 1024 * 1024
MAX_IMPORT_ROWS = 5000


def month_range(month: str) -> tuple[date, date]:
    """'2026-11' -> (2026-11-01, 2026-12-01)."""
    try:
        y, m = map(int, month.split("-"))
        start = date(y, m, 1)
    except ValueError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "month must be YYYY-MM")
    end = date(y + (m == 12), m % 12 + 1, 1)
    return start, end


def _owned(db: Session, user: User, txn_id: int) -> Transaction:
    txn = db.get(Transaction, txn_id)
    if txn is None or txn.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Transaction not found")
    return txn


@router.get("/categories")
def categories():
    return {"expense": EXPENSE_CATEGORIES, "income": INCOME_CATEGORIES}


@router.get("", response_model=list[TransactionOut])
def list_transactions(
    month: str | None = Query(None, description="YYYY-MM"),
    kind: str | None = Query(None, pattern="^(expense|income)$"),
    category: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = select(Transaction).where(Transaction.user_id == user.id)
    if month:
        start, end = month_range(month)
        q = q.where(Transaction.date >= start, Transaction.date < end)
    if kind:
        q = q.where(Transaction.kind == kind)
    if category:
        q = q.where(Transaction.category == category)
    return db.scalars(q.order_by(Transaction.date.desc(), Transaction.id.desc())).all()


def guess_category(note: str, kind: str) -> str:
    """Keyword rules first; the AI only sees descriptions the rules can't place."""
    cat = categorize(note, kind)
    if cat in ("other", "other_income") and note.strip():
        cat = ai_categorize([(note, kind)]).get(0, cat)
    return cat


@router.post("", response_model=TransactionOut, status_code=status.HTTP_201_CREATED)
def create_transaction(body: TransactionIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    data = body.model_dump()
    data["category"] = data["category"] or guess_category(body.note, body.kind)
    txn = Transaction(user_id=user.id, **data)
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return txn


@router.put("/{txn_id}", response_model=TransactionOut)
def update_transaction(txn_id: int, body: TransactionIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    txn = _owned(db, user, txn_id)
    data = body.model_dump()
    data["category"] = data["category"] or guess_category(body.note, body.kind)
    for k, v in data.items():
        setattr(txn, k, v)
    db.commit()
    db.refresh(txn)
    return txn


@router.delete("/{txn_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(txn_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.delete(_owned(db, user, txn_id))
    db.commit()


@router.post("/import", response_model=ImportResult)
async def import_csv(file: UploadFile = File(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "CSV must be under 2 MB")
    rows, errors = parse_csv(content)
    if len(rows) > MAX_IMPORT_ROWS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"At most {MAX_IMPORT_ROWS} rows per import")

    # One batched AI call for the descriptions the keyword rules filed under "other".
    unsure = [r for r in rows if r.pop("auto_category") and r["category"] in ("other", "other_income") and r["note"]]
    notes = list(dict.fromkeys((r["note"], r["kind"]) for r in unsure))
    guesses = {notes[i]: cat for i, cat in ai_categorize(notes).items()}
    ai_categorized = 0
    for r in unsure:
        if (r["note"], r["kind"]) in guesses:
            r["category"] = guesses[(r["note"], r["kind"])]
            ai_categorized += 1

    # Skip exact duplicates (same date, amount, kind, note) so re-uploading a statement is safe.
    existing = {
        (t.date, round(t.amount, 2), t.kind, t.note)
        for t in db.scalars(select(Transaction).where(Transaction.user_id == user.id))
    }
    imported = skipped = 0
    for r in rows:
        key = (r["date"], r["amount"], r["kind"], r["note"])
        if key in existing:
            skipped += 1
            continue
        existing.add(key)
        db.add(Transaction(user_id=user.id, **r))
        imported += 1
    db.commit()
    return ImportResult(imported=imported, skipped=skipped, errors=errors[:50], ai_categorized=ai_categorized)
