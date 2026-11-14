# market_data/kite_feed.py
"""Optional real-time prices from Zerodha Kite Connect.

READ-ONLY market data. This module only uses login_url, generate_session,
invalidate_access_token, instruments and the KiteTicker websocket. It must
never call anything that places, modifies or cancels an order.

The kiteconnect package is imported lazily so the app (and its tests) run
even when it is missing or broken on the current Python version.

Threading: KiteTicker runs a Twisted reactor in its own thread. Its
callbacks therefore run off the asyncio loop; they only touch plain
attributes and hand finished ticks to the loop with
asyncio.run_coroutine_threadsafe.
"""
import asyncio
import logging
import time
from datetime import datetime, timedelta

from engine.market_calendar import IST, is_market_open
from market_data.tickers import NIFTY_50

logger = logging.getLogger(__name__)

TOKEN_KEY = "kite:access_token"
MAX_TICK_AGE_SECONDS = 30
PUBLISH_INTERVAL_SECONDS = 1.0


def seconds_until_next_6am_ist(now: datetime | None = None) -> int:
    """Kite access tokens die at ~06:00 IST the next day."""
    now = (now or datetime.now(IST)).astimezone(IST)
    target = now.replace(hour=6, minute=0, second=0, microsecond=0)
    if now >= target:
        target += timedelta(days=1)
    return max(1, int((target - now).total_seconds()))


def map_tick(tick: dict, symbol: str, market_open: bool) -> dict | None:
    """Kite quote-mode tick -> the app's tick dict. None if unusable."""
    price = tick.get("last_price")
    if not price:
        return None
    ohlc = tick.get("ohlc") or {}
    prev = ohlc.get("close") or 0
    return {
        "ticker": symbol,
        "price": price,
        "previous_close": prev,
        "open": ohlc.get("open", 0),
        "day_high": ohlc.get("high", 0),
        "day_low": ohlc.get("low", 0),
        "volume": tick.get("volume_traded", 0),
        "change_pct": (price - prev) / prev * 100 if prev else 0,
        "market_open": market_open,
        "source": "kite",
    }


def _sdk():
    """(KiteConnect, KiteTicker, TokenException) or None if unavailable."""
    try:
        from kiteconnect import KiteConnect, KiteTicker
        from kiteconnect.exceptions import TokenException
        return KiteConnect, KiteTicker, TokenException
    except Exception as e:  # missing package or broken on this Python
        logger.warning("kiteconnect unavailable: %s", e)
        return None


def _in_reactor(fn, *args, **kwargs):
    """Run fn on the Twisted reactor thread if it is already running
    (a later ticker reuses the existing reactor; Twisted cannot restart
    one). Otherwise just call it."""
    try:
        from twisted.internet import reactor
        if reactor.running:
            reactor.callFromThread(fn, *args, **kwargs)
            return
    except Exception:
        pass
    fn(*args, **kwargs)


def _looks_like_token_error(code, reason) -> bool:
    text = f"{code} {reason}".lower()
    return any(m in text for m in ("403", "forbidden", "token", "unauthor"))


