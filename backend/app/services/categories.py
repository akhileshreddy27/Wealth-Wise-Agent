"""Expense/income categories and a rule-based auto-categoriser.

Each expense category maps to a 50/30/20 bucket: needs, wants, or savings.
Phase 5 can swap `categorize()` for an LLM call; the rules stay as a fast fallback.
"""
import re

EXPENSE_CATEGORIES: dict[str, dict] = {
    "rent":          {"label": "Rent & Housing",   "bucket": "needs"},
    "groceries":     {"label": "Groceries",        "bucket": "needs"},
    "utilities":     {"label": "Bills & Utilities", "bucket": "needs"},
    "transport":     {"label": "Transport & Fuel", "bucket": "needs"},
    "health":        {"label": "Health",           "bucket": "needs"},
    "insurance":     {"label": "Insurance",        "bucket": "needs"},
    "education":     {"label": "Education",        "bucket": "needs"},
    "emi":           {"label": "Loan EMI",         "bucket": "needs"},
    "dining":        {"label": "Food & Dining",    "bucket": "wants"},
    "shopping":      {"label": "Shopping",         "bucket": "wants"},
    "entertainment": {"label": "Entertainment",    "bucket": "wants"},
    "travel":        {"label": "Travel",           "bucket": "wants"},
    "subscriptions": {"label": "Subscriptions",    "bucket": "wants"},
    "personal_care": {"label": "Personal Care",    "bucket": "wants"},
    "investments":   {"label": "Investments / SIP", "bucket": "savings"},
    "other":         {"label": "Other",            "bucket": "wants"},
}

INCOME_CATEGORIES: dict[str, dict] = {
    "salary":       {"label": "Salary"},
    "freelance":    {"label": "Freelance / Business"},
    "interest":     {"label": "Interest & Dividends"},
    "other_income": {"label": "Other income"},
}

_RULES: list[tuple[str, list[str]]] = [
    ("subscriptions", ["netflix", "spotify", "prime", "hotstar", "youtube premium", "subscription", "icloud", "google one", "jiocinema"]),
    ("dining",        ["swiggy", "zomato", "restaurant", "cafe", "starbucks", "domino", "pizza", "mcdonald", "kfc", "food"]),
    ("groceries",     ["bigbasket", "blinkit", "zepto", "dmart", "grocery", "instamart", "kirana", "vegetable", "milk"]),
    ("transport",     ["uber", "ola", "rapido", "metro", "petrol", "fuel", "diesel", "irctc", "bus", "parking", "fastag"]),
    ("travel",        ["makemytrip", "goibibo", "indigo", "air india", "vistara", "hotel", "oyo", "airbnb", "flight"]),
    ("shopping",      ["amazon", "flipkart", "myntra", "ajio", "nykaa", "meesho", "mall", "decathlon"]),
    ("utilities",     ["electricity", "water bill", "gas", "broadband", "wifi", "airtel", "jio", "vodafone", "recharge", "dth", "bescom"]),
    ("rent",          ["rent", "maintenance", "society", "landlord"]),
    ("health",        ["pharmacy", "apollo", "medplus", "hospital", "clinic", "doctor", "1mg", "pharmeasy", "gym", "cult"]),
    ("insurance",     ["insurance", "lic", "premium", "policy"]),
    ("education",     ["course", "udemy", "coursera", "tuition", "school", "college", "books"]),
    ("emi",           ["emi", "loan", "credit card bill"]),
    ("entertainment", ["bookmyshow", "pvr", "inox", "movie", "concert", "game", "steam"]),
    ("personal_care", ["salon", "spa", "haircut", "urban company"]),
    ("investments",   ["sip", "mutual fund", "zerodha", "groww", "upstox", "ppf", "nps", "fd ", "fixed deposit"]),
]

_INCOME_RULES: list[tuple[str, list[str]]] = [
    ("salary",    ["salary", "payroll", "sal cr"]),
    ("interest",  ["interest", "dividend", "int.pd", "int cr"]),
    ("freelance", ["freelance", "invoice", "client", "upwork", "fiverr"]),
]


def categorize(text: str, kind: str = "expense") -> str:
    t = f" {text.lower()} "
    for category, keywords in (_INCOME_RULES if kind == "income" else _RULES):
        if any(k in t for k in keywords):
            return category
    return "other_income" if kind == "income" else "other"


def normalize_merchant(text: str) -> str:
    """Used to spot recurring payments: lowercase, drop digits/punctuation."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z ]", " ", text.lower())).strip()
