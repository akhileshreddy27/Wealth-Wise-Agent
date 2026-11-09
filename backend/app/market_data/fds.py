import json
from datetime import date
from pathlib import Path

RATES_FILE = Path(__file__).with_name("fd_rates.json")
FIVE_YEARS = 1825


def load_fd_rows(path: Path = RATES_FILE) -> list[dict]:
    data = json.loads(path.read_text())
    as_of = date.fromisoformat(data["as_of"])
    rows = []
    for b in data["banks"]:
        slabs = b.get("slabs", data["slabs"])
        if len(slabs) != len(b["rates"]):
            raise ValueError(f"{b['bank']}: {len(b['rates'])} rates for {len(slabs)} slabs")
        for (lo, hi), rate in zip(slabs, b["rates"]):
            rows.append({"bank": b["bank"], "bank_type": b["type"], "min_days": lo, "max_days": hi,
                         "rate": rate, "senior_rate": round(rate + b["senior_bonus"], 2),
                         "tax_saver": False, "as_of": as_of, "source_url": b.get("url")})
        if b.get("tax_saver_rate"):
            r = b["tax_saver_rate"]
            rows.append({"bank": b["bank"], "bank_type": b["type"], "min_days": FIVE_YEARS, "max_days": FIVE_YEARS,
                         "rate": r, "senior_rate": round(r + b["senior_bonus"], 2),
                         "tax_saver": True, "as_of": as_of, "source_url": b.get("url")})
    return rows


def maturity_value(principal: float, rate_pct: float, days: int, compounding_per_year: int = 4) -> float:
    """Quarterly compounding (the Indian bank standard for cumulative FDs)."""
    years = days / 365
    return principal * (1 + rate_pct / 100 / compounding_per_year) ** (compounding_per_year * years)
