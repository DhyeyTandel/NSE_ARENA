# market_data/broadcaster.py
import asyncio
import json
import logging
import redis.asyncio as redis
from config import REDIS_URL

logger = logging.getLogger(__name__)

# Default tickers to stream
DEFAULT_TICKERS = ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK"]


class PriceBroadcaster:
    """Redis pub/sub → WebSocket fan-out for live prices"""

    CHANNEL = "live_prices"

    def __init__(self):
        self.redis = redis.from_url(REDIS_URL)
        self._polling_task: asyncio.Task | None = None

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
        """Cache latest price in Redis"""
        await self.redis.set(
            f"price:{ticker}",
            json.dumps(price_data),
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
        """Start background task that polls yfinance every 60 seconds"""
        self._polling_task = asyncio.create_task(self._poll_loop())
        logger.info("Price polling started for tickers: %s", DEFAULT_TICKERS)

    async def _poll_loop(self) -> None:
        """Main polling loop — runs until cancelled"""
        from market_data.fetcher import MarketDataFetcher

        while True:
            for ticker in DEFAULT_TICKERS:
                try:
                    price_data = MarketDataFetcher.get_price(ticker)
                    # Cache in Redis
                    await self.cache_price(ticker, price_data)
                    # Publish to subscribers
                    await self.publish_price(ticker, price_data)
                    logger.debug("Published price for %s: ₹%.2f", ticker, price_data.get("price", 0))
                except Exception as e:
                    logger.warning("Failed to fetch price for %s: %s", ticker, e)

            # Wait 60 seconds before next poll
            try:
                await asyncio.sleep(60)
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
