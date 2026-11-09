import os

os.environ["DATABASE_URL"] = "sqlite:///./test.db"

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.db import Base, engine
from app.main import app
from app.services.categories import categorize
from app.services.csv_import import parse_csv

client = TestClient(app)
M = "2026-11"


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def h():
    r = client.post("/api/auth/signup", json={"email": "e@example.com", "full_name": "E", "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def add(h, amount, d, note="", category=None, kind="expense"):
    body = {"amount": amount, "date": d, "note": note, "kind": kind}
    if category:
        body["category"] = category
    r = client.post("/api/transactions", json=body, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


def test_categorize_rules():
    assert categorize("Swiggy order #123") == "dining"
    assert categorize("NETFLIX.COM") == "subscriptions"
    assert categorize("Uber trip") == "transport"
    assert categorize("random thing") == "other"
    assert categorize("ACME salary Nov", "income") == "salary"


def test_crud_and_isolation(h):
    t = add(h, 450, "2026-11-03", "Zomato dinner")
    assert t["category"] == "dining"  # auto-categorised

    upd = client.put(f"/api/transactions/{t['id']}", json={**t, "amount": 500, "category": "groceries"}, headers=h)
    assert upd.json()["amount"] == 500 and upd.json()["category"] == "groceries"

    assert len(client.get(f"/api/transactions?month={M}", headers=h).json()) == 1
    assert client.get("/api/transactions?month=2026-10", headers=h).json() == []

    # Another user can't see or delete it
    r = client.post("/api/auth/signup", json={"email": "x@example.com", "full_name": "X", "password": "password123"})
    other = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client.get("/api/transactions", headers=other).json() == []
    assert client.delete(f"/api/transactions/{t['id']}", headers=other).status_code == 404

    assert client.delete(f"/api/transactions/{t['id']}", headers=h).status_code == 204
    assert client.get("/api/transactions", headers=h).json() == []


def test_invalid_category_rejected(h):
    r = client.post("/api/transactions", json={"amount": 10, "date": "2026-11-01", "category": "salary"}, headers=h)
    assert r.status_code == 422


def test_summary_and_budgets(h):
    add(h, 100000, "2026-11-01", "Salary", kind="income")
    add(h, 30000, "2026-11-02", "Rent", "rent")
    add(h, 12000, "2026-11-05", "Amazon", "shopping")
    add(h, 8000, "2026-11-10", "Swiggy", "dining")
    add(h, 5000, "2026-10-10", "Swiggy", "dining")

    client.put("/api/budgets", json=[{"category": "shopping", "monthly_limit": 10000}, {"category": "travel", "monthly_limit": 5000}], headers=h)
    s = client.get(f"/api/expenses/summary?month={M}", headers=h).json()
    assert s["income"] == 100000 and s["expense"] == 50000 and s["savings_rate"] == 0.5
    cats = {c["category"]: c for c in s["categories"]}
    assert cats["shopping"]["budget_used"] == 1.2
    assert cats["travel"]["amount"] == 0  # budget with no spend still listed
    assert s["buckets"] == {"needs": 30000, "wants": 20000, "savings": 50000}
    assert [t["month"] for t in s["trend"]][-2:] == ["2026-10", "2026-11"]

    # limit 0 removes budget
    client.put("/api/budgets", json=[{"category": "travel", "monthly_limit": 0}], headers=h)
    assert [b["category"] for b in client.get("/api/budgets", headers=h).json()] == ["shopping"]

    ins = client.get(f"/api/expenses/insights?month={M}", headers=h).json()
    types = [i["type"] for i in ins["insights"]]
    assert "over_budget" in types and "savings_rate" in types and "top_want" in types
    assert ins["insights"][0]["severity"] == "danger"


def test_recurring_and_spike_detection(h):
    add(h, 60000, "2026-11-01", "Salary", kind="income")
    for m in ("2026-09", "2026-10", "2026-11"):
        add(h, 649, f"{m}-05", "Netflix")
    for m, amt in (("2026-08", 3000), ("2026-09", 3200), ("2026-10", 2900), ("2026-11", 9000)):
        add(h, amt, f"{m}-12", "Swiggy", "dining")

    ins = client.get(f"/api/expenses/insights?month={M}", headers=h).json()
    assert any(r["name"] == "Netflix" and r["monthly_amount"] == 649 for r in ins["recurring"])
    spike = next(i for i in ins["insights"] if i["type"] == "spike")
    assert spike["category"] == "dining"
    assert ins["potential_monthly_saving"] > 0


def test_csv_parse_formats():
    signed = b"Date,Narration,Amount\n01/11/2026,SALARY ACME,85000\n02/11/2026,UPI-ZOMATO,-450\nbad,x,1\n"
    rows, errors = parse_csv(signed)
    assert [(r["kind"], r["category"]) for r in rows] == [("income", "salary"), ("expense", "dining")]
    assert rows[0]["date"] == date(2026, 11, 1) and len(errors) == 1

    debit_credit = b"Txn Date,Description,Debit,Credit\n2026-11-03,Uber,250,\n2026-11-04,Interest,,120\n"
    rows, _ = parse_csv(debit_credit)
    assert [(r["kind"], r["amount"], r["category"]) for r in rows] == [("expense", 250, "transport"), ("income", 120, "interest")]

    rows, errors = parse_csv(b"foo,bar\n1,2\n")
    assert rows == [] and errors


def test_csv_import_dedupes(h):
    csv = b"date,note,amount\n2026-11-01,Swiggy,300\n2026-11-02,Blinkit,800\n"
    r = client.post("/api/transactions/import", files={"file": ("s.csv", csv, "text/csv")}, headers=h).json()
    assert r == {"imported": 2, "skipped": 0, "errors": [], "ai_categorized": 0}
    r = client.post("/api/transactions/import", files={"file": ("s.csv", csv, "text/csv")}, headers=h).json()
    assert r["imported"] == 0 and r["skipped"] == 2


def test_inr_format_and_investments_count_as_saving(h):
    from app.services.expenses import inr
    assert (inr(229737), inr(999), inr(12345678)) == ("₹2,29,737", "₹999", "₹1,23,45,678")
    add(h, 50000, "2026-11-01", "Salary", kind="income")
    add(h, 10000, "2026-11-02", "SIP Groww", "investments")
    add(h, 20000, "2026-11-03", "Rent", "rent")
    s = client.get(f"/api/expenses/summary?month={M}", headers=h).json()
    assert s["net"] == 30000 and s["savings_rate"] == 0.6 and s["invested"] == 10000
