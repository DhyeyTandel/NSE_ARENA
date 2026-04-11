# api/routes/portfolio.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db
from db.models import User, Portfolio, Position, Season
from api.dependencies import get_current_user
from market_data.fetcher import MarketDataFetcher

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("")
async def get_portfolio(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Get active season
    season_result = await db.execute(select(Season).where(Season.is_active == True))
    season = season_result.scalar_one_or_none()
    if not season:
        raise HTTPException(status_code=400, detail="No active season")

    # Get portfolio
    portfolio_result = await db.execute(
        select(Portfolio).where(
            Portfolio.user_id == user.id,
            Portfolio.season_id == season.id
        )
    )
    portfolio = portfolio_result.scalar_one_or_none()
    if not portfolio:
        raise HTTPException(status_code=400, detail="No portfolio found")

    # Get positions
    positions_result = await db.execute(
        select(Position).where(Position.portfolio_id == portfolio.id)
    )
    positions = positions_result.scalars().all()

    # Calculate current values
    holdings = []
    total_holdings_value = 0.0

    for pos in positions:
        if pos.quantity <= 0:
            continue
        try:
            price_data = MarketDataFetcher.get_price(pos.ticker)
            current_price = price_data["price"]
        except Exception:
            current_price = pos.avg_price

        current_value = current_price * pos.quantity
        invested_value = pos.avg_price * pos.quantity
        pnl = current_value - invested_value
        pnl_pct = (pnl / invested_value * 100) if invested_value > 0 else 0

        total_holdings_value += current_value

        holdings.append({
            "ticker": pos.ticker,
            "quantity": pos.quantity,
            "avg_price": round(pos.avg_price, 2),
            "current_price": round(current_price, 2),
            "current_value": round(current_value, 2),
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "state": pos.state,
            "settlement_date": pos.settlement_date,
        })

    total_value = portfolio.cash_balance + total_holdings_value
    total_return = total_value - season.starting_capital
    total_return_pct = (total_return / season.starting_capital * 100) if season.starting_capital > 0 else 0

    return {
        "cash_balance": round(portfolio.cash_balance, 2),
        "holdings_value": round(total_holdings_value, 2),
        "total_value": round(total_value, 2),
        "starting_capital": season.starting_capital,
        "total_return": round(total_return, 2),
        "total_return_pct": round(total_return_pct, 2),
        "holdings": holdings,
    }
