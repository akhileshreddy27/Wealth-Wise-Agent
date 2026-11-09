import os

os.environ["DATABASE_URL"] = "sqlite:///./test.db"

import json

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.agents import guard, llm
from app.agents.advisor import GUARD_NAME
from app.core.config import settings
from app.db import Base, engine
from app.main import app
from tests.fakes import ScriptedChatModel, tool_call
from tests.test_recommend import _seed_market, _signup

client = TestClient(app)


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    llm.set_llm(None)


def use_fake(*script) -> ScriptedChatModel:
    fake = ScriptedChatModel(script=list(script))
    llm.set_llm(fake)
    return fake


def last_tool_json(messages) -> dict:
    return json.loads(next(m.content for m in reversed(messages) if isinstance(m, ToolMessage)))


# ---------- number guard ----------
def test_guard_extracts_indian_formats():
    claims = {c.text: (c.value, c.is_pct) for c in guard.extract_claims(
        "Put ₹1,50,000 (₹1.5 lakh) at 7.25% for 3Y; ₹2 Cr goal, ₹41k/month under 80C in 2026")}
    assert claims == {"₹1,50,000": (150000, False), "₹1.5 lakh": (150000, False), "7.25%": (7.25, True),
                      "₹2 Cr": (2e7, False), "₹41k": (41000, False), "2026": (2026, False)}


def test_guard_accepts_grounded_and_rounded_figures():
    tool = {"monthly": 41313, "equity": 0.65, "expected_return": 0.1028, "sharpe": 1.2486, "text": "rate 7.5% p.a."}
    ok = guard.check("Invest ₹41,313 a month (about ₹41,000), 65% in equity, expecting 10.3% (roughly 10%). "
                     "Sharpe 1.25, FD at 7.5%. Keep 6 months of expenses aside; 80C allows ₹1.5 lakh.", tool)
    assert ok.ok, ok.unverified


def test_guard_flags_invented_figures():
    r = guard.check("You'll earn 14% and have ₹99,000 extra by 2030.", {"monthly": 41313})
    assert not r.ok and r.unverified == ["14%", "₹99,000"]
    assert guard.check("Your goal is ₹25,00,000.", {"x": 1}, "I want ₹25,00,000 for a house").ok  # user's own figure


# ---------- provider config ----------
def test_llm_status_and_groq_client(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "groq")
    monkeypatch.setattr(settings, "groq_api_key", "")
    monkeypatch.setattr(settings, "llm_api_key", "")
    st = llm.llm_status()
    assert not st["enabled"] and "GROQ_API_KEY" in st["reason"] and llm.get_llm() is None

    monkeypatch.setattr(settings, "groq_api_key", "gsk_test")
    st = llm.llm_status()
    assert st == {"enabled": True, "provider": "groq", "model": "llama-3.3-70b-versatile", "reason": None}
    model = llm.get_llm()
    assert model.model_name == "llama-3.3-70b-versatile" and "api.groq.com" in str(model.openai_api_base)

    monkeypatch.setattr(settings, "llm_provider", "ollama")
    monkeypatch.setattr(settings, "groq_api_key", "")
    assert llm.llm_status()["enabled"]        # local models need no key
    monkeypatch.setattr(settings, "llm_provider", "none")
    assert "turned off" in llm.llm_status()["reason"]
    assert client.get("/api/agent/status").json()["enabled"] is False


# ---------- advisor agent ----------
def _plan_answer(messages) -> AIMessage:
    p = last_tool_json(messages)
    return AIMessage(content=f"You can invest ₹{p['investable_monthly']:,.0f} a month. "
                             f"{p['allocation_pct']['equity']:.0f}% goes to equity for an expected "
                             f"{p['expected_return_pct']}% a year.")


def test_chat_calls_tools_and_is_grounded():
    _seed_market()
    h = _signup()
    use_fake(tool_call("get_investment_plan", {"tax_regime": "new"}), _plan_answer)
    r = client.post("/api/agent/chat", headers=h, json={"messages": [{"role": "user", "content": "Explain my plan"}]})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["grounded"] and data["unverified"] == []
    assert data["tool_calls"] == [{"name": "get_investment_plan", "args": {"tax_regime": "new"}}]
    assert "₹50,000" in data["reply"]


def test_chat_retries_when_numbers_are_made_up():
    _seed_market()
    h = _signup()
    fake = use_fake(tool_call("get_investment_plan"),
                    AIMessage(content="You'll make 37.7% a year, guaranteed."),   # invented
                    _plan_answer)
    data = client.post("/api/agent/chat", headers=h, json={"messages": [{"role": "user", "content": "Returns?"}]}).json()
    assert data["grounded"]
    feedback = fake.seen[-1][-1]
    assert isinstance(feedback, HumanMessage) and feedback.name == GUARD_NAME and "37.7%" in feedback.content


def test_chat_flags_figures_it_cannot_verify():
    h = _signup()
    use_fake(AIMessage(content="Nifty will return 22% next year."), AIMessage(content="Expect about 22% next year."))
    data = client.post("/api/agent/chat", headers=h, json={"messages": [{"role": "user", "content": "Nifty?"}]}).json()
    assert not data["grounded"] and data["unverified"] == ["22%"]


