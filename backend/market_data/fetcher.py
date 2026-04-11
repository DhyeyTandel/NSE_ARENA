# market_data/fetcher.py
import yfinance as yf
from datetime import datetime


class MarketDataFetcher:
    """Fetches real NSE/BSE market data using yfinance"""

    @staticmethod
    def get_price(ticker: str) -> dict:
        """Get current price for an NSE stock"""
        nse_ticker = ticker if ticker.endswith(".NS") else f"{ticker}.NS"
        stock = yf.Ticker(nse_ticker)
        info = stock.info
        return {
            "ticker": ticker.replace(".NS", ""),
            "price": info.get("currentPrice", info.get("regularMarketPrice", 0)),
            "previous_close": info.get("previousClose", 0),
            "open": info.get("open", 0),
            "day_high": info.get("dayHigh", 0),
            "day_low": info.get("dayLow", 0),
            "volume": info.get("volume", 0),
            "change_pct": info.get("regularMarketChangePercent", 0),
        }

    @staticmethod
    def get_ohlcv(ticker: str, period: str = "1mo") -> list[dict]:
        """Get OHLCV data for charting"""
        nse_ticker = ticker if ticker.endswith(".NS") else f"{ticker}.NS"
        stock = yf.Ticker(nse_ticker)
        hist = stock.history(period=period)

        data = []
        for date, row in hist.iterrows():
            data.append({
                "time": int(date.timestamp()),
                "open": round(row["Open"], 2),
                "high": round(row["High"], 2),
                "low": round(row["Low"], 2),
                "close": round(row["Close"], 2),
                "volume": int(row["Volume"]),
            })
        return data

    @staticmethod
    def get_multiple_prices(tickers: list[str]) -> dict:
        """Get prices for multiple tickers"""
        prices = {}
        for ticker in tickers:
            try:
                data = MarketDataFetcher.get_price(ticker)
                prices[ticker] = data
            except Exception:
                prices[ticker] = {"ticker": ticker, "price": 0, "error": True}
        return prices
