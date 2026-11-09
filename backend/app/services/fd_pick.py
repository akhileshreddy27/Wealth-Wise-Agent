"""FD pick: best rate for the user's horizon, senior rate at 60+, tax-saver FD when 80C helps."""
from app.market_data.fds import FIVE_YEARS, maturity_value

DICGC_LIMIT = 500000  # deposit insurance per depositor per bank


def fd_tenure_days(horizon_years: int) -> int:
    """Match the horizon, between 1 and 5 years (longer FDs rarely pay more; reinvest at maturity)."""
    return min(max(horizon_years, 1), 5) * 365  # 5 * 365 == FIVE_YEARS, the tax-saver tenure


def _quote(r: dict, senior: bool, amount: float, days: int) -> dict:
    rate = r["senior_rate"] if senior else r["rate"]
    mv = maturity_value(amount, rate, days)
    return {"bank": r["bank"], "bank_type": r["bank_type"], "rate": rate, "tenure_days": days,
            "tax_saver": r["tax_saver"], "maturity_value": round(mv, 2), "interest": round(mv - amount, 2),
            "source_url": r.get("source_url")}


def pick_fd(rows: list[dict], horizon_years: int, age: int, old_tax_regime: bool, amount: float = 100000) -> dict:
    days = fd_tenure_days(horizon_years)
    senior = age >= 60
    regular = [r for r in rows if not r["tax_saver"] and r["min_days"] <= days <= r["max_days"]]
    quotes = sorted((_quote(r, senior, amount, days) for r in regular), key=lambda q: -q["rate"])

    notes = [f"Tenure matched to your {horizon_years}-year horizon" + (" (capped at 5 years)." if horizon_years > 5 else ".")]
    if senior:
        notes.append("Senior-citizen rates applied (age 60+).")

    best = quotes[0] if quotes else None
    safest = None
    if best and best["bank_type"] == "small_finance":
        safest = next((q for q in quotes if q["bank_type"] != "small_finance"), None)
        notes.append(f"Small finance banks pay more but carry more risk; DICGC insures only ₹{DICGC_LIMIT // 100000} lakh "
                     "per bank, so keep larger deposits in a bigger bank.")

    tax_saver = None
    if old_tax_regime:
        ts = [r for r in rows if r["tax_saver"]]
        if ts:
            tax_saver = max((_quote(r, senior, amount, FIVE_YEARS) for r in ts), key=lambda q: q["rate"])
            notes.append("Tax-saver FDs qualify for 80C (old regime) but lock money in for 5 years, "
                         "and the interest is still taxable.")

    return {
        "tenure_days": days, "senior": senior, "amount": amount,
        "best": best, "safest": safest, "alternatives": quotes[1:4], "tax_saver": tax_saver,
        "as_of": rows[0]["as_of"] if rows else None, "indicative": True, "notes": notes,
    }
