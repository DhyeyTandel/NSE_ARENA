# main.py
import json
import logging
import asyncio
import uuid
from contextlib import asynccontextmanager
from datetime import timedelta
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
import config
from database import init_db, async_session, db_utcnow
from logging_setup import configure_logging, request_id_var
from api.routes import auth, trades, portfolio, leaderboard, websocket
from api.routes import seasons as seasons_router
from api.routes import ai as ai_router
from api.routes import scripts as scripts_router
from api.routes import kite as kite_router
from market_data.broadcaster import PriceBroadcaster, DEFAULT_TICKERS
from market_data.kite_feed import KiteFeed
from ai.scheduler import ai_scheduler

configure_logging()
logger = logging.getLogger(__name__)


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Tags every request with a correlation ID (reused from the caller's
    X-Request-ID header if present, e.g. a reverse proxy that already
    generated one) so every log line emitted while handling it — from any
    module — carries the same ID, and echoes it back in the response for
    client-side correlation."""

    async def dispatch(self, request: Request, call_next):
        req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        token = request_id_var.set(req_id)
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers["X-Request-ID"] = req_id
        return response

# Global broadcaster instance
broadcaster = PriceBroadcaster()
# Optional Kite Connect feed; inert unless KITE_API_KEY/SECRET are set.
kite_feed = KiteFeed(broadcaster, config.KITE_API_KEY, config.KITE_API_SECRET)
broadcaster.kite_feed = kite_feed


async def ensure_active_season():
    """Auto-create Season 1 if no seasons exist.

    The partial unique index on Season.is_active (db/models.py) means at
    most one worker can win this race: if another process already created
    the active season between our check and our commit, the INSERT fails
    with an IntegrityError, which we treat as "someone else already did
    this" rather than a startup failure.
    """
    from sqlalchemy import select
    from sqlalchemy.exc import IntegrityError
    from db.models import Season

    async with async_session() as db:
        result = await db.execute(select(Season).where(Season.is_active == True))
        season = result.scalar_one_or_none()

        if not season:
            season = Season(
                name="Season 1",
                start_date=db_utcnow(),
                end_date=db_utcnow() + timedelta(days=30),
                starting_capital=100000.0,
            )
            db.add(season)
            try:
                await db.commit()
                logger.info("Created Season 1 (30 days, ₹1,00,000 starting capital)")
            except IntegrityError:
                await db.rollback()
                logger.info("Active season already created by another worker")
        else:
            logger.info("Active season: %s", season.name)


AI_AGENT_USERNAME = "ai-agent"


async def ensure_ai_agent():
    """Make sure the AI agent has an account and a portfolio in the active season.

    ai/scheduler.py looks up the single User with is_ai=True and skips the
    cycle if it (or its portfolio) is missing; nothing else creates either,
    so without this the agent never trades. Idempotent, and safe against two
    workers booting together: the unique username makes the second INSERT
    fail with an IntegrityError, which we treat as "already done".
    """
    import secrets
    from sqlalchemy import select
    from sqlalchemy.exc import IntegrityError
    from api.routes.auth import pwd_context
    from db.models import Season, User, Portfolio

    async with async_session() as db:
        try:
            ai_user = (
                await db.execute(select(User).where(User.is_ai == True))
            ).scalars().first()
            if not ai_user:
                ai_user = User(
                    username=AI_AGENT_USERNAME,
                    email=f"{AI_AGENT_USERNAME}@nse-arena.local",
                    # Valid hash of a secret nobody knows: the account
                    # cannot be logged into, and login stays a clean 401.
                    hashed_password=pwd_context.hash(secrets.token_urlsafe(32)),
                    is_ai=True,
                )
                db.add(ai_user)
                await db.flush()
                logger.info("Created AI agent account '%s'", AI_AGENT_USERNAME)

            season = (
                await db.execute(select(Season).where(Season.is_active == True))
            ).scalar_one_or_none()
            if season:
                portfolio = (
                    await db.execute(
                        select(Portfolio).where(
                            Portfolio.user_id == ai_user.id,
                            Portfolio.season_id == season.id,
                        )
                    )
                ).scalar_one_or_none()
                if not portfolio:
                    db.add(Portfolio(
                        user_id=ai_user.id,
                        season_id=season.id,
                        cash_balance=season.starting_capital,
                    ))
                    logger.info("Created AI agent portfolio for %s", season.name)
            await db.commit()
        except IntegrityError:
            await db.rollback()
            logger.info("AI agent account/portfolio already created elsewhere")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    logger.info("Database initialized")
    app.state.broadcaster = broadcaster
    app.state.kite_feed = kite_feed

    # Ensure at least one season exists
    try:
        await ensure_active_season()
    except Exception as e:
        logger.warning("Could not ensure active season: %s", e)

    # Ensure the AI agent has an account + portfolio to trade with
    try:
        await ensure_ai_agent()
    except Exception as e:
        logger.warning("Could not ensure AI agent account: %s", e)

    # Start background price polling + the single shared WS fan-out task
    fanout_task = None
    try:
        redis_ok = await broadcaster.check_health()
        if redis_ok:
            await broadcaster.start_polling()
            fanout_task = await websocket.start_price_fanout(broadcaster)
            logger.info("Redis connected — live price streaming active")
            if kite_feed.configured:
                try:
                    await kite_feed.start_from_stored()
                except Exception as e:
                    logger.warning("Kite feed not started: %s", e)
        else:
            logger.warning("Redis not available — running without live prices")
    except Exception as e:
        logger.warning("Could not start price polling: %s", e)

    # Start AI agent scheduler
    try:
        await ai_scheduler.start()
    except Exception as e:
        logger.warning("Could not start AI scheduler: %s", e)

    yield

    # Shutdown
    await ai_scheduler.stop()
    if fanout_task:
        fanout_task.cancel()
        try:
            await fanout_task
        except asyncio.CancelledError:
            pass
    await kite_feed.stop(clear_token=False)
    await broadcaster.close()
    logger.info("Broadcaster and scheduler shut down")


app = FastAPI(
    title="NSE Arena",
    description="A paper trading competition platform for Indian markets with AI agents",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow frontend. Origins are env-driven (config.CORS_ORIGINS) so a
# deployed frontend origin doesn't require a code change; defaults to the
# local dev origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
)
app.add_middleware(RequestIdMiddleware)

# Mount routes
app.include_router(auth.router)
app.include_router(trades.router)
app.include_router(portfolio.router)
app.include_router(leaderboard.router)
app.include_router(websocket.router)
app.include_router(seasons_router.router)
app.include_router(ai_router.router)
app.include_router(scripts_router.router)
app.include_router(kite_router.router)
app.state.kite_feed = kite_feed


@app.get("/")
async def root():
    return {"message": "NSE Arena API", "version": "1.0.0"}


@app.get("/tickers")
async def list_tickers():
    """Tickers streamed on the live price feed."""
    return {"tickers": list(DEFAULT_TICKERS)}


@app.get("/health")
async def health_check():
    """Health check endpoint — verifies Redis connectivity"""
    redis_ok = await broadcaster.check_health()
    return {
        "status": "healthy",
        "redis": "connected" if redis_ok else "disconnected",
        "polling": broadcaster._polling_task is not None
                   and not broadcaster._polling_task.done()
                   if broadcaster._polling_task else False,
    }


PRICE_CACHE_TTL_SECONDS = 60
INTRADAY_CACHE_TTL_SECONDS = 30  # 1D/1W while the market is open
PRICE_RATE_LIMIT = 30  # requests per minute per client IP
DEFAULT_PRICE_RANGE = "1M"
# range -> (yfinance period, yfinance interval)
PRICE_RANGES = {
    "1D": ("1d", "5m"),
    "1W": ("5d", "30m"),
    "1M": ("1mo", "1d"),
    "1Y": ("1y", "1d"),
}


def _ohlcv_cache_key(ticker: str, range_: str) -> str:
    # Keyed by the yfinance period, which is 1:1 with the range, so the
    # default 1M key stays "ohlcv:<T>:1mo" (unchanged for existing callers).
    return f"ohlcv:{ticker}:{PRICE_RANGES[range_][0]}"


def _ohlcv_ttl(range_: str) -> int:
    from datetime import datetime, timezone
    from engine.market_calendar import is_market_open
    if range_ in ("1D", "1W") and is_market_open(datetime.now(timezone.utc)):
        return INTRADAY_CACHE_TTL_SECONDS
    return PRICE_CACHE_TTL_SECONDS


UNKNOWN_TICKER_TTL_SECONDS = 300


def _unknown_ticker_key(ticker: str) -> str:
    return f"unknown_ticker:{ticker}"


async def _is_known_unknown(ticker: str) -> bool:
    try:
        return await broadcaster.redis.get(_unknown_ticker_key(ticker)) in (b"1", "1")
    except Exception as e:
        logger.debug("Unknown-ticker cache read skipped for %s: %s", ticker, e)
        return False


async def _remember_unknown(ticker: str) -> None:
    try:
        await broadcaster.redis.set(
            _unknown_ticker_key(ticker), "1", ex=UNKNOWN_TICKER_TTL_SECONDS)
    except Exception as e:
        logger.debug("Unknown-ticker cache write skipped for %s: %s", ticker, e)


async def _read_ohlcv_cache(ticker: str, range_: str = DEFAULT_PRICE_RANGE):
    try:
        raw = await broadcaster.redis.get(_ohlcv_cache_key(ticker, range_))
        return json.loads(raw) if raw else None
    except Exception as e:
        logger.debug("OHLCV cache read skipped for %s: %s", ticker, e)
        return None


async def _write_ohlcv_cache(ticker: str, ohlcv: list, range_: str = DEFAULT_PRICE_RANGE) -> None:
    try:
        await broadcaster.redis.set(
            _ohlcv_cache_key(ticker, range_), json.dumps(ohlcv), ex=_ohlcv_ttl(range_))
    except Exception as e:
        logger.debug("OHLCV cache write skipped for %s: %s", ticker, e)


@app.get("/price/{ticker}")
async def get_price(ticker: str, request: Request, range: str = DEFAULT_PRICE_RANGE):
    """GET /price/{ticker}?range=1D|1W|1M|1Y — OHLCV + current price for an NSE stock.

    Public (the logged-out dashboard preview uses it), so it is validated,
    rate-limited per client IP, and the OHLCV is cached in Redis per range
    (60s; 30s for 1D/1W while the market is open)."""
    from api.rate_limit import check_rate_limit, client_ip
    from api.validation import normalize_ticker
    from market_data.fetcher import MarketDataFetcher, UnknownTickerError

    await check_rate_limit(request, bucket="price", identity=client_ip(request),
                           limit=PRICE_RATE_LIMIT, window_seconds=60)
    symbol = normalize_ticker(ticker)
    if symbol is None:
        raise HTTPException(status_code=400, detail="Invalid ticker symbol")
    if range not in PRICE_RANGES:
        raise HTTPException(status_code=400, detail="Invalid range")
    period, interval = PRICE_RANGES[range]

    if await _is_known_unknown(symbol):
        raise HTTPException(status_code=404, detail="Unknown ticker")

    try:
        live = await broadcaster.get_cached_price(symbol)
    except Exception as e:  # Redis down: fall through to yfinance
        logger.debug("Live price cache read skipped for %s: %s", symbol, e)
        live = None

    ohlcv = await _read_ohlcv_cache(symbol, range)
    try:
        if ohlcv is None and live:
            ohlcv = await asyncio.to_thread(
                MarketDataFetcher.get_ohlcv, symbol, period=period, interval=interval)
            await _write_ohlcv_cache(symbol, ohlcv, range)
        elif ohlcv is None:
            ohlcv, live = await asyncio.gather(
                asyncio.to_thread(MarketDataFetcher.get_ohlcv, symbol, period=period, interval=interval),
                asyncio.to_thread(MarketDataFetcher.get_price, symbol),
            )
            await _write_ohlcv_cache(symbol, ohlcv, range)
        elif not live:
            live = await asyncio.to_thread(MarketDataFetcher.get_price, symbol)
    except UnknownTickerError:
        # Yahoo answered but has nothing for this symbol: cache the miss so
        # repeat requests do not re-query it.
        # A listed ticker is never cached as a miss (it would be a Yahoo blip).
        if symbol not in DEFAULT_TICKERS:
            await _remember_unknown(symbol)
        raise HTTPException(status_code=404, detail="Unknown ticker")
    except Exception as e:
        # Transient upstream failure: never cached as a miss.
        logger.warning("Market data fetch failed for %s: %s", symbol, type(e).__name__)
        raise HTTPException(status_code=502, detail="Market data temporarily unavailable")

    return {"ticker": symbol, "current": live, "ohlcv": ohlcv, "range": range, "interval": interval}


@app.get("/score/{user_id}")
async def get_trader_score(user_id: int):
    """GET /score/{user_id} — get trader score"""
    from sqlalchemy import select
    from database import async_session
    from db.models import TraderScore

    async with async_session() as db:
        result = await db.execute(
            select(TraderScore)
            .where(TraderScore.user_id == user_id)
            .order_by(TraderScore.calculated_at.desc())
        )
        score = result.scalar_one_or_none()

        if not score:
            return {
                "user_id": user_id,
                "final_score": 300,
                "grade": "Beginner",
                "breakdown": {
                    "returns_score": 0,
                    "risk_score": 0,
                    "consistency_score": 0,
                    "discipline_score": 0,
                }
            }

        return {
            "user_id": user_id,
            "final_score": score.final_score,
            "grade": score.grade,
            "breakdown": {
                "returns_score": score.returns_score,
                "risk_score": score.risk_score,
                "consistency_score": score.consistency_score,
                "discipline_score": score.discipline_score,
            }
        }
