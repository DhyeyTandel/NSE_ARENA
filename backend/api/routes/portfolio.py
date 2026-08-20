# api/routes/portfolio.py
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import asyncio

from database import get_db
from db.models import User, Portfolio, Position, Season
from api.dependencies import get_current_user
from market_data.fetcher import MarketDataFetcher

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("")
async def get_portfolio(
    request: Request,
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

    # Try fetching all prices from Redis cache or yfinance in parallel off-thread
    broadcaster = request.app.state.broadcaster
    active_positions = [pos for pos in positions if pos.quantity > 0]

    async def get_price_for_ticker(ticker: str, avg_price: float):
        cached = await broadcaster.get_cached_price(ticker)
        if cached:
            return cached.get("price", avg_price)
        try:
            # Fallback to yfinance in thread pool
            price_data = await asyncio.to_thread(MarketDataFetcher.get_price, ticker)
            return price_data.get("price", avg_price)
        except Exception:
            return avg_price

    # avg_price is Decimal (the DB ledger); current_price here is always a
    # live float quote (Redis cache or yfinance) or that same avg_price as
    # a fallback. This route is pure read/display math mixed with external
    # float market data, not a source of ledger truth, so it drops to
    # float at the read boundary rather than carrying Decimal through PnL
    # arithmetic mixed with float quotes.
    prices = await asyncio.gather(*(get_price_for_ticker(pos.ticker, float(pos.avg_price)) for pos in active_positions))
    price_map = {pos.ticker: price for pos, price in zip(active_positions, prices)}

    for pos in active_positions:
        avg_price = float(pos.avg_price)
        current_price = price_map.get(pos.ticker, avg_price)
        current_value = current_price * pos.quantity
        invested_value = avg_price * pos.quantity
        pnl = current_value - invested_value
        pnl_pct = (pnl / invested_value * 100) if invested_value > 0 else 0

        total_holdings_value += current_value

        holdings.append({
            "ticker": pos.ticker,
            "quantity": pos.quantity,
            "avg_price": round(avg_price, 2),
            "current_price": round(current_price, 2),
            "current_value": round(current_value, 2),
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "state": pos.state,
            "settlement_date": pos.settlement_date,
        })

    cash_balance = float(portfolio.cash_balance)
    total_value = cash_balance + total_holdings_value
    total_return = total_value - season.starting_capital
    total_return_pct = (total_return / season.starting_capital * 100) if season.starting_capital > 0 else 0

    return {
        "cash_balance": round(cash_balance, 2),
        "holdings_value": round(total_holdings_value, 2),
        "total_value": round(total_value, 2),
        "starting_capital": season.starting_capital,
        "total_return": round(total_return, 2),
        "total_return_pct": round(total_return_pct, 2),
        "holdings": holdings,
    }
