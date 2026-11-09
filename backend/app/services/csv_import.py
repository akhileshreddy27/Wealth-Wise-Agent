"""Parse a bank-statement style CSV into transaction dicts.

Accepted headers (case-insensitive, first match wins):
  date:        date, txn date, transaction date, value date
  note:        note, description, narration, details, particulars, remarks
  amount:      amount   (negative = expense, positive = income, unless `type` given)
  or debit/credit columns: debit / withdrawal, credit / deposit
  type:        type, kind  (expense|income|debit|credit|dr|cr)  optional
  category:    category    optional (auto-categorised when missing/invalid)

Each row carries `auto_category` (True when the category was guessed) so the caller can refine guesses.
"""
import csv
import io
from datetime import date, datetime

from app.services.categories import EXPENSE_CATEGORIES, INCOME_CATEGORIES, categorize

DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d-%m-%y", "%d %b %Y", "%d-%b-%Y", "%m/%d/%Y"]
ALIASES = {
    "date": ["date", "txn date", "transaction date", "value date"],
    "note": ["note", "description", "narration", "details", "particulars", "remarks"],
    "amount": ["amount"],
    "debit": ["debit", "withdrawal", "withdrawal amt", "debit amount"],
    "credit": ["credit", "deposit", "deposit amt", "credit amount"],
    "type": ["type", "kind", "dr/cr"],
    "category": ["category"],
}


def _parse_date(s: str) -> date:
    s = s.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"unrecognised date '{s}'")


def _num(s: str | None) -> float | None:
    if s is None:
        return None
    s = s.replace(",", "").replace("₹", "").strip()
    return float(s) if s else None


def _safe_num(s: str | None) -> bool:
    try:
        return _num(s) is not None
    except ValueError:
        return False


def parse_csv(content: bytes) -> tuple[list[dict], list[str]]:
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return [], ["File is empty or has no header row"]

    headers = {h.strip().lower(): h for h in reader.fieldnames if h}
    col = {key: next((headers[a] for a in names if a in headers), None) for key, names in ALIASES.items()}
    if not col["date"] or not (col["amount"] or col["debit"] or col["credit"]):
        return [], ["CSV needs a 'date' column and either 'amount' or 'debit'/'credit' columns"]

    raw = list(reader)
    signed = bool(col["amount"]) and any((_num(r.get(col["amount"])) or 0) < 0 for r in raw if _safe_num(r.get(col["amount"])))

    rows, errors = [], []
    for i, row in enumerate(raw, start=2):  # line 1 is the header
        try:
            note = (row.get(col["note"]) or "").strip()[:255] if col["note"] else ""
            kind_hint = (row.get(col["type"]) or "").strip().lower() if col["type"] else ""

            if col["amount"] and _num(row.get(col["amount"])) is not None:
                amt = _num(row[col["amount"]])
                if kind_hint in ("income", "credit", "cr"):
                    kind = "income"
                elif kind_hint in ("expense", "debit", "dr"):
                    kind = "expense"
                elif signed:  # bank style: negative = money out
                    kind = "expense" if amt < 0 else "income"
                else:         # expense-log style: all positive = spend
                    kind = "expense"
                amt = abs(amt)
            else:
                debit, credit = _num(row.get(col["debit"])) if col["debit"] else None, _num(row.get(col["credit"])) if col["credit"] else None
                if debit:
                    kind, amt = "expense", abs(debit)
                elif credit:
                    kind, amt = "income", abs(credit)
                else:
                    raise ValueError("no amount")

            if amt <= 0:
                raise ValueError("amount must be non-zero")

            valid = EXPENSE_CATEGORIES if kind == "expense" else INCOME_CATEGORIES
            cat = (row.get(col["category"]) or "").strip().lower() if col["category"] else ""
            auto = cat not in valid
            if auto:
                cat = categorize(note, kind)

            rows.append({"kind": kind, "amount": round(amt, 2), "category": cat,
                         "date": _parse_date(row[col["date"]]), "note": note, "payment_mode": "other",
                         "auto_category": auto})
        except (ValueError, TypeError, KeyError) as e:
            errors.append(f"Line {i}: {e}")
    return rows, errors
