# market_data/broadcaster.py
import asyncio
import json
import logging
import time
from datetime import datetime
import redis.asyncio as redis
from config import REDIS_URL, PRICE_POLL_INTERVAL_SECONDS
from engine.market_calendar import IST, is_market_open

logger = logging.getLogger(__name__)

from market_data.tickers import NIFTY_50

# Tickers to stream (full NIFTY 50)
DEFAULT_TICKERS = NIFTY_50

# Slower poll while the market is closed; must stay below the 120s cache TTL.
CLOSED_MARKET_POLL_SECONDS = 60


class PriceBroadcaster:
    """Redis pub/sub → WebSocket fan-out for live prices"""

    CHANNEL = "live_prices"

    def __init__(self):
        self.redis = redis.from_url(REDIS_URL)
        self._polling_task: asyncio.Task | None = None
        # Optional KiteFeed (market_data/kite_feed.py); None = Yahoo only.
        self.kite_feed = None

    async def publish_price(self, ticker: str, price_data: dict) -> None:
        """Publish a price update to Redis pub/sub"""
        data = json.dumps(price_data)
        await self.redis.publish(self.CHANNEL, data)

    async def subscribe(self):
        """Subscribe to Redis price updates"""
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(self.CHANNEL)
        return pubsub

    async def cache_price(self, ticker: str, price_data: dict) -> None:
        """Cache latest price in Redis. Stamps fetched_at so callers on
        the trade-execution path can tell how stale this entry is —
        display/portfolio paths can use the full 120s TTL, but execution
        needs a much tighter staleness bound (see submit_trade)."""
        stamped = {**price_data, "fetched_at": time.time()}
        await self.redis.set(
            f"price:{ticker}",
            json.dumps(stamped),
            ex=120  # 2 minute TTL
        )

    async def get_cached_price(self, ticker: str) -> dict | None:
        """Get cached price from Redis"""
        data = await self.redis.get(f"price:{ticker}")
        if data:
            return json.loads(data)
        return None

    async def get_all_cached_prices(self) -> dict:
        """Get all cached prices for default tickers"""
        prices = {}
        for ticker in DEFAULT_TICKERS:
            cached = await self.get_cached_price(ticker)
            if cached:
                prices[ticker] = cached
        return prices

    async def start_polling(self) -> None:
        """Start background task that polls yfinance (see _poll_loop)"""
        self._polling_task = asyncio.create_task(self._poll_loop())
        logger.info("Price polling started for tickers: %s", DEFAULT_TICKERS)

    async def _poll_once(self) -> None:
        """Fetch all tickers in one batched request, then cache + publish.

        Each tick carries `market_open` so the UI can label a price as live
        or as the last close instead of calling everything "Live".
        """
        from market_data.fetcher import MarketDataFetcher

        market_open = is_market_open(datetime.now(IST))
        try:
            results = await asyncio.to_thread(
                MarketDataFetcher.get_batch_prices, DEFAULT_TICKERS
            )
        except Exception as e:
            logger.warning("Batch price fetch failed: %s", e)
            return
        missing = [t for t in DEFAULT_TICKERS if t not in results]
        if missing:
            logger.warning("No price returned for %d tickers: %s", len(missing), missing)
        for ticker, price_data in results.items():
            try:
                price_data["market_open"] = market_open
                price_data["source"] = "yahoo"
                await self.cache_price(ticker, price_data)
                await self.publish_price(ticker, price_data)
            except Exception as e:
                logger.warning("Failed to publish price for %s: %s", ticker, e)

    async def _kite_covers(self, market_open: bool) -> bool:
        """True when the Kite feed makes a Yahoo poll unnecessary: it is
        connected AND (a tick arrived recently, or the market is closed so
        no ticks are expected). While closed we additionally require the
        Redis cache to still hold every ticker, because entries expire
        after 120s and Kite sends nothing on a closed market; without this
        the last close would vanish from the cache shortly after 15:30."""
        feed = self.kite_feed
        if feed is None or not feed.connected:
            return False
        if market_open:
            return feed.has_fresh_tick()
        try:
            keys = [f"price:{t}" for t in DEFAULT_TICKERS]
            values = await self.redis.mget(keys)
            return all(v is not None for v in values)
        except Exception as e:
            logger.warning("Cache check failed, polling Yahoo: %s", e)
            return False

    async def _poll_loop(self) -> None:
        """Main polling loop — runs until cancelled.

        Polls every PRICE_POLL_INTERVAL_SECONDS while NSE is open. When it
        is closed prices cannot move, so it backs off to
        CLOSED_MARKET_POLL_SECONDS (kept under the 120s cache TTL so the
        last close stays cached and the open is noticed within a minute).
        """
        while True:
            open_now = is_market_open(datetime.now(IST))
            if not await self._kite_covers(open_now):
                await self._poll_once()
            delay = PRICE_POLL_INTERVAL_SECONDS if open_now else CLOSED_MARKET_POLL_SECONDS
            try:
                await asyncio.sleep(delay)
            except asyncio.CancelledError:
                logger.info("Price polling stopped")
                return

    async def stop_polling(self) -> None:
        """Stop the background polling task"""
        if self._polling_task and not self._polling_task.done():
            self._polling_task.cancel()
            try:
                await self._polling_task
            except asyncio.CancelledError:
                pass
            logger.info("Price polling task cancelled")

    async def check_health(self) -> bool:
        """Check if Redis is reachable"""
        try:
            await self.redis.ping()
            return True
        except Exception:
            return False

    async def close(self):
        await self.stop_polling()
        await self.redis.close()
