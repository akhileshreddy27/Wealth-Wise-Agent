"""'Explain my plan': the LLM turns the Phase 4 plan into plain language, with a rule-based fallback.

The plan is fetched by code (not by the model), so the explanation is always about the real plan.
The answer must pass the number guard; if it fails twice, or AI is off, we use the template text.
"""
import json

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents import guard
from app.agents.advisor import SYSTEM_PROMPT
from app.agents.llm import get_llm, llm_status
from app.agents.tools import compact_plan
from app.services.expenses import inr

PROMPT = """Here is the user's plan from the app's rule-based engine, as JSON:

{plan}

Explain it to the user in 4 short sections with these headings:
**First step**, **Why this mix**, **Where the money goes**, **Keep in mind**.
Use only numbers that appear in the JSON. Keep it under 220 words."""


def rules_explanation(plan: dict) -> str:
    """Deterministic explanation built straight from the plan: the fallback when AI is unavailable."""
    em, inv, w = plan["emergency"], plan["investable"], plan["allocation"]["weights"]
    lines = ["**First step**"]
    if em["ok"]:
        lines.append(f"Your emergency fund ({inr(em['current'])}) already covers 6 months of expenses, "
                     f"so all of your {inr(inv['monthly'])}/month surplus can be invested.")
    elif em["monthly_contribution"]:
        lines.append(f"Build your emergency fund first: {inr(em['monthly_contribution'])}/month into a liquid fund "
                     f"for about {em['months_to_fill']} months closes the {inr(em['shortfall'])} gap.")
    else:
        lines.append(f"You need {inr(em['shortfall'])} more in your emergency fund, but there's no monthly surplus yet. "
                     "Freeing up some spending comes first.")
    lines += ["", "**Why this mix**",
              f"{w['equity']:.0%} equity, {w['debt']:.0%} debt funds, {w['fd']:.0%} FDs and {w['liquid']:.0%} liquid, "
              f"for an expected return of about {plan['allocation']['expected_return']:.1%} a year."]
    lines += [f"- {r}" for r in plan["allocation"]["rationale"]]
    if plan["plan"]:
        lines += ["", "**Where the money goes**"]
        for i in plan["plan"]:
            names = [p.get("short_name") or p.get("bank") or p.get("symbol") for p in i["picks"][:2]]
            lines.append(f"- {i['label']}: {inr(i['monthly'])}/month" + (f" (e.g. {', '.join(names)})" if names else ""))
    lines += ["", "**Keep in mind**",
              "Returns are long-run assumptions, not promises; review the plan once a year or when your income changes. "
              "This is educational output, not SEBI-registered advice."]
    return "\n".join(lines)


def explain_plan(plan: dict) -> dict:
    fallback = {"source": "rules", "text": rules_explanation(plan), "unverified": []}
    llm = get_llm()
    if llm is None:
        return fallback | {"reason": llm_status()["reason"]}

    data = compact_plan(plan)
    messages = [SystemMessage(SYSTEM_PROMPT), HumanMessage(PROMPT.format(plan=json.dumps(data, default=str)))]
    try:
        for attempt in range(2):
            text = str(llm.invoke(messages).content)
            result = guard.check(text, data)
            if result.ok:
                return {"source": "ai", "text": text, "unverified": []}
            messages += [HumanMessage(f"These figures aren't in the JSON: {', '.join(result.unverified)}. "
                                      "Rewrite using only numbers from the JSON.")]
        return fallback | {"reason": "The AI answer used figures that couldn't be verified, so the rule-based summary is shown."}
    except Exception as e:  # provider down, rate limited, bad key...
        return fallback | {"reason": f"AI unavailable ({type(e).__name__}); showing the rule-based summary."}
