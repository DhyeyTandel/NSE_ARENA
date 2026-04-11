# tests/conftest.py
import sys
import os
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import pandas as pd

# Add backend root to path so imports resolve correctly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── Import the FastAPI app FIRST at conftest load time ────────────────
# This must happen before any other test module triggers db.models import.
# We patch init_db to skip the real database connection.

_init_db_patcher = patch("database.init_db", new_callable=AsyncMock)
_init_db_patcher.start()

# Mock broadcaster Redis calls to avoid needing a running Redis in tests
_broadcaster_cache_patcher = patch(
    "market_data.broadcaster.PriceBroadcaster.get_cached_price",
    new_callable=AsyncMock, return_value=None,
)
_broadcaster_health_patcher = patch(
    "market_data.broadcaster.PriceBroadcaster.check_health",
    new_callable=AsyncMock, return_value=False,
)
_broadcaster_cache_patcher.start()
_broadcaster_health_patcher.start()

from main import app as _app  # noqa: E402

_init_db_patcher.stop()
_broadcaster_cache_patcher.stop()
_broadcaster_health_patcher.stop()


# ── Mock yfinance data ──────────────────────────────────────────────

MOCK_INFO = {
    "currentPrice": 2891.45,
    "regularMarketPrice": 2891.45,
    "previousClose": 2847.30,
    "open": 2855.00,
    "dayHigh": 2905.10,
    "dayLow": 2840.20,
    "volume": 5_234_100,
    "regularMarketChangePercent": 1.55,
}

MOCK_HISTORY_DF = pd.DataFrame(
    {
        "Open": [2850.0, 2870.0, 2860.0],
        "High": [2880.0, 2900.0, 2890.0],
        "Low": [2830.0, 2850.0, 2845.0],
        "Close": [2870.123, 2880.456, 2875.789],
        "Volume": [5000000, 4500000, 4800000],
    },
    index=pd.to_datetime(["2026-03-10", "2026-03-11", "2026-03-12"]),
)


def _make_mock_ticker(info=None, history_df=None):
    """Create a mock yf.Ticker that returns deterministic data."""
    ticker = MagicMock()
    ticker.info = info or MOCK_INFO
    ticker.history.return_value = history_df if history_df is not None else MOCK_HISTORY_DF
    return ticker


@pytest.fixture
def mock_yfinance():
    """Patch yf.Ticker to avoid real API calls."""
    with patch("yfinance.Ticker", side_effect=lambda t: _make_mock_ticker()) as m:
        yield m


@pytest.fixture
def mock_yfinance_error():
    """Patch yf.Ticker to raise an exception."""
    with patch("yfinance.Ticker", side_effect=Exception("API unavailable")) as m:
        yield m


@pytest.fixture(scope="session")
def fastapi_app():
    """Provide the FastAPI app instance (already imported at module level)."""
    return _app
