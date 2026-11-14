# api/validation.py
"""Shared input validation for ticker / period parameters."""
import re

from api.routes.trades import TICKER_PATTERN  # r"^[A-Z0-9&\-]{1,20}$" — NIFTY symbols like M&M, BAJAJ-AUTO

_TICKER_RE = re.compile(TICKER_PATTERN)

# yfinance periods the app actually offers.
ALLOWED_PERIODS = ("1mo", "3mo", "6mo", "1y", "2y")


def normalize_ticker(ticker: str) -> str | None:
    """Upper-cased ticker if it matches the trade ticker pattern, else None."""
    candidate = (ticker or "").strip().upper()
    return candidate if _TICKER_RE.match(candidate) else None
