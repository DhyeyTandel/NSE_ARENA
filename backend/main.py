# main.py
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import init_db, async_session
from api.routes import auth, trades, portfolio, leaderboard, websocket
from api.routes import seasons as seasons_router
from api.routes import ai as ai_router
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
    """Auto-create Season 1 if no seasons exist"""
    from sqlalchemy import select
    from db.models import Season

    async with async_session() as db:
        result = await db.execute(select(Season).where(Season.is_active == True))
        season = result.scalar_one_or_none()

        if not season:
            season = Season(
                name="Season 1",
                start_date=datetime.utcnow(),
                end_date=datetime.utcnow() + timedelta(days=30),
                starting_capital=100000.0,
            )
            db.add(season)
            await db.commit()
            logger.info("Created Season 1 (30 days, ₹1,00,000 starting capital)")
        else:
            logger.info("Active season: %s", season.name)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    logger.info("Database initialized")

    # Ensure at least one season exists
    try:
        await ensure_active_season()
    except Exception as e:
        logger.warning("Could not ensure active season: %s", e)

    # Start background price polling
    try:
        redis_ok = await broadcaster.check_health()
        if redis_ok:
            await broadcaster.start_polling()
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
    await broadcaster.close()
    logger.info("Broadcaster and scheduler shut down")


app = FastAPI(
    title="NSE Arena",
    description="A paper trading competition platform for Indian markets with AI agents",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routes
app.include_router(auth.router)
app.include_router(trades.router)
app.include_router(portfolio.router)
app.include_router(leaderboard.router)
app.include_router(websocket.router)
app.include_router(seasons_router.router)
app.include_router(ai_router.router)


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
        ohlcv = MarketDataFetcher.get_ohlcv(ticker, period="1mo")
        return {
            "ticker": ticker,
            "current": cached,
            "ohlcv": ohlcv,
        }

    from market_data.fetcher import MarketDataFetcher
    ohlcv = MarketDataFetcher.get_ohlcv(ticker, period="1mo")
    price = MarketDataFetcher.get_price(ticker)
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
