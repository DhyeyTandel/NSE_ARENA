# tests/test_batch_prices.py
"""MarketDataFetcher.get_batch_prices: one batched fetch for the whole
streamed list. The price must come from the session's 1-minute bars --
Yahoo returns the current day's *daily* bar with a NaN Close, so reading
the latest daily close silently reports the previous day's price.
"""
import json
from unittest.mock import patch

import numpy as np
import pandas as pd

from market_data.fetcher import MarketDataFetcher

NAN = np.nan
COLS = ["Open", "High", "Low", "Close", "Volume"]


def _frame(per_ticker: dict, index) -> pd.DataFrame:
    """Build a yf.download(group_by='ticker')-shaped frame: (ticker, field) columns."""
    parts = {f"{t}.NS": pd.DataFrame(rows, columns=COLS, index=index) for t, rows in per_ticker.items()}
    return pd.concat(parts, axis=1)


DAYS = pd.to_datetime(["2026-11-10", "2026-11-11", "2026-11-12"])
MINS = pd.to_datetime(["2026-11-12 09:15", "2026-11-12 09:16", "2026-11-12 09:17"]).tz_localize("Asia/Kolkata")


def _run(intraday, daily, tickers):
    def fake_download(symbols, period=None, interval=None, **kw):
        return intraday if interval == "1m" else daily
    with patch("market_data.fetcher.yf.download", side_effect=fake_download):
        return MarketDataFetcher.get_batch_prices(tickers)


def test_price_is_last_intraday_trade_not_stale_daily_close():
    # Today's daily bar has a NaN Close, exactly as Yahoo returns it.
    daily = _frame({"AAA": [[90, 99, 89, 95, 1000], [95, 101, 94, 100, 1000], [100, NAN, NAN, NAN, NAN]]}, DAYS)
    intraday = _frame({"AAA": [[100, 103, 99, 102, 10], [102, 106, 101, 105, 20], [NAN, NAN, NAN, NAN, NAN]]}, MINS)

    out = _run(intraday, daily, ["AAA"])

    q = out["AAA"]
    assert q["price"] == 105.0            # last traded minute, not 100 (yesterday)
    assert q["previous_close"] == 100.0   # last completed day before the session
    assert round(q["change_pct"], 6) == 5.0
    assert (q["open"], q["day_high"], q["day_low"], q["volume"]) == (100.0, 106.0, 99.0, 30)
    json.dumps(out, allow_nan=False)      # must be JSON-safe


def test_ticker_without_any_data_is_omitted_others_survive():
    daily = _frame({
        "AAA": [[90, 99, 89, 95, 1000], [95, 101, 94, 100, 1000], [100, NAN, NAN, NAN, NAN]],
        "BAD": [[NAN] * 5] * 3,
    }, DAYS)
    intraday = _frame({
        "AAA": [[100, 103, 99, 102, 10]] * 3,
        "BAD": [[NAN] * 5] * 3,
    }, MINS)

    out = _run(intraday, daily, ["AAA", "BAD", "NOTINFRAME"])

    assert set(out) == {"AAA"}


def test_falls_back_to_daily_bars_when_no_intraday_data():
    daily = _frame({"AAA": [[90, 99, 89, 95, 1000], [95, 101, 94, 100, 2000], [NAN] * 5]}, DAYS)
    intraday = _frame({"AAA": [[NAN] * 5] * 3}, MINS)

    q = _run(intraday, daily, ["AAA"])["AAA"]

    assert (q["price"], q["previous_close"], q["volume"]) == (100.0, 95.0, 2000)


def test_no_previous_close_gives_zero_change_not_a_crash():
    daily = _frame({"AAA": [[NAN] * 5] * 3}, DAYS)
    intraday = _frame({"AAA": [[100, 103, 99, 102, 10]] * 3}, MINS)

    q = _run(intraday, daily, ["AAA"])["AAA"]

    assert (q["price"], q["previous_close"], q["change_pct"]) == (102.0, 0, 0)


def test_empty_input_makes_no_request():
    with patch("market_data.fetcher.yf.download") as dl:
        assert MarketDataFetcher.get_batch_prices([]) == {}
    dl.assert_not_called()
