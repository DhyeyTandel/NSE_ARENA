# tests/test_fetcher.py
"""Unit tests for MarketDataFetcher — all yfinance calls are mocked."""

import json
from unittest.mock import patch

import pandas as pd
import pytest

from market_data.fetcher import MarketDataFetcher
from tests.conftest import MOCK_INFO, _make_mock_ticker

NAN = float("nan")


class TestGetPrice:
    def test_appends_ns_suffix(self, mock_yfinance):
        """Bare ticker like 'RELIANCE' should become 'RELIANCE.NS' internally."""
        MarketDataFetcher.get_price("RELIANCE")
        mock_yfinance.assert_called_once_with("RELIANCE.NS")

    def test_no_double_suffix(self, mock_yfinance):
        """'RELIANCE.NS' should NOT become 'RELIANCE.NS.NS'."""
        MarketDataFetcher.get_price("RELIANCE.NS")
        mock_yfinance.assert_called_once_with("RELIANCE.NS")

    def test_returns_expected_fields(self, mock_yfinance):
        """Response dict must contain all 7 expected keys."""
        result = MarketDataFetcher.get_price("TCS")
        expected_keys = {
            "ticker", "price", "previous_close", "open",
            "day_high", "day_low", "volume", "change_pct",
        }
        assert set(result.keys()) == expected_keys

    def test_returns_correct_values(self, mock_yfinance):
        """Spot-check that mock data flows through correctly."""
        result = MarketDataFetcher.get_price("INFY")
        assert result["price"] == 2891.45
        assert result["previous_close"] == 2847.30
        assert result["volume"] == 5_234_100


class TestGetOhlcv:
    def test_returns_list_of_candles(self, mock_yfinance):
        """OHLCV should return a list of dicts with the right shape."""
        data = MarketDataFetcher.get_ohlcv("RELIANCE", period="1mo")
        assert isinstance(data, list)
        assert len(data) == 3  # 3 rows in mock
        for candle in data:
            assert set(candle.keys()) == {"time", "open", "high", "low", "close", "volume"}
            assert isinstance(candle["time"], int)
            assert isinstance(candle["volume"], int)

    def test_rounds_prices_to_2dp(self, mock_yfinance):
        """Prices should be rounded to 2 decimal places."""
        data = MarketDataFetcher.get_ohlcv("TCS")
        # Mock close values: 2870.123, 2880.456, 2875.789
        assert data[0]["close"] == 2870.12
        assert data[1]["close"] == 2880.46
        assert data[2]["close"] == 2875.79

    def test_skips_candles_with_nan_prices(self):
        """NaN OHLC rows are dropped so the result is JSON serializable."""
        df = pd.DataFrame(
            {
                "Open": [2850.0, NAN, 2860.0],
                "High": [2880.0, 2900.0, 2890.0],
                "Low": [2830.0, 2850.0, NAN],
                "Close": [2870.0, 2880.0, 2875.0],
                "Volume": [5000000, 4500000, 4800000],
            },
            index=pd.to_datetime(["2026-03-10", "2026-03-11", "2026-03-12"]),
        )
        with patch("yfinance.Ticker", side_effect=lambda t: _make_mock_ticker(history_df=df)):
            data = MarketDataFetcher.get_ohlcv("RELIANCE")
        assert len(data) == 1
        assert data[0]["open"] == 2850.0
        json.dumps(data, allow_nan=False)

    def test_nan_volume_becomes_zero(self):
        df = pd.DataFrame(
            {
                "Open": [2850.0], "High": [2880.0], "Low": [2830.0],
                "Close": [2870.0], "Volume": [NAN],
            },
            index=pd.to_datetime(["2026-03-10"]),
        )
        with patch("yfinance.Ticker", side_effect=lambda t: _make_mock_ticker(history_df=df)):
            data = MarketDataFetcher.get_ohlcv("RELIANCE")
        assert len(data) == 1
        assert data[0]["volume"] == 0


