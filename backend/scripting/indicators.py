# scripting/indicators.py
"""
Pure-Python implementations of common technical-analysis functions.
Each function accepts numpy arrays and returns numpy arrays so the
scripting engine can work without pandas overhead at execution time.
"""
import numpy as np


# ── Trend ───────────────────────────────────────────────────────────────────

def sma(source: np.ndarray, length: int) -> np.ndarray:
    """Simple Moving Average"""
    out = np.full_like(source, np.nan, dtype=float)
    if length < 1 or length > len(source):
        return out
    cumsum = np.cumsum(source, dtype=float)
    cumsum[length:] = cumsum[length:] - cumsum[:-length]
    out[length - 1:] = cumsum[length - 1:] / length
    return out


def ema(source: np.ndarray, length: int) -> np.ndarray:
    """Exponential Moving Average"""
    out = np.full_like(source, np.nan, dtype=float)
    if length < 1 or length > len(source):
        return out
    k = 2.0 / (length + 1)
    out[length - 1] = np.mean(source[:length])
    for i in range(length, len(source)):
        out[i] = source[i] * k + out[i - 1] * (1 - k)
    return out


def wma(source: np.ndarray, length: int) -> np.ndarray:
    """Weighted Moving Average"""
    out = np.full_like(source, np.nan, dtype=float)
    if length < 1 or length > len(source):
        return out
    weights = np.arange(1, length + 1, dtype=float)
    w_sum = weights.sum()
    for i in range(length - 1, len(source)):
        out[i] = np.dot(source[i - length + 1:i + 1], weights) / w_sum
    return out


# ── Momentum / Oscillators ──────────────────────────────────────────────────

def rsi(source: np.ndarray, length: int) -> np.ndarray:
    """Relative Strength Index (Wilder smoothing)"""
    out = np.full_like(source, np.nan, dtype=float)
    if length < 1 or len(source) < length + 1:
        return out
    deltas = np.diff(source)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    avg_gain = np.mean(gains[:length])
    avg_loss = np.mean(losses[:length])

    if avg_loss == 0:
        out[length] = 100.0
    else:
        rs = avg_gain / avg_loss
        out[length] = 100.0 - 100.0 / (1.0 + rs)

    for i in range(length, len(deltas)):
        avg_gain = (avg_gain * (length - 1) + gains[i]) / length
        avg_loss = (avg_loss * (length - 1) + losses[i]) / length
        if avg_loss == 0:
            out[i + 1] = 100.0
        else:
            rs = avg_gain / avg_loss
            out[i + 1] = 100.0 - 100.0 / (1.0 + rs)
    return out


def macd(source: np.ndarray, fast: int = 12, slow: int = 26,
         signal_len: int = 9) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """MACD → (macd_line, signal_line, histogram)"""
    fast_ema = ema(source, fast)
    slow_ema = ema(source, slow)
    macd_line = fast_ema - slow_ema
    signal_line = ema(macd_line, signal_len)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def stoch(close: np.ndarray, high: np.ndarray, low: np.ndarray,
          length: int = 14) -> np.ndarray:
    """%K of Stochastic Oscillator"""
    out = np.full_like(close, np.nan, dtype=float)
    if length < 1:
        return out
    for i in range(length - 1, len(close)):
        hh = np.max(high[i - length + 1:i + 1])
        ll = np.min(low[i - length + 1:i + 1])
        denom = hh - ll
        if denom == 0:
            out[i] = 50.0
        else:
            out[i] = (close[i] - ll) / denom * 100.0
    return out


def roc(source: np.ndarray, length: int) -> np.ndarray:
    """Rate of Change (percentage)"""
    out = np.full_like(source, np.nan, dtype=float)
    for i in range(length, len(source)):
        prev = source[i - length]
        if prev != 0:
            out[i] = (source[i] - prev) / prev * 100.0
    return out


# ── Volatility ──────────────────────────────────────────────────────────────

def bbands(source: np.ndarray, length: int = 20,
           mult: float = 2.0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Bollinger Bands → (upper, middle, lower)"""
    middle = sma(source, length)
    std = np.full_like(source, np.nan, dtype=float)
    for i in range(length - 1, len(source)):
        std[i] = np.std(source[i - length + 1:i + 1], ddof=0)
    upper = middle + mult * std
    lower = middle - mult * std
    return upper, middle, lower


def atr(high: np.ndarray, low: np.ndarray, close: np.ndarray,
        length: int = 14) -> np.ndarray:
    """Average True Range"""
    tr = np.zeros_like(close, dtype=float)
    tr[0] = high[0] - low[0]
    for i in range(1, len(close)):
        tr[i] = max(high[i] - low[i],
                     abs(high[i] - close[i - 1]),
                     abs(low[i] - close[i - 1]))
    # Wilder smoothing (same as RMA)
    out = np.full_like(close, np.nan, dtype=float)
    if length > len(close):
        return out
    out[length - 1] = np.mean(tr[:length])
    for i in range(length, len(close)):
        out[i] = (out[i - 1] * (length - 1) + tr[i]) / length
    return out


def vwap(close: np.ndarray, volume: np.ndarray) -> np.ndarray:
    """Volume Weighted Average Price (cumulative)"""
    cum_vol = np.cumsum(volume, dtype=float)
    cum_pv = np.cumsum(close * volume, dtype=float)
    out = np.where(cum_vol > 0, cum_pv / cum_vol, np.nan)
    return out


# ── Utility / Crossover ────────────────────────────────────────────────────

def crossover(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """True when `a` crosses above `b`"""
    out = np.zeros(len(a), dtype=bool)
    for i in range(1, len(a)):
        if not (np.isnan(a[i]) or np.isnan(b[i]) or
                np.isnan(a[i - 1]) or np.isnan(b[i - 1])):
            out[i] = a[i] > b[i] and a[i - 1] <= b[i - 1]
    return out


def crossunder(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """True when `a` crosses below `b`"""
    out = np.zeros(len(a), dtype=bool)
    for i in range(1, len(a)):
        if not (np.isnan(a[i]) or np.isnan(b[i]) or
                np.isnan(a[i - 1]) or np.isnan(b[i - 1])):
            out[i] = a[i] < b[i] and a[i - 1] >= b[i - 1]
    return out


def highest(source: np.ndarray, length: int) -> np.ndarray:
    """Highest value over last `length` bars"""
    out = np.full_like(source, np.nan, dtype=float)
    for i in range(length - 1, len(source)):
        out[i] = np.max(source[i - length + 1:i + 1])
    return out


def lowest(source: np.ndarray, length: int) -> np.ndarray:
    """Lowest value over last `length` bars"""
    out = np.full_like(source, np.nan, dtype=float)
    for i in range(length - 1, len(source)):
        out[i] = np.min(source[i - length + 1:i + 1])
    return out
