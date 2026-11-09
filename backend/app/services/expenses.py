"""Expense analytics: monthly summary, budget tracking and savings insights."""
import statistics
from collections import defaultdict
from datetime import date

from app.models import Transaction
from app.services.categories import EXPENSE_CATEGORIES, normalize_merchant
from app.services.planner import sip_future_value


def inr(n: float) -> str:
    """Indian digit grouping: 1234567 -> ₹12,34,567."""
    neg, n = n < 0, round(abs(n))
    s = str(n)
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        head = ",".join([head[max(0, i - 2):i] for i in range(len(head), 0, -2)][::-1])
        s = f"{head},{tail}"
    return f"{'-' if neg else ''}₹{s}"


def month_key(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def shift_month(month: str, delta: int) -> str:
    y, m = map(int, month.split("-"))
    idx = y * 12 + (m - 1) + delta
    return f"{idx // 12:04d}-{idx % 12 + 1:02d}"


def _expenses_by_month_cat(txns: list[Transaction]) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for t in txns:
        if t.kind == "expense":
            out[month_key(t.date)][t.category] += t.amount
    return out


def build_summary(txns: list[Transaction], month: str, budgets: dict[str, float], fallback_income: float = 0) -> dict:
    cur = [t for t in txns if month_key(t.date) == month]
    income = sum(t.amount for t in cur if t.kind == "income")
    expense = sum(t.amount for t in cur if t.kind == "expense")
    income_base = income or fallback_income

    by_cat: dict[str, float] = defaultdict(float)
    daily: dict[str, float] = defaultdict(float)
    for t in cur:
        if t.kind == "expense":
            by_cat[t.category] += t.amount
            daily[t.date.isoformat()] += t.amount

    categories = []
    for cat in set(by_cat) | set(budgets):
        spent = round(by_cat.get(cat, 0), 2)
        limit = budgets.get(cat)
        meta = EXPENSE_CATEGORIES.get(cat, {"label": cat, "bucket": "wants"})
        categories.append({
            "category": cat, "label": meta["label"], "bucket": meta["bucket"], "amount": spent,
            "share": round(spent / expense, 4) if expense else 0,
            "budget": limit,
            "budget_used": round(spent / limit, 4) if limit else None,
        })
    categories.sort(key=lambda c: -c["amount"])

    buckets = {"needs": 0.0, "wants": 0.0, "savings": 0.0}
    for c in categories:
        buckets[c["bucket"]] += c["amount"]
    # Whatever is left of income after all spending also counts as savings.
    invested = buckets["savings"]
    saved = income_base - (expense - invested)  # SIPs/investments are saving, not spending
    leftover = max(income_base - expense, 0)
    buckets["savings"] += leftover
    bucket_share = {k: round(v / income_base, 4) if income_base else None for k, v in buckets.items()}

    trend = []
    by_month_income: dict[str, float] = defaultdict(float)
    by_month_expense: dict[str, float] = defaultdict(float)
    for t in txns:
        (by_month_income if t.kind == "income" else by_month_expense)[month_key(t.date)] += t.amount
    for i in range(5, -1, -1):
        m = shift_month(month, -i)
        trend.append({"month": m, "income": round(by_month_income[m], 2), "expense": round(by_month_expense[m], 2)})

    return {
        "month": month,
        "income": round(income, 2),
        "income_is_estimate": income == 0 and fallback_income > 0,
        "income_base": round(income_base, 2),
        "expense": round(expense, 2),
        "invested": round(invested, 2),
        "net": round(saved, 2),
        "savings_rate": round(saved / income_base, 4) if income_base else None,
        "categories": categories,
        "buckets": {k: round(v, 2) for k, v in buckets.items()},
        "bucket_share": bucket_share,
        "daily": [{"date": d, "amount": round(a, 2)} for d, a in sorted(daily.items())],
        "trend": trend,
    }


def detect_recurring(txns: list[Transaction], month: str, lookback: int = 3) -> list[dict]:
    """Same merchant/note, similar amount, in >= 2 of the last `lookback` months."""
    window = {shift_month(month, -i) for i in range(lookback)}
    groups: dict[str, list[Transaction]] = defaultdict(list)
    for t in txns:
        if t.kind == "expense" and t.note and month_key(t.date) in window:
            key = normalize_merchant(t.note)
            if key:
                groups[key].append(t)

    found = []
    for key, items in groups.items():
        months = {month_key(t.date) for t in items}
        if len(months) < 2:
            continue
        amounts = [t.amount for t in items]
        med = statistics.median(amounts)
        if med <= 0 or any(abs(a - med) / med > 0.15 for a in amounts):
            continue  # amounts vary too much to be a fixed subscription
        latest = max(items, key=lambda t: t.date)
        found.append({"name": latest.note, "category": latest.category, "monthly_amount": round(med, 2), "months_seen": len(months)})
    return sorted(found, key=lambda r: -r["monthly_amount"])


def detect_spikes(txns: list[Transaction], month: str, history: int = 6) -> list[dict]:
    """Flag categories where this month is > mean + 2·std of prior months (and >25% above mean)."""
    by_mc = _expenses_by_month_cat(txns)
    current = by_mc.get(month, {})
    spikes = []
    for cat, amount in current.items():
        past = [by_mc[m][cat] for m in (shift_month(month, -i) for i in range(1, history + 1)) if by_mc.get(m, {}).get(cat)]
        if len(past) < 2:
            continue
        mean = statistics.mean(past)
        std = statistics.pstdev(past)
        if amount > mean + 2 * std and amount > 1.25 * mean and amount - mean >= 500:
            z = (amount - mean) / std if std else None
            spikes.append({"category": cat, "amount": round(amount, 2), "usual": round(mean, 2),
                           "z_score": round(z, 1) if z is not None else None})
    return spikes


def _label(cat: str) -> str:
    return EXPENSE_CATEGORIES.get(cat, {"label": cat})["label"]


def build_insights(txns: list[Transaction], month: str, budgets: dict[str, float], fallback_income: float = 0) -> dict:
    s = build_summary(txns, month, budgets, fallback_income)
    insights: list[dict] = []
    saving_by_cat: dict[str, float] = {}

    def add(kind, severity, title, detail, saving=0.0, category=None):
        insights.append({"type": kind, "severity": severity, "title": title, "detail": detail,
                         "potential_saving": round(saving, 2), "category": category})
        if category and saving:
            saving_by_cat[category] = max(saving_by_cat.get(category, 0), saving)

    if s["expense"] == 0:
        return {"month": month, "insights": [], "potential_monthly_saving": 0, "recurring": []}

    # 1. Budgets
    for c in s["categories"]:
        if c["budget"]:
            used = c["budget_used"]
            if used > 1:
                over = c["amount"] - c["budget"]
                add("over_budget", "danger", f"{c['label']} is over budget",
                    f"Spent {inr(c['amount'])} against a {inr(c['budget'])} budget ({inr(over)} over).", over, c["category"])
            elif used >= 0.8:
                add("near_budget", "warning", f"{c['label']} is at {used:.0%} of budget",
                    f"{inr(c['budget'] - c['amount'])} left for the rest of the month.", 0, c["category"])

    # 2. 50/30/20 rule
    share = s["bucket_share"]
    base = s["income_base"]
    if base:
        if share["wants"] and share["wants"] > 0.30:
            excess = s["buckets"]["wants"] - 0.30 * base
            add("rule_50_30_20", "warning", f"Wants are {share['wants']:.0%} of income (target 30%)",
                f"Trimming {inr(excess)} of discretionary spending gets you back to the 50/30/20 guideline.", excess)
        if share["needs"] and share["needs"] > 0.50:
            add("rule_50_30_20", "info", f"Needs are {share['needs']:.0%} of income (target 50%)",
                "Fixed costs are high. Rent, EMIs and bills are worth renegotiating or refinancing.")
        if s["savings_rate"] is not None:
            if s["savings_rate"] >= 0.20:
                add("savings_rate", "success", f"You're saving {s['savings_rate']:.0%} of income",
                    "That beats the 20% target. Put the surplus to work in an SIP or FD.")
            elif s["savings_rate"] < 0:
                add("savings_rate", "danger", "You spent more than you earned",
                    f"Spending exceeded income by {inr(-s['net'])} this month.")
            else:
                gap = 0.20 * base - s["net"]
                add("savings_rate", "warning", f"Savings rate is {s['savings_rate']:.0%} (target 20%)",
                    f"Saving {inr(gap)} more per month would reach the 20% target.")

    # 3. Recurring payments
    recurring = detect_recurring(txns, month)
    subs = [r for r in recurring if r["category"] in ("subscriptions", "entertainment", "other")]
    if subs:
        total = sum(r["monthly_amount"] for r in subs)
        names = ", ".join(r["name"] for r in subs[:4])
        add("subscriptions", "info", f"{len(subs)} recurring subscription{'s' * (len(subs) > 1)} ({inr(total)}/month)",
            f"{names}. Cancel the ones you don't use; that's {inr(total * 12)} a year.", total, "subscriptions")

    # 4. Unusual spikes
    for sp in detect_spikes(txns, month):
        extra = sp["amount"] - sp["usual"]
        add("spike", "warning", f"{_label(sp['category'])} spending spiked",
            f"{inr(sp['amount'])} this month vs a usual {inr(sp['usual'])}. That's {inr(extra)} above normal.",
            extra, sp["category"])

    # 5. Top discretionary category → show the compounding cost
    wants = [c for c in s["categories"] if c["bucket"] == "wants" and c["amount"] > 0]
    if wants:
        top = wants[0]
        cut = top["amount"] * 0.20
        fv = sip_future_value(cut, years=10, annual_return=0.12)
        add("top_want", "info", f"Biggest discretionary spend: {top['label']} ({inr(top['amount'])})",
            f"Cutting it by 20% frees {inr(cut)}/month. Invested as a SIP at 12%, that's about {inr(fv)} in 10 years.",
            cut, top["category"])

    order = {"danger": 0, "warning": 1, "info": 2, "success": 3}
    insights.sort(key=lambda i: order[i["severity"]])
    return {
        "month": month,
        "insights": insights,
        "potential_monthly_saving": round(sum(saving_by_cat.values()), 2),
        "recurring": recurring,
    }