class KiteFeed:
    def __init__(self, broadcaster, api_key: str, api_secret: str, clock=time.monotonic):
        self.broadcaster = broadcaster
        self.api_key = api_key
        self.api_secret = api_secret
        self._clock = clock
        self.connected = False
        self.last_tick_at: float | None = None  # epoch seconds
        self._ticker = None
        self._access_token: str | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._token_to_symbol: dict[int, str] = {}
        self._instruments_date = None
        self._last_pub: dict[str, float] = {}

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.api_secret)

    def has_fresh_tick(self, max_age: float = MAX_TICK_AGE_SECONDS) -> bool:
        return self.last_tick_at is not None and (time.time() - self.last_tick_at) <= max_age

    # ── token storage (Redis, expires at next 06:00 IST) ──────────────

    async def _store_token(self, token: str) -> None:
        await self.broadcaster.redis.set(TOKEN_KEY, token, ex=seconds_until_next_6am_ist())

    async def _clear_token(self) -> None:
        self._access_token = None
        try:
            await self.broadcaster.redis.delete(TOKEN_KEY)
        except Exception as e:
            logger.warning("Could not clear stored Kite token: %s", e)

    async def _load_token(self) -> str | None:
        raw = await self.broadcaster.redis.get(TOKEN_KEY)
        if not raw:
            return None
        return raw.decode() if isinstance(raw, bytes) else raw

    # ── lifecycle ─────────────────────────────────────────────────────

    async def start_from_stored(self) -> bool:
        if not self.configured:
            return False
        token = await self._load_token()
        if not token:
            return False
        return await self.start(token)

    async def login(self, request_token: str) -> bool:
        """Exchange the callback's request_token, store it, start the feed.
        Raises on failure; callers must not echo the exception."""
        if not self.configured:
            return False
        sdk = _sdk()
        if sdk is None:
            return False
        KiteConnect = sdk[0]
        kite = KiteConnect(api_key=self.api_key)
        session = await asyncio.to_thread(kite.generate_session, request_token, self.api_secret)
        token = session["access_token"]
        await self._store_token(token)
        return await self.start(token)

    async def start(self, access_token: str) -> bool:
        if not self.configured:
            return False
        sdk = _sdk()
        if sdk is None:
            return False
        KiteConnect, KiteTicker, TokenException = sdk
        await self.stop(clear_token=False)
        self._loop = asyncio.get_running_loop()
        try:
            await asyncio.to_thread(self._load_instruments, KiteConnect, access_token)
        except TokenException:
            logger.warning("Kite access token rejected; clearing it")
            await self._clear_token()
            return False
        except Exception as e:
            logger.warning("Kite instruments fetch failed: %s", type(e).__name__)
            return False
        if not self._token_to_symbol:
            logger.warning("No NIFTY 50 instruments resolved; Kite feed not started")
            return False

        self._access_token = access_token
        ticker = KiteTicker(self.api_key, access_token, reconnect=True)
        ticker.on_connect = self._on_connect
        ticker.on_ticks = self._on_ticks
        ticker.on_close = self._on_close
        ticker.on_error = self._on_error
        ticker.on_noreconnect = self._on_noreconnect
        self._ticker = ticker
        # Starts the Twisted reactor thread on first use.
        _in_reactor(ticker.connect, threaded=True)
        logger.info("Kite feed starting for %d instruments", len(self._token_to_symbol))
        return True

    async def stop(self, clear_token: bool = True) -> None:
        """Stop the websocket. clear_token also deletes the stored token
        and invalidates it at Kite (explicit disconnect, not shutdown)."""
        ticker, self._ticker = self._ticker, None
        self.connected = False
        if ticker is not None:
            try:
                _in_reactor(ticker.close)
            except Exception as e:
                logger.warning("Kite ticker close failed: %s", e)
        if clear_token:
            token = self._access_token or await self._load_token()
            sdk = _sdk()
            if token and sdk is not None and self.configured:
                try:
                    kite = sdk[0](api_key=self.api_key)
                    await asyncio.to_thread(kite.invalidate_access_token, token)
                except Exception as e:
                    logger.warning("Kite token invalidate failed: %s", type(e).__name__)
            await self._clear_token()

    # ── instruments ───────────────────────────────────────────────────

    def _load_instruments(self, KiteConnect, access_token: str) -> None:
        """Blocking. Cached in memory for the IST day."""
        today = datetime.now(IST).date()
        if self._instruments_date == today and self._token_to_symbol:
            return
        kite = KiteConnect(api_key=self.api_key)
        kite.set_access_token(access_token)
        wanted = set(NIFTY_50)
        mapping: dict[int, str] = {}
        for row in kite.instruments("NSE"):
            sym = row.get("tradingsymbol")
            if sym in wanted and row.get("instrument_type") == "EQ" and row.get("segment") == "NSE":
                mapping[row["instrument_token"]] = sym
        missing = wanted - set(mapping.values())
        if missing:
            logger.warning("Kite: no NSE instrument for %d symbols: %s", len(missing), sorted(missing))
        self._token_to_symbol = mapping
        self._instruments_date = today

    # ── ticker callbacks (Twisted thread) ─────────────────────────────

    def _on_connect(self, ws, response):
        if ws is not self._ticker:
            return
        tokens = list(self._token_to_symbol)
        ws.subscribe(tokens)
        ws.set_mode(ws.MODE_QUOTE, tokens)
        self.connected = True
        logger.info("Kite ticker connected")

    def _on_ticks(self, ws, ticks):
        if ws is not self._ticker or self._loop is None:
            return
        now = self._clock()
        market_open = None
        for tick in ticks:
            symbol = self._token_to_symbol.get(tick.get("instrument_token"))
            if symbol is None:
                continue
            self.last_tick_at = time.time()
            last = self._last_pub.get(symbol)
            if last is not None and now - last < PUBLISH_INTERVAL_SECONDS:
                continue
            if market_open is None:
                market_open = is_market_open(datetime.now(IST))
            data = map_tick(tick, symbol, market_open)
            if data is None:
                continue
            self._last_pub[symbol] = now
            asyncio.run_coroutine_threadsafe(self._emit(symbol, data), self._loop)

    async def _emit(self, symbol: str, data: dict) -> None:
        try:
            await self.broadcaster.cache_price(symbol, data)
            await self.broadcaster.publish_price(symbol, data)
        except Exception as e:
            logger.warning("Failed to publish Kite tick for %s: %s", symbol, e)

    def _on_close(self, ws, code, reason):
        if ws is not self._ticker:
            return
        self.connected = False
        if _looks_like_token_error(code, reason):
            self._handle_invalid_token(ws)

    def _on_error(self, ws, code, reason):
        if ws is not self._ticker:
            return
        if _looks_like_token_error(code, reason):
            self.connected = False
            self._handle_invalid_token(ws)

    def _on_noreconnect(self, ws):
        if ws is self._ticker:
            self.connected = False

    def _handle_invalid_token(self, ws):
        """Stop the SDK's retry loop and drop the stored token."""
        logger.warning("Kite ticker rejected the access token; stopping feed")
        self._ticker = None
        try:
            _in_reactor(ws.stop_retry)
        except Exception:
            pass
        if self._loop is not None:
            asyncio.run_coroutine_threadsafe(self._clear_token(), self._loop)
