# api/routes/leaderboard.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db
from db.models import User, Portfolio, Position, Season, TraderScore
from market_data.fetcher import MarketDataFetcher

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])


@router.get("")
async def get_leaderboard(db: AsyncSession = Depends(get_db)):
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

        # Calculate total value
        holdings_value = 0.0
        for pos in positions:
            if pos.quantity <= 0:
                continue
            try:
                price_data = MarketDataFetcher.get_price(pos.ticker)
                holdings_value += price_data["price"] * pos.quantity
            except Exception:
                holdings_value += pos.avg_price * pos.quantity

        total_value = portfolio.cash_balance + holdings_value
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
