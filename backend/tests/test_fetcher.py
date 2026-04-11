# tests/test_fetcher.py
"""Unit tests for MarketDataFetcher — all yfinance calls are mocked."""

from market_data.fetcher import MarketDataFetcher


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


class TestGetMultiplePrices:
    def test_handles_error_gracefully(self, mock_yfinance_error):
        """When yfinance fails, return an error dict instead of crashing."""
        result = MarketDataFetcher.get_multiple_prices(["RELIANCE", "TCS"])
        for ticker in ["RELIANCE", "TCS"]:
            assert result[ticker]["ticker"] == ticker
            assert result[ticker]["price"] == 0
            assert result[ticker]["error"] is True
