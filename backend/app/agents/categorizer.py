"""LLM fallback for the keyword auto-categoriser.

The keyword rules in services/categories.py stay first (fast, free, predictable). Only transactions
they can't place ("other") are sent to the model, in one batched request per import.
"""
import json
import logging
import re

from langchain_core.messages import HumanMessage

from app.agents.llm import get_llm
from app.core.config import settings
from app.services.categories import EXPENSE_CATEGORIES, INCOME_CATEGORIES

log = logging.getLogger(__name__)
MAX_ITEMS = 60

PROMPT = """Categorise these Indian bank-statement transactions.
Expense categories: {expense}
Income categories: {income}

Transactions (number. [kind] description):
{items}

Reply with only a JSON object mapping each number to a category key, e.g. {{"1": "dining", "2": "salary"}}.
Use "other" (expense) or "other_income" (income) if unsure."""


def ai_categorize(items: list[tuple[str, str]]) -> dict[int, str]:
    """items: [(description, kind)]. Returns {index: category} for the ones the model placed confidently."""
    llm = get_llm(temperature=0) if settings.llm_categorize else None
    if llm is None or not items:
        return {}
    items = items[:MAX_ITEMS]
    prompt = PROMPT.format(
        expense=", ".join(f"{k} ({v['label']})" for k, v in EXPENSE_CATEGORIES.items()),
        income=", ".join(INCOME_CATEGORIES),
        items="\n".join(f"{i}. [{kind}] {note[:120]}" for i, (note, kind) in enumerate(items, 1)))
    try:
        text = str(llm.invoke([HumanMessage(prompt)]).content)
        raw = json.loads(re.search(r"\{.*\}", text, re.S).group(0))
    except Exception as e:  # network, rate limit, or a reply that isn't JSON: keep the rule-based "other"
        log.warning("AI categorisation skipped: %s", e)
        return {}

    out = {}
    for key, cat in raw.items():
        try:
            idx = int(key) - 1
        except ValueError:
            continue
        if 0 <= idx < len(items):
            valid = EXPENSE_CATEGORIES if items[idx][1] == "expense" else INCOME_CATEGORIES
            if cat in valid and cat not in ("other", "other_income"):
                out[idx] = cat
    return out
