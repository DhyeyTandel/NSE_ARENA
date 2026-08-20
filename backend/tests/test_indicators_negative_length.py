# tests/test_indicators_negative_length.py
"""P1 audit fix: several scripting indicators didn't guard against a
negative `length` argument the way sma/ema/wma/rsi already did. A script
like `plot(ta.highest(close, -999999999))` would drive a near-unbounded
Python loop (`range(negative_length, len(source))` iterates roughly
abs(negative_length) times) — a real DoS gap in a sandboxed script
execution path with a nominal 10s timeout that doesn't actually cancel
the underlying thread. Each of these must return an all-NaN array
immediately for length <= 0, not loop.
"""
import time

import numpy as np
import pytest

from scripting import indicators as ta

SOURCE = np.array([float(i) for i in range(1, 21)])  # 20 bars


@pytest.mark.parametrize("fn,kwargs", [
    (ta.roc, {}),
    (ta.highest, {}),
    (ta.lowest, {}),
])
def test_negative_length_returns_immediately_not_loops(fn, kwargs):
    start = time.monotonic()
    out = fn(SOURCE, -999_999_999, **kwargs)
    elapsed = time.monotonic() - start

    assert elapsed < 1.0, f"{fn.__name__} took {elapsed:.2f}s for a negative length — looped instead of guarding"
    assert len(out) == len(SOURCE)
    assert np.all(np.isnan(out))


def test_atr_negative_length_returns_immediately_not_loops():
    high = SOURCE + 1
    low = SOURCE - 1
    close = SOURCE

    start = time.monotonic()
    out = ta.atr(high, low, close, length=-999_999_999)
    elapsed = time.monotonic() - start

    assert elapsed < 1.0, f"atr took {elapsed:.2f}s for a negative length — looped instead of guarding"
    assert len(out) == len(SOURCE)
    assert np.all(np.isnan(out))


def test_stoch_negative_length_already_guarded():
    """Confirms stoch's existing `length < 1` guard still holds — not a
    new fix, just locking in the behavior so a future edit can't regress it."""
    high = SOURCE + 1
    low = SOURCE - 1
    close = SOURCE

    out = ta.stoch(close, high, low, length=-999_999_999)
    assert np.all(np.isnan(out))


def test_zero_length_also_guarded():
    """length=0 is as meaningless as a negative length for all of these."""
    for fn in (ta.roc, ta.highest, ta.lowest):
        out = fn(SOURCE, 0)
        assert np.all(np.isnan(out)), f"{fn.__name__}(length=0) should be all-NaN"


def test_positive_length_still_computes_correctly():
    """Sanity check the guards didn't break the happy path."""
    result = ta.highest(SOURCE, 3)
    assert result[-1] == 20.0  # max of last 3 of [.., 18, 19, 20]
    result = ta.lowest(SOURCE, 3)
    assert result[-1] == 18.0
    result = ta.roc(SOURCE, 1)
    assert result[-1] == pytest.approx((20.0 - 19.0) / 19.0 * 100.0)
