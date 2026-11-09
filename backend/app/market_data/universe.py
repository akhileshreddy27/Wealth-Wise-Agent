"""What we track. Edit these lists to widen the universe.

NIFTY 50 constituents change twice a year (NSE rebalances in March/September);
symbols Yahoo can't resolve are skipped and reported in the refresh log.
"""

NIFTY_INDEX = "^NSEI"

NIFTY50 = [
    "ADANIENT", "ADANIPORTS", "APOLLOHOSP", "ASIANPAINT", "AXISBANK", "BAJAJ-AUTO", "BAJFINANCE",
    "BAJAJFINSV", "BEL", "BHARTIARTL", "CIPLA", "COALINDIA", "DRREDDY", "EICHERMOT", "ETERNAL",
    "GRASIM", "HCLTECH", "HDFCBANK", "HDFCLIFE", "HINDALCO", "HINDUNILVR", "ICICIBANK", "INDIGO",
    "INFY", "ITC", "JIOFIN", "JSWSTEEL", "KOTAKBANK", "LT", "M&M", "MARUTI", "MAXHEALTH",
    "NESTLEIND", "NTPC", "ONGC", "POWERGRID", "RELIANCE", "SBILIFE", "SBIN", "SHRIRAMFIN",
    "SUNPHARMA", "TATACONSUM", "TMPV", "TATASTEEL", "TCS", "TECHM", "TITAN", "TRENT",
    "ULTRACEMCO", "WIPRO",
]

# Curated Direct-Growth funds, matched by name against mfapi.in's scheme list at refresh time
# (every word must appear in the scheme name; AMCs rename schemes, so update these when one stops matching).
# The category shown in the app comes from the AMFI category in the scheme's metadata.
FUND_QUERIES = [
    # Index
    "UTI Nifty 50 Index Fund", "HDFC Nifty 50 Index Fund", "UTI Nifty Next 50 Index Fund",
    "ICICI Prudential Nifty 500 Index Fund", "Motilal Oswal Nifty Midcap 150 Index Fund",
    # Large cap
    "ICICI Prudential Large Cap Fund", "Nippon India Large Cap Fund", "Mirae Asset Large Cap Fund",
    # Flexi cap
    "Parag Parikh Flexi Cap Fund", "HDFC Flexi Cap Fund", "Kotak Flexi Cap Fund",
    # Mid cap
    "HDFC Mid Cap Fund", "Kotak Mid Cap Fund",
    # Small cap
    "Nippon India Small Cap Fund", "SBI Small Cap Fund", "Axis Small Cap Fund",
    # ELSS (80C)
    "Mirae Asset ELSS Tax Saver Fund", "Quant ELSS Tax Saver Fund", "DSP ELSS Tax Saver Fund",
    # Hybrid
    "ICICI Prudential Balanced Advantage Fund", "HDFC Balanced Advantage Fund",
    # Debt
    "HDFC Corporate Bond Fund", "ICICI Prudential Corporate Bond Fund",
    "Aditya Birla Sun Life Corporate Bond Fund", "SBI Gilt Fund", "HDFC Short Term Fund",
    # Liquid
    "Parag Parikh Liquid Fund", "HDFC Liquid Fund", "SBI Liquid Fund",
]
