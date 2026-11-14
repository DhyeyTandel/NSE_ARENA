# market_data/fetcher.py
import math

import yfinance as yf
from datetime import datetime, timedelta, timezone


def _is_bad(value) -> bool:
    """True for None or NaN/inf (yfinance emits NaN for missing data, and
    NaN is not JSON compliant so it 500s the endpoint if it leaks out)."""
    try:
        return value is None or not math.isfinite(float(value))
    except (TypeError, ValueError):
        return True


def _num_or_zero(value):
    return 0 if _is_bad(value) else value


class MarketDataFetcher:
    """Fetches real NSE/BSE market data using yfinance"""

    @staticmethod
    def get_price(ticker: str) -> dict:
        """Get current price for an NSE stock"""
        nse_ticker = ticker if ticker.endswith(".NS") else f"{ticker}.NS"
        stock = yf.Ticker(nse_ticker)
        info = stock.info
        price = info.get("currentPrice", info.get("regularMarketPrice", 0))
        if _is_bad(price):
            # Callers already treat a raised exception as "no usable quote"
            # (fallback price / refetch-failed rejection / error dict in
            # get_multiple_prices); NaN must not leak out as a price.
            raise ValueError(f"No valid price available for {ticker}")
        return {
            "ticker": ticker.replace(".NS", ""),
            "price": price,
            "previous_close": _num_or_zero(info.get("previousClose", 0)),
            "open": _num_or_zero(info.get("open", 0)),
            "day_high": _num_or_zero(info.get("dayHigh", 0)),
            "day_low": _num_or_zero(info.get("dayLow", 0)),
            "volume": _num_or_zero(info.get("volume", 0)),
            "change_pct": _num_or_zero(info.get("regularMarketChangePercent", 0)),
        }

    @staticmethod
    def get_batch_prices(tickers: list[str]) -> dict[str, dict]:
        """Get prices for many tickers in two yfinance requests total.

        Same dict shape as get_price (change_pct in percent). Tickers with
        missing/NaN data are omitted. Raises if the downloads fail.

        Two frames, because neither alone is right:
        - 1-minute bars of the latest session give the actual last traded
          price plus the session's open/high/low/volume.
        - Daily bars give the previous close. They cannot give the price:
          Yahoo returns the current day's daily bar with a NaN Close, so
          "latest daily close" silently reports the day before.
        """
        names = [t.replace(".NS", "") for t in tickers]
        if not names:
            return {}
        symbols = [f"{n}.NS" for n in names]
        common = dict(group_by="ticker", threads=True, progress=False, auto_adjust=False)
        intraday = yf.download(symbols, period="1d", interval="1m", **common)
        daily = yf.download(symbols, period="5d", interval="1d", **common)

        out: dict[str, dict] = {}
        for name in names:
            try:
                days = daily[f"{name}.NS"].dropna(subset=["Close"])
                try:
                    mins = intraday[f"{name}.NS"].dropna(subset=["Close"])
                except KeyError:
                    mins = None

                if mins is not None and not mins.empty:
                    price = float(mins["Close"].iloc[-1])
                    session_date = mins.index[-1].date()
                    # Previous close = last completed daily bar before this session.
                    earlier = days[[d.date() < session_date for d in days.index]]
                    prev = float(earlier["Close"].iloc[-1]) if not earlier.empty else 0
                    day_open = mins["Open"].dropna()
                    day_open = float(day_open.iloc[0]) if not day_open.empty else 0
                    day_high, day_low = float(mins["High"].max()), float(mins["Low"].min())
                    volume = mins["Volume"].sum()
                elif not days.empty:
                    # No intraday data (e.g. thinly traded): fall back to daily bars.
                    last = days.iloc[-1]
                    price = float(last["Close"])
                    prev = float(days["Close"].iloc[-2]) if len(days) >= 2 else 0
                    day_open, day_high, day_low = float(last["Open"]), float(last["High"]), float(last["Low"])
                    volume = last["Volume"]
                else:
                    continue

                if _is_bad(price):
                    continue
                if _is_bad(prev):
                    prev = 0
                out[name] = {
                    "ticker": name,
                    "price": price,
                    "previous_close": prev,
                    "open": _num_or_zero(day_open),
                    "day_high": _num_or_zero(day_high),
                    "day_low": _num_or_zero(day_low),
                    "volume": int(_num_or_zero(volume)),
                    "change_pct": (price - prev) / prev * 100 if prev else 0,
                }
            except (KeyError, IndexError, ValueError, TypeError):
                continue
        return out

    @staticmethod
    def _history_to_bars(hist) -> list[dict]:
        data = []
        for date, row in hist.iterrows():
            if any(_is_bad(row[c]) for c in ("Open", "High", "Low", "Close")):
                continue  # incomplete candle; NaN would break JSON serialization
            data.append({
                "time": int(date.timestamp()),
                "open": round(row["Open"], 2),
                "high": round(row["High"], 2),
                "low": round(row["Low"], 2),
                "close": round(row["Close"], 2),
                "volume": int(_num_or_zero(row["Volume"])),
            })
        return data

    @staticmethod
    def get_ohlcv(ticker: str, period: str = "1mo", interval: str = "1d") -> list[dict]:
        """Get OHLCV data for charting (time = unix seconds)"""
        nse_ticker = ticker if ticker.endswith(".NS") else f"{ticker}.NS"
        stock = yf.Ticker(nse_ticker)
        hist = stock.history(period=period, interval=interval)
        data = MarketDataFetcher._history_to_bars(hist)
        if not data and period == "1d":
            # Weekend/holiday/pre-open: "1d" can come back empty. Fall back to
            # 5 days and keep only the most recent session's bars.
            data = MarketDataFetcher._history_to_bars(
                stock.history(period="5d", interval=interval))
            if data:
                ist = timezone(timedelta(hours=5, minutes=30))
                last_day = datetime.fromtimestamp(data[-1]["time"], ist).date()
                data = [b for b in data
                        if datetime.fromtimestamp(b["time"], ist).date() == last_day]
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
