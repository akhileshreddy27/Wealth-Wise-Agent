import os

os.environ["DATABASE_URL"] = "sqlite:///./test.db"

import pytest
from fastapi.testclient import TestClient

from app.db import Base, engine
from app.main import app
from app.services.risk import compute_risk

client = TestClient(app)
ANSWERS = {"market_drop": 3, "primary_goal": 3, "experience": 3, "return_vs_risk": 3, "income_stability": 3}


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


def auth_header(email="a@example.com"):
    r = client.post("/api/auth/signup", json={"email": email, "full_name": "Test", "password": "password123"})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_signup_login_me():
    h = auth_header()
    assert client.get("/api/auth/me", headers=h).json()["has_profile"] is False
    r = client.post("/api/auth/login", json={"email": "A@example.com", "password": "password123"})
    assert r.status_code == 200
    assert client.post("/api/auth/login", json={"email": "a@example.com", "password": "wrongpass1"}).status_code == 401
    assert client.post("/api/auth/signup", json={"email": "a@example.com", "full_name": "X", "password": "password123"}).status_code == 409


def test_profile_requires_auth():
    assert client.get("/api/profile").status_code == 401


def test_profile_upsert():
    h = auth_header()
    assert client.get("/api/profile", headers=h).status_code == 404
    body = {"age": 25, "monthly_income": 80000, "monthly_expenses": 40000, "current_savings": 300000,
            "dependents": 0, "horizon_years": 10, "goals": ["house"], "risk_answers": ANSWERS}
    r = client.put("/api/profile", json=body, headers=h)
    assert r.status_code == 200, r.text
    data = r.json()
    assert 1 <= data["risk_score"] <= 10
    assert data["snapshot"]["monthly_surplus"] == 40000
    assert data["snapshot"]["emergency_fund_ok"] is True
    assert client.get("/api/auth/me", headers=h).json()["has_profile"] is True

    body["risk_answers"] = {"market_drop": 3}
    assert client.put("/api/profile", json=body, headers=h).status_code == 422


def test_capacity_caps_tolerance():
    bold = {k: 4 for k in ANSWERS}
    young, _ = compute_risk(bold, 24, 15, 0, 30000, 300000)
    old, cat = compute_risk(bold, 62, 2, 3, 30000, 10000)
    assert young >= 9
    assert old < young and cat != "aggressive"