class TestGetOhlcvInterval:
    def test_passes_period_and_interval(self):
        t = _make_mock_ticker()
        with patch("yfinance.Ticker", return_value=t):
            MarketDataFetcher.get_ohlcv("RELIANCE", period="5d", interval="30m")
        t.history.assert_called_once_with(period="5d", interval="30m")

    def test_default_interval_is_daily(self):
        t = _make_mock_ticker()
        with patch("yfinance.Ticker", return_value=t):
            MarketDataFetcher.get_ohlcv("RELIANCE")
        t.history.assert_called_once_with(period="1mo", interval="1d")

    def test_intraday_nan_rows_skipped(self):
        df = pd.DataFrame(
            {"Open": [1.0, NAN], "High": [2.0, 2.0], "Low": [1.0, 1.0],
             "Close": [1.5, 1.5], "Volume": [10, 10]},
            index=pd.to_datetime(["2026-11-13 09:15", "2026-11-13 09:20"]).tz_localize("Asia/Kolkata"),
        )
        with patch("yfinance.Ticker", return_value=_make_mock_ticker(history_df=df)):
            data = MarketDataFetcher.get_ohlcv("RELIANCE", period="1d", interval="5m")
        assert len(data) == 1

    def test_empty_1d_falls_back_to_last_session_only(self):
        idx = pd.to_datetime(["2026-11-12 09:15", "2026-11-12 09:20",
                              "2026-11-13 09:15", "2026-11-13 09:20"]).tz_localize("Asia/Kolkata")
        df = pd.DataFrame({"Open": [1.0] * 4, "High": [2.0] * 4, "Low": [1.0] * 4,
                           "Close": [1.5] * 4, "Volume": [1] * 4}, index=idx)
        t = _make_mock_ticker()
        t.history.side_effect = [df.iloc[0:0], df]
        with patch("yfinance.Ticker", return_value=t):
            data = MarketDataFetcher.get_ohlcv("RELIANCE", period="1d", interval="5m")
        assert [b["time"] for b in data] == [int(i.timestamp()) for i in idx[2:]]
        assert t.history.call_args_list[1].kwargs == {"period": "5d", "interval": "5m"}


class TestGetPriceNaN:
    def test_nan_price_raises(self):
        info = {**MOCK_INFO, "currentPrice": NAN, "regularMarketPrice": NAN}
        with patch("yfinance.Ticker", side_effect=lambda t: _make_mock_ticker(info=info)):
            with pytest.raises(ValueError):
                MarketDataFetcher.get_price("RELIANCE")

    def test_nan_secondary_fields_become_zero(self):
        info = {**MOCK_INFO, "dayHigh": NAN, "volume": NAN, "regularMarketChangePercent": NAN}
        with patch("yfinance.Ticker", side_effect=lambda t: _make_mock_ticker(info=info)):
            result = MarketDataFetcher.get_price("RELIANCE")
        assert result["price"] == 2891.45
        assert result["day_high"] == 0
        assert result["volume"] == 0
        assert result["change_pct"] == 0
        json.dumps(result, allow_nan=False)


class TestGetMultiplePrices:
    def test_nan_price_yields_error_entry(self):
        info = {**MOCK_INFO, "currentPrice": NAN, "regularMarketPrice": NAN}
        with patch("yfinance.Ticker", side_effect=lambda t: _make_mock_ticker(info=info)):
            result = MarketDataFetcher.get_multiple_prices(["TCS"])
        assert result["TCS"] == {"ticker": "TCS", "price": 0, "error": True}

    def test_handles_error_gracefully(self, mock_yfinance_error):
        """When yfinance fails, return an error dict instead of crashing."""
        result = MarketDataFetcher.get_multiple_prices(["RELIANCE", "TCS"])
        for ticker in ["RELIANCE", "TCS"]:
            assert result[ticker]["ticker"] == ticker
            assert result[ticker]["price"] == 0
            assert result[ticker]["error"] is True
