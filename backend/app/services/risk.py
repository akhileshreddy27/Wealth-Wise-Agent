"""Risk profiling: combines risk *tolerance* (questionnaire) with risk *capacity*
(age, horizon, dependents, emergency cushion) into a 1-10 score."""

QUESTIONNAIRE = [
    {
        "id": "market_drop",
        "question": "Your investments fall 20% in a month. What do you do?",
        "options": [
            {"value": 1, "label": "Sell everything to stop the losses"},
            {"value": 2, "label": "Sell some to reduce risk"},
            {"value": 3, "label": "Hold and wait for recovery"},
            {"value": 4, "label": "Invest more while prices are low"},
        ],
    },
    {
        "id": "primary_goal",
        "question": "What matters most to you when investing?",
        "options": [
            {"value": 1, "label": "Protecting my capital"},
            {"value": 2, "label": "Steady income with low risk"},
            {"value": 3, "label": "Balanced growth"},
            {"value": 4, "label": "Maximum long-term growth"},
        ],
    },
    {
        "id": "experience",
        "question": "How experienced are you with stocks or mutual funds?",
        "options": [
            {"value": 1, "label": "Never invested"},
            {"value": 2, "label": "Only FDs / savings accounts"},
            {"value": 3, "label": "Some mutual funds or SIPs"},
            {"value": 4, "label": "Regularly invest in stocks"},
        ],
    },
    {
        "id": "return_vs_risk",
        "question": "Which portfolio would you pick for one year?",
        "options": [
            {"value": 1, "label": "Best +7%, worst +5%"},
            {"value": 2, "label": "Best +12%, worst 0%"},
            {"value": 3, "label": "Best +20%, worst -8%"},
            {"value": 4, "label": "Best +35%, worst -20%"},
        ],
    },
    {
        "id": "income_stability",
        "question": "How stable is your income?",
        "options": [
            {"value": 1, "label": "Very uncertain"},
            {"value": 2, "label": "Somewhat uncertain"},
            {"value": 3, "label": "Stable"},
            {"value": 4, "label": "Very stable with growth"},
        ],
    },
]

_QUESTION_IDS = {q["id"] for q in QUESTIONNAIRE}


def validate_answers(answers: dict[str, int]) -> None:
    missing = _QUESTION_IDS - answers.keys()
    if missing:
        raise ValueError(f"Missing answers for: {', '.join(sorted(missing))}")
    for qid, val in answers.items():
        if qid not in _QUESTION_IDS:
            raise ValueError(f"Unknown question: {qid}")
        if val not in (1, 2, 3, 4):
            raise ValueError(f"Answer for {qid} must be 1-4")


def _capacity_score(age: int, horizon_years: int, dependents: int, emergency_months: float) -> float:
    """Return 0..1: how much risk the user can *afford* to take."""
    age_pts = 1.0 if age < 30 else 0.75 if age < 40 else 0.5 if age < 50 else 0.25 if age < 60 else 0.1
    horizon_pts = 1.0 if horizon_years >= 10 else 0.75 if horizon_years >= 5 else 0.4 if horizon_years >= 3 else 0.1
    dep_pts = 1.0 if dependents == 0 else 0.7 if dependents <= 2 else 0.4
    cushion_pts = 1.0 if emergency_months >= 6 else 0.6 if emergency_months >= 3 else 0.3
    return 0.35 * age_pts + 0.35 * horizon_pts + 0.15 * dep_pts + 0.15 * cushion_pts


def compute_risk(
    answers: dict[str, int], age: int, horizon_years: int, dependents: int,
    monthly_expenses: float, current_savings: float,
) -> tuple[int, str]:
    validate_answers(answers)
    tolerance = (sum(answers.values()) - len(answers)) / (3 * len(answers))  # 0..1
    emergency_months = current_savings / monthly_expenses if monthly_expenses > 0 else 12
    capacity = _capacity_score(age, horizon_years, dependents, emergency_months)

    # Capacity caps tolerance: a 58-year-old with a 2-year horizon can't be "aggressive"
    # no matter how bold their answers are.
    combined = 0.6 * tolerance + 0.4 * capacity
    combined = min(combined, capacity + 0.2)
    score = max(1, min(10, round(1 + combined * 9)))

    category = "conservative" if score <= 3 else "moderate" if score <= 6 else "aggressive"
    return score, category


def financial_snapshot(monthly_income: float, monthly_expenses: float, current_savings: float) -> dict:
    surplus = monthly_income - monthly_expenses
    savings_rate = surplus / monthly_income if monthly_income > 0 else 0
    emergency_target = monthly_expenses * 6
    return {
        "monthly_surplus": round(surplus, 2),
        "savings_rate": round(savings_rate, 4),
        "emergency_fund_target": round(emergency_target, 2),
        "emergency_fund_months": round(current_savings / monthly_expenses, 1) if monthly_expenses > 0 else None,
        "emergency_fund_ok": current_savings >= emergency_target,
    }
