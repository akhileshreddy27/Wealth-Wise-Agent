"""Number guard: every figure in an AI answer must come from a tool result.

LLMs are good at explaining and bad at arithmetic, and on a finance app a made-up number is
worse than no answer. So after the model writes its reply, we pull every number out of it and
check that it matches (allowing for rounding, % vs fraction, and lakh/crore/k units) a number
that appeared in the tool outputs, the user's own message, or a small set of known rules.
"""
import json
import re
from dataclasses import dataclass, field

# General rules the assistant may quote without a tool call: 50/30/20 budgeting, 6-month emergency
# fund, 80C limit, DICGC insurance cover, ELSS / tax-saver FD lock-ins, 6% inflation assumption.
KNOWN_FACTS = [50, 30, 20, 6, 150000, 500000, 3, 5, 0.06, 100]

_UNITS = {"%": 1, "percent": 1, "k": 1e3, "thousand": 1e3, "lakh": 1e5, "lakhs": 1e5, "lac": 1e5, "l": 1e5,
          "crore": 1e7, "crores": 1e7, "cr": 1e7}
_NUM = re.compile(
    r"(?<![A-Za-z0-9.])(₹\s?)?(\d(?:[\d,]*\d)?(?:\.\d+)?)"
    r"(?:\s?(%|percent|k|thousand|lakhs?|lac|l|crores?|cr)(?![A-Za-z]))?(?![A-Za-z0-9])", re.I)


@dataclass
class Claim:
    text: str
    value: float
    is_pct: bool


@dataclass
class GuardResult:
    ok: bool
    unverified: list[str] = field(default_factory=list)


def extract_claims(text: str) -> list[Claim]:
    claims = []
    for m in _NUM.finditer(text):
        raw = m.group(2).replace(",", "")
        try:
            v = float(raw)
        except ValueError:
            continue
        unit = (m.group(3) or "").lower()
        claims.append(Claim(m.group(0).strip(), v * _UNITS.get(unit, 1) if unit not in ("%", "percent") else v,
                            unit in ("%", "percent")))
    return claims


def _numbers_in(obj, out: list[float]) -> None:
    """Collect numbers from tool output: JSON values and numbers written inside strings."""
    if isinstance(obj, bool) or obj is None:
        return
    if isinstance(obj, (int, float)):
        out.append(float(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            _numbers_in(v, out)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _numbers_in(v, out)
    elif isinstance(obj, str):
        try:
            _numbers_in(json.loads(obj), out)
            return
        except (ValueError, TypeError):
            pass
        out.extend(c.value for c in extract_claims(obj))


def allowed_numbers(*sources) -> list[float]:
    out: list[float] = list(map(float, KNOWN_FACTS))
    for s in sources:
        _numbers_in(s, out)
    return out


def _close(claim: Claim, ref: float) -> bool:
    diff = abs(claim.value - ref)
    if claim.is_pct:
        # "10%" may round 10.28%; "10.3%" should be within a rounding step of it.
        return diff <= (0.5 if claim.value == int(claim.value) else 0.051)
    if abs(ref) < 100:
        return diff <= 0.051                    # ratios like Sharpe 1.25 vs 1.2486
    return diff <= 0.02 * abs(ref)             # rupee amounts: "about ₹41,000" for 41,313


def _matches(c: Claim, allowed: list[float]) -> bool:
    for a in allowed:
        refs = [a, a * 100] if c.is_pct and abs(a) <= 5 else [a]   # 0.123 may be quoted as 12.3%
        if any(_close(c, r) for r in refs):
            return True
    return False


def check(answer: str, *sources) -> GuardResult:
    allowed = allowed_numbers(*sources)
    bad = []
    for c in extract_claims(answer):
        if not c.is_pct and c.value <= 12 and c.value == int(c.value):
            continue          # small counts: "3 funds", "step 2", "12 months"
        if not c.is_pct and 1990 <= c.value <= 2100 and c.value == int(c.value):
            continue          # years
        if not _matches(c, allowed):
            bad.append(c.text)
    return GuardResult(ok=not bad, unverified=list(dict.fromkeys(bad)))
