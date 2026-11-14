# tests/test_price_polling.py
"""Price polling: every tick is tagged with market_open (so the UI stops
calling a last-close price "Live"), one bad ticker does not stop the rest,
and the loop polls faster while NSE is open than when it is closed.
"""
import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from market_data import broadcaster as b


def _fake_batch(tickers):
    return {t: {"ticker": t, "price": 100.0, "change_pct": 0.5}
            for t in tickers if t != "TCS"}


@pytest.mark.asyncio
@pytest.mark.parametrize("is_open", [True, False])
async def test_ticks_carry_market_open_and_omitted_ticker_is_skipped(is_open):
    pb = b.PriceBroadcaster()
    pb.cache_price = AsyncMock()
    pb.publish_price = AsyncMock()
    with patch("market_data.fetcher.MarketDataFetcher.get_batch_prices", side_effect=_fake_batch), \
         patch.object(b, "is_market_open", return_value=is_open):
        await pb._poll_once()

    published = {c.args[0]: c.args[1] for c in pb.publish_price.await_args_list}
    assert set(published) == set(b.DEFAULT_TICKERS) - {"TCS"}
    assert all(p["market_open"] is is_open for p in published.values())
    assert pb.cache_price.await_count == len(published)


@pytest.mark.asyncio
async def test_whole_batch_failure_does_not_raise():
    pb = b.PriceBroadcaster()
    pb.cache_price = AsyncMock()
    pb.publish_price = AsyncMock()
    with patch("market_data.fetcher.MarketDataFetcher.get_batch_prices", side_effect=RuntimeError("yahoo down")):
        await pb._poll_once()
    pb.publish_price.assert_not_awaited()


@pytest.mark.asyncio
async def test_loop_keeps_going_after_poll_failure():
    pb = b.PriceBroadcaster()
    calls = []

    async def fake_sleep(delay):
        if len(calls) >= 2:
            raise asyncio.CancelledError

    with patch("market_data.fetcher.MarketDataFetcher.get_batch_prices",
               side_effect=[RuntimeError("boom"), _fake_batch(b.DEFAULT_TICKERS)]), \
         patch.object(b, "is_market_open", return_value=True), \
         patch.object(b.asyncio, "sleep", fake_sleep):
        pb.cache_price = AsyncMock()
        pb.publish_price = AsyncMock()
        orig = pb._poll_once

        async def counting():
            calls.append(1)
            await orig()
        pb._poll_once = counting
        await pb._poll_loop()

    assert len(calls) == 2
    assert pb.publish_price.await_count > 0


@pytest.mark.asyncio
@pytest.mark.parametrize("is_open,expected", [
    (True, b.PRICE_POLL_INTERVAL_SECONDS),
    (False, b.CLOSED_MARKET_POLL_SECONDS),
])
async def test_loop_delay_depends_on_market_hours(is_open, expected):
    pb = b.PriceBroadcaster()
    pb._poll_once = AsyncMock()
    sleeps = []

    async def fake_sleep(delay):
        sleeps.append(delay)
        raise asyncio.CancelledError

    with patch.object(b, "is_market_open", return_value=is_open), \
         patch.object(b.asyncio, "sleep", fake_sleep):
        await pb._poll_loop()

    assert sleeps == [expected]


def test_intervals_are_sane():
    assert 5 <= b.PRICE_POLL_INTERVAL_SECONDS < b.CLOSED_MARKET_POLL_SECONDS < 120
