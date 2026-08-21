# main.py
import logging
import asyncio
from contextlib import asynccontextmanager
from datetime import timedelta
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import config
from database import init_db, async_session, db_utcnow
from api.routes import auth, trades, portfolio, leaderboard, websocket
from api.routes import seasons as seasons_router
from api.routes import ai as ai_router
from api.routes import scripts as scripts_router
from market_data.broadcaster import PriceBroadcaster
from ai.scheduler import ai_scheduler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Global broadcaster instance
broadcaster = PriceBroadcaster()


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


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    logger.info("Database initialized")
    app.state.broadcaster = broadcaster

    # Ensure at least one season exists
    try:
        await ensure_active_season()
    except Exception as e:
        logger.warning("Could not ensure active season: %s", e)

    # Start background price polling + the single shared WS fan-out task
    fanout_task = None
    try:
        redis_ok = await broadcaster.check_health()
        if redis_ok:
            await broadcaster.start_polling()
            fanout_task = await websocket.start_price_fanout(broadcaster)
            logger.info("Redis connected — live price streaming active")
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

# Mount routes
app.include_router(auth.router)
app.include_router(trades.router)
app.include_router(portfolio.router)
app.include_router(leaderboard.router)
app.include_router(websocket.router)
app.include_router(seasons_router.router)
app.include_router(ai_router.router)
app.include_router(scripts_router.router)


@app.get("/")
async def root():
    return {"message": "NSE Arena API", "version": "1.0.0"}


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


@app.get("/price/{ticker}")
async def get_price(ticker: str):
    """GET /price/{ticker} — fetches OHLCV data using yfinance for Indian NSE stocks"""
    # Try Redis cache first
    cached = await broadcaster.get_cached_price(ticker)
    if cached:
        from market_data.fetcher import MarketDataFetcher
        ohlcv = await asyncio.to_thread(MarketDataFetcher.get_ohlcv, ticker, period="1mo")
        return {
            "ticker": ticker,
            "current": cached,
            "ohlcv": ohlcv,
        }

    from market_data.fetcher import MarketDataFetcher
    ohlcv, price = await asyncio.gather(
        asyncio.to_thread(MarketDataFetcher.get_ohlcv, ticker, period="1mo"),
        asyncio.to_thread(MarketDataFetcher.get_price, ticker)
    )
    return {
        "ticker": ticker,
        "current": price,
        "ohlcv": ohlcv,
    }


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
