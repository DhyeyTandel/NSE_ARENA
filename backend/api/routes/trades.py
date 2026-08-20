# api/routes/trades.py
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field
from typing import Literal
import asyncio
import time

from database import get_db
from db.models import User, Portfolio, TradeRecord, Season
from api.dependencies import get_current_user
from market_data.fetcher import MarketDataFetcher
from services.trading import execute_validated_trade, TradeRejected

router = APIRouter(prefix="/trades", tags=["trades"])

# Execution needs a much tighter staleness bound than the 120s display
# cache TTL — a price up to 2 minutes old is fine to show, not to trade on.
STALE_PRICE_THRESHOLD_SECONDS = 15


class TradeRequest(BaseModel):
    ticker: str
    side: Literal["buy", "sell"]
    order_type: Literal["market", "limit"] = "market"
    quantity: int = Field(gt=0)
    limit_price: float = Field(default=0.0, ge=0.0)
    stop_loss_price: float = Field(default=0.0, ge=0.0)


@router.post("")
async def submit_trade(
    request: TradeRequest,
    http_request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Get active season
    season_result = await db.execute(select(Season).where(Season.is_active == True))
    season = season_result.scalar_one_or_none()
    if not season:
        raise HTTPException(status_code=400, detail="No active season")

    # Lock portfolio row for update to prevent race conditions
    portfolio_result = await db.execute(
        select(Portfolio).where(
            Portfolio.user_id == user.id,
            Portfolio.season_id == season.id
        ).with_for_update()
    )
    portfolio = portfolio_result.scalar_one_or_none()
    if not portfolio:
        raise HTTPException(status_code=400, detail="No portfolio found for active season")

    async def _refetch_quote() -> dict | None:
        try:
            fresh = await asyncio.to_thread(MarketDataFetcher.get_price, request.ticker)
            fresh["fetched_at"] = time.time()
            return fresh
        except Exception:
            return None

    # Try fetching price from Redis cache first. A cached price older
    # than STALE_PRICE_THRESHOLD_SECONDS isn't good enough to execute
    # on (120s cache TTL is fine for display, not for trading) — refetch
    # instead, and reject rather than execute on a stale price if that
    # refetch fails.
    broadcaster = http_request.app.state.broadcaster
    price_data = await broadcaster.get_cached_price(request.ticker)
    if price_data:
        age_seconds = time.time() - (price_data.get("fetched_at") or 0)
        if age_seconds > STALE_PRICE_THRESHOLD_SECONDS:
            price_data = await _refetch_quote()
    else:
        price_data = await _refetch_quote()

    if not price_data:
        raise HTTPException(status_code=503, detail=f"Could not fetch a current price for {request.ticker}")

    current_price = price_data.get("price", 0.0)
    if current_price <= 0:
        raise HTTPException(status_code=400, detail=f"Invalid price for {request.ticker}")

    # The circuit breaker needs a real previous_close — don't let a cache
    # entry missing it silently bypass the breaker. Refetch a full quote
    # instead of trusting the gap; reject the trade if even that comes up
    # empty rather than trading on an unverifiable reference price.
    previous_close = price_data.get("previous_close", 0.0) or 0.0
    if previous_close <= 0:
        fresh_quote = await _refetch_quote()
        previous_close = (fresh_quote or {}).get("previous_close", 0.0) or 0.0
        if previous_close <= 0:
            raise HTTPException(
                status_code=503,
                detail="reference price unavailable — cannot verify circuit breaker"
            )

    try:
        result = await execute_validated_trade(
            db,
            user_id=user.id,
            portfolio=portfolio,
            ticker=request.ticker,
            side=request.side,
            order_type=request.order_type,
            quantity=request.quantity,
            current_price=current_price,
            previous_close=previous_close,
            limit_price=request.limit_price,
            stop_loss_price=request.stop_loss_price,
            source="human",
        )
    except TradeRejected as e:
        raise HTTPException(status_code=400, detail=e.detail)

    await db.commit()

    return {
        "status": "executed",
        "ticker": result.ticker,
        "side": result.side,
        "quantity": result.quantity,
        "price": result.price,
        "fees": {
            "stt": result.fees.stt,
            "brokerage": result.fees.brokerage,
            "exchange_charge": result.fees.exchange_charge,
            "sebi_charge": result.fees.sebi_charge,
            "gst": result.fees.gst,
            "total": result.fees.total,
        },
        "total_cost": round(result.total_cost, 2),
        "remaining_balance": round(result.remaining_balance, 2),
    }


@router.get("")
async def get_trade_history(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    season_result = await db.execute(select(Season).where(Season.is_active == True))
    season = season_result.scalar_one_or_none()
    if not season:
        return []

    portfolio_result = await db.execute(
        select(Portfolio).where(
            Portfolio.user_id == user.id,
            Portfolio.season_id == season.id
        )
    )
    portfolio = portfolio_result.scalar_one_or_none()
    if not portfolio:
        return []

    trades_result = await db.execute(
        select(TradeRecord)
        .where(TradeRecord.portfolio_id == portfolio.id)
        .order_by(TradeRecord.created_at.desc())
    )
    trades = trades_result.scalars().all()

    return [
        {
            "id": t.id,
            "ticker": t.ticker,
            "side": t.side,
            "order_type": t.order_type,
            "quantity": t.quantity,
            "price": t.price,
            "fees": t.fees,
            "settlement_date": t.settlement_date,
            "source": t.source,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in trades
    ]
