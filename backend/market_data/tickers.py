# market_data/tickers.py
"""NIFTY 50 constituents streamed by the price broadcaster.

Source: NSE official constituent CSV
https://nsearchives.nseindia.com/content/indices/ind_nifty50list.csv
Fetched 2026-11-13; every symbol verified to return data from yfinance
with ".NS" appended. The index is reconstituted periodically, so refresh
this list from that URL when NSE announces changes.
"""

NIFTY_50 = [
    "ADANIENT", "ADANIPORTS", "APOLLOHOSP", "ASIANPAINT",
    "AXISBANK", "BSE", "BAJAJ-AUTO", "BAJFINANCE",
    "BAJAJFINSV", "BEL", "BHARTIARTL", "CIPLA",
    "COALINDIA", "DRREDDY", "EICHERMOT", "ETERNAL",
    "GRASIM", "HCLTECH", "HDFCBANK", "HDFCLIFE",
    "HINDALCO", "HINDUNILVR", "ICICIBANK", "ITC",
    "INFY", "INDIGO", "JSWSTEEL", "JIOFIN",
    "KOTAKBANK", "LT", "M&M", "MARUTI",
    "MAXHEALTH", "NTPC", "NESTLEIND", "ONGC",
    "POWERGRID", "RELIANCE", "SBILIFE", "SHRIRAMFIN",
    "SBIN", "SUNPHARMA", "TCS", "TATACONSUM",
    "TMPV", "TATASTEEL", "TECHM", "TITAN",
    "TRENT", "ULTRACEMCO",
]