def test_chat_tools_cover_stocks_funds_fds_goals_and_expenses():
    _seed_market()
    h = _signup()
    calls = [("lookup_stock", {"symbol": "s1"}), ("get_fund_rankings", {"category": "debt"}),
             ("get_fd_options", {"years": 3, "amount": 200000}), ("plan_goal_sip", {"goal_amount": 1000000, "years": 5}),
             ("get_expense_summary", {}), ("get_stock_scores", {"top_n": 2}), ("get_financial_snapshot", {})]
    results = {}

    def capture(name):
        def reply(messages):
            results[name] = last_tool_json(messages)
            return AIMessage(content="Done.")
        return reply

    for name, args in calls:
        use_fake(tool_call(name, args), capture(name))
        r = client.post("/api/agent/chat", headers=h, json={"messages": [{"role": "user", "content": name}]})
        assert r.status_code == 200, r.text
    assert results["lookup_stock"]["symbol"] == "S1" and results["lookup_stock"]["rank_in_nifty50"] >= 1
    assert results["get_fund_rankings"]["funds"][0]["category"] == "Debt"
    assert results["get_fd_options"]["best"]["rate"] > 0 and results["get_fd_options"]["tenure_years"] == 3
    assert results["plan_goal_sip"]["monthly_sip"] > 0 and results["plan_goal_sip"]["monthly_budget"] == 50000
    assert results["get_expense_summary"]["spent"] == 0
    assert len(results["get_stock_scores"]["picks"]) == 2
    assert results["get_financial_snapshot"]["monthly_surplus"] == 50000


def test_chat_errors():
    h = _signup()
    body = {"messages": [{"role": "user", "content": "hi"}]}
    assert client.post("/api/agent/chat", headers=h, json=body).status_code == 503   # AI off

    class RateLimitError(Exception):
        pass

    def boom(_):
        raise RateLimitError("429")
    use_fake(boom)
    assert client.post("/api/agent/chat", headers=h, json=body).status_code == 429
    bad = {"messages": [{"role": "assistant", "content": "hi"}]}
    assert client.post("/api/agent/chat", headers=h, json=bad).status_code == 422


# ---------- explain my plan ----------
def _explain_from_prompt(messages) -> AIMessage:
    p = json.loads(messages[-1].content.split("as JSON:\n\n", 1)[1].split("\n\nExplain", 1)[0])
    return AIMessage(content=f"**First step** Invest ₹{p['investable_monthly']:,.0f}/month. "
                             f"**Why this mix** {p['allocation_pct']['equity']:.0f}% equity.")


def test_explain_plan_rules_fallback_and_ai():
    _seed_market()
    h = _signup()
    r = client.get("/api/agent/explain-plan", headers=h).json()
    assert r["source"] == "rules" and "**First step**" in r["text"] and "₹50,000" in r["text"] and r["reason"]

    use_fake(_explain_from_prompt)
    r = client.get("/api/agent/explain-plan", headers=h).json()
    assert r["source"] == "ai" and "₹50,000/month" in r["text"]

    use_fake(AIMessage(content="Expect 37.7% returns."), AIMessage(content="Still 37.7%."))
    r = client.get("/api/agent/explain-plan", headers=h).json()
    assert r["source"] == "rules" and "couldn't be verified" in r["reason"]


# ---------- AI categoriser ----------
def test_csv_import_uses_ai_for_unknown_descriptions():
    h = _signup()
    csv = (b"Date,Narration,Amount\n01/06/2026,Swiggy,-400\n02/06/2026,PAYTM*CHAIPOINT,-120\n"
           b"03/06/2026,NEFT XYZ TRADERS,-5000\n04/06/2026,UPI-RAHUL,-300\n")

    def answer(messages):
        text = messages[-1].content
        assert "Swiggy" not in text            # keyword rules already handled it
        return AIMessage(content='Sure: {"1": "dining", "2": "shopping", "3": "not-a-category"}')
    use_fake(answer)
    r = client.post("/api/transactions/import", headers=h, files={"file": ("s.csv", csv, "text/csv")}).json()
    assert r["imported"] == 4 and r["ai_categorized"] == 2
    cats = {t["note"]: t["category"] for t in client.get("/api/transactions", headers=h).json()}
    assert cats == {"Swiggy": "dining", "PAYTM*CHAIPOINT": "dining", "NEFT XYZ TRADERS": "shopping", "UPI-RAHUL": "other"}


def test_single_transaction_ai_fallback_and_failure():
    h = _signup()
    use_fake(AIMessage(content='{"1": "health"}'), AIMessage(content="not json"))
    t = {"kind": "expense", "amount": 900, "date": "2026-06-05", "note": "Dr Mehta consult", "payment_mode": "upi", "category": None}
    assert client.post("/api/transactions", headers=h, json=t).json()["category"] == "health"
    t["note"] = "Mystery shop"
    assert client.post("/api/transactions", headers=h, json=t).json()["category"] == "other"
