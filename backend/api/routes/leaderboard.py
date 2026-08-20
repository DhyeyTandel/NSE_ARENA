# api/routes/leaderboard.py
import asyncio

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db
from db.models import User, Portfolio, Position, Season, TraderScore
from market_data.fetcher import MarketDataFetcher

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])


async def _price_or_fallback(broadcaster, ticker: str, fallback: float) -> float:
    cached = await broadcaster.get_cached_price(ticker)
    if cached:
        return cached.get("price", fallback)
    try:
        price_data = await asyncio.to_thread(MarketDataFetcher.get_price, ticker)
        return price_data.get("price", fallback)
    except Exception:
        return fallback


@router.get("")
async def get_leaderboard(request: Request, db: AsyncSession = Depends(get_db)):
    # Get active season
    season_result = await db.execute(select(Season).where(Season.is_active == True))
    season = season_result.scalar_one_or_none()
    if not season:
        return []

    # Get all portfolios for this season
    portfolios_result = await db.execute(
        select(Portfolio, User)
        .join(User, Portfolio.user_id == User.id)
        .where(Portfolio.season_id == season.id)
    )
    portfolios = portfolios_result.all()

    leaderboard = []
    for portfolio, user in portfolios:
        # Get positions
        positions_result = await db.execute(
            select(Position).where(Position.portfolio_id == portfolio.id)
        )
        positions = positions_result.scalars().all()

        # Calculate total value (cache-first, threaded fallback — never a
        # blocking yfinance call on the event loop)
        # avg_price/cash_balance are Decimal (the DB ledger); this route
        # mixes them with live float market quotes for a read-only ranking
        # computation, so it drops to float at the read boundary — same
        # reasoning as api/routes/portfolio.py.
        broadcaster = request.app.state.broadcaster
        holdings_value = 0.0
        for pos in positions:
            if pos.quantity <= 0:
                continue
            price = await _price_or_fallback(broadcaster, pos.ticker, float(pos.avg_price))
            holdings_value += price * pos.quantity

        total_value = float(portfolio.cash_balance) + holdings_value
        total_return_pct = ((total_value - season.starting_capital) / season.starting_capital * 100)

        # Get trader score
        score_result = await db.execute(
            select(TraderScore)
            .where(TraderScore.user_id == user.id, TraderScore.season_id == season.id)
            .order_by(TraderScore.calculated_at.desc())
        )
        score = score_result.scalar_one_or_none()

        initials = user.username[:2].upper()

        leaderboard.append({
            "user_id": user.id,
            "username": user.username,
            "initials": initials,
            "is_ai": user.is_ai,
            "total_value": round(total_value, 2),
            "total_return_pct": round(total_return_pct, 2),
            "trader_score": score.final_score if score else 300,
            "grade": score.grade if score else "Beginner",
            "max_drawdown": 0.0,  # Calculated from daily values
        })

    # Sort by total value descending
    leaderboard.sort(key=lambda x: x["total_value"], reverse=True)

    # Add rank
    for i, entry in enumerate(leaderboard):
        entry["rank"] = i + 1

    return leaderboard
