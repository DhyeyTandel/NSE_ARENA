# api/routes/trades.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from datetime import datetime

from database import get_db
from db.models import User, Portfolio, Position, TradeRecord, Season
from api.dependencies import get_current_user
from engine.models import Order, OrderSide, OrderType
from engine.fee_engine import FeeEngine
from engine.settlement import SettlementEngine
from market_data.fetcher import MarketDataFetcher

router = APIRouter(prefix="/trades", tags=["trades"])
fee_engine = FeeEngine()
settlement_engine = SettlementEngine()


class TradeRequest(BaseModel):
    ticker: str
    side: str  # "buy" or "sell"
    order_type: str = "market"  # "market" or "limit"
    quantity: int
    limit_price: float = 0.0
    stop_loss_price: float = 0.0


@router.post("")
async def submit_trade(
    request: TradeRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Get active season and portfolio
    season_result = await db.execute(select(Season).where(Season.is_active == True))
    season = season_result.scalar_one_or_none()
    if not season:
        raise HTTPException(status_code=400, detail="No active season")

    portfolio_result = await db.execute(
        select(Portfolio).where(
            Portfolio.user_id == user.id,
            Portfolio.season_id == season.id
        )
    )
    portfolio = portfolio_result.scalar_one_or_none()
    if not portfolio:
        raise HTTPException(status_code=400, detail="No portfolio found for active season")

    # Get current price
    try:
        price_data = MarketDataFetcher.get_price(request.ticker)
        current_price = price_data["price"]
    except Exception:
        raise HTTPException(status_code=400, detail=f"Could not fetch price for {request.ticker}")

    if current_price <= 0:
        raise HTTPException(status_code=400, detail=f"Invalid price for {request.ticker}")

    execution_price = request.limit_price if request.order_type == "limit" and request.limit_price > 0 else current_price

    # Calculate fees
    fees = fee_engine.calculate(
        price=execution_price,
        quantity=request.quantity,
        side=request.side,
        trade_type="delivery"
    )

    total_cost = execution_price * request.quantity + fees.total

    # ── Bug #3 fix: calculate position_size_pct BEFORE cash changes ──
    pre_trade_portfolio_value = portfolio.cash_balance
    position_size_pct = (execution_price * request.quantity) / pre_trade_portfolio_value if pre_trade_portfolio_value > 0 else 0

    if request.side == "buy":
        # Check balance
        if total_cost > portfolio.cash_balance:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient balance. Required: ₹{total_cost:,.2f}, Available: ₹{portfolio.cash_balance:,.2f}"
            )

        # Deduct cash
        portfolio.cash_balance -= total_cost

        settlement_date = settlement_engine.calculate_settlement_date(datetime.utcnow())

        # Check for existing position (any state)
        pos_result = await db.execute(
            select(Position).where(
                Position.portfolio_id == portfolio.id,
                Position.ticker == request.ticker,
            )
        )
        existing_pos = pos_result.scalar_one_or_none()

        if existing_pos:
            # ── Bug #2 fix: average into existing position, keep its state ──
            total_qty = existing_pos.quantity + request.quantity
            existing_pos.avg_price = (
                (existing_pos.avg_price * existing_pos.quantity + execution_price * request.quantity) / total_qty
            )
            existing_pos.quantity = total_qty
            # Don't change state — if confirmed, stays confirmed (averaging in)
            # If pending, stays pending (bought more during same settlement window)
        else:
            # Create new pending position (T+1 settlement)
            new_pos = Position(
                portfolio_id=portfolio.id,
                ticker=request.ticker,
                quantity=request.quantity,
                avg_price=execution_price,
                state="pending",
                settlement_date=settlement_date,
            )
            db.add(new_pos)

    elif request.side == "sell":
        # Check holdings — only confirmed positions can be sold
        pos_result = await db.execute(
            select(Position).where(
                Position.portfolio_id == portfolio.id,
                Position.ticker == request.ticker,
                Position.state == "confirmed"
            )
        )
        existing_pos = pos_result.scalar_one_or_none()

        if not existing_pos or existing_pos.quantity < request.quantity:
            available = existing_pos.quantity if existing_pos else 0
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient shares. Available: {available}, Requested: {request.quantity}"
            )

        # Add cash (minus fees)
        sell_value = execution_price * request.quantity - fees.total
        portfolio.cash_balance += sell_value

        # Update position
        existing_pos.quantity -= request.quantity
        if existing_pos.quantity == 0:
            await db.delete(existing_pos)

    # Record trade
    trade_record = TradeRecord(
        portfolio_id=portfolio.id,
        order_id=Order().id,
        ticker=request.ticker,
        side=request.side,
        order_type=request.order_type,
        quantity=request.quantity,
        price=execution_price,
        fees=fees.total,
        settlement_date=settlement_engine.calculate_settlement_date(datetime.utcnow()),
        stop_loss_set=request.stop_loss_price > 0,
        position_size_pct=round(position_size_pct, 4),
        source="human",
    )
    db.add(trade_record)
    await db.commit()

    return {
        "status": "executed",
        "ticker": request.ticker,
        "side": request.side,
        "quantity": request.quantity,
        "price": execution_price,
        "fees": {
            "stt": fees.stt,
            "brokerage": fees.brokerage,
            "exchange_charge": fees.exchange_charge,
            "sebi_charge": fees.sebi_charge,
            "gst": fees.gst,
            "total": fees.total,
        },
        "total_cost": round(total_cost, 2),
        "remaining_balance": round(portfolio.cash_balance, 2),
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
