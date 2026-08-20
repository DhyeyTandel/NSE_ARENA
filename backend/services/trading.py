# services/trading.py
"""Shared, validated trade-execution logic.

Extracted from api/routes/trades.py so the human /trades endpoint and the
AI agent's order execution (ai/execution.py) both run the exact same
validation and mutation path — same Validator checks (circuit breaker,
market hours, balance/shares), same atomic guarded-UPDATE cash/position
mutation, same TradeRecord bookkeeping. Neither caller can accidentally
diverge from the other's guarantees.

This module intentionally does NOT resolve prices or lock the portfolio
row — callers differ too much there (the HTTP route has a Redis-cached
quote with staleness handling; the AI agent already has a fresh quote from
its market-data watchlist fetch). Callers are responsible for: resolving
current_price/previous_close, locking the portfolio row with
with_for_update(), and commit/rollback.
"""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Portfolio, Position, TradeRecord
from engine.fee_engine import FeeBreakdown, FeeEngine
from engine.models import Order, OrderSide, OrderType
from engine.settlement import SettlementEngine
from engine.validator import (
    CircuitBreakerError,
    InsufficientBalanceError,
    InsufficientSharesError,
    MarketClosedError,
    Validator,
)

fee_engine = FeeEngine()
settlement_engine = SettlementEngine()


class TradeRejected(Exception):
    """A trade failed validation or couldn't be filled (balance, shares,
    circuit breaker, market hours, bad limit price). Callers map this to
    whatever error surface makes sense for them (HTTP 400, a blocked AI
    decision, etc) — this module has no opinion on that."""

    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(detail)


def _to_decimal(value) -> Decimal:
    """Coerce a float/int/str/Decimal into a Decimal via its string form —
    never Decimal(float) directly, which would bake in the float's own
    binary-representation error."""
    return value if isinstance(value, Decimal) else Decimal(str(value))


@dataclass
class TradeResult:
    ticker: str
    side: str
    order_type: str
    quantity: int
    price: Decimal
    fees: FeeBreakdown
    total_cost: Decimal
    remaining_balance: Decimal


async def execute_validated_trade(
    db: AsyncSession,
    *,
    user_id,
    portfolio: Portfolio,
    ticker: str,
    side: str,
    order_type: str,
    quantity: int,
    current_price: float,
    previous_close: float,
    limit_price: float = 0.0,
    stop_loss_price: float = 0.0,
    source: str = "human",
) -> TradeResult:
    """Validate and execute one trade against `portfolio`: runs the same
    Validator checks the human trade path runs, fills at current_price
    (never at limit_price — see the limit-order comment below), mutates
    cash/position, and adds a TradeRecord to `db` (not committed — the
    caller commits alongside whatever else is in its transaction).

    Raises TradeRejected on any validation or fill failure. Caller's
    portfolio row must already be locked with with_for_update().
    """
    # Callers hand in plain floats (a Pydantic request body, a yfinance
    # quote dict) — this is the boundary where money enters Decimal space
    # and stays there for the rest of this function.
    current_price = _to_decimal(current_price)
    previous_close = _to_decimal(previous_close)
    limit_price = _to_decimal(limit_price)
    stop_loss_price = _to_decimal(stop_loss_price)

    if order_type == "limit" and limit_price <= 0:
        raise TradeRejected("Limit price must be greater than zero for limit orders")

    engine_order = Order(
        user_id=str(user_id),
        ticker=ticker,
        side=OrderSide.BUY if side == "buy" else OrderSide.SELL,
        order_type=OrderType.LIMIT if order_type == "limit" else OrderType.MARKET,
        quantity=quantity,
        limit_price=limit_price if order_type == "limit" else Decimal("0"),
    )

    pos_holdings_result = await db.execute(
        select(Position).where(
            Position.portfolio_id == portfolio.id,
            Position.state == "confirmed",
        )
    )
    holdings = {pos.ticker: pos.quantity for pos in pos_holdings_result.scalars().all()}

    validator = Validator()
    try:
        validator.validate(
            order=engine_order,
            balance=portfolio.cash_balance,
            holdings=holdings,
            previous_close=previous_close,
            market_price=current_price,
            strict=True,
        )
    except (MarketClosedError, CircuitBreakerError, InsufficientBalanceError, InsufficientSharesError) as e:
        raise TradeRejected(str(e))

    # Determine fill price. Resting orders aren't supported: a limit order
    # either fills immediately at the current market price (if the limit
    # would be satisfied) or is rejected outright — it never fills at the
    # user-specified limit_price itself, which would let orders buy below
    # (or sell above) market inside the circuit-breaker band.
    if order_type == "limit":
        if side == "buy" and limit_price < current_price:
            raise TradeRejected("limit price below market — order would not fill")
        if side == "sell" and limit_price > current_price:
            raise TradeRejected("limit price above market — order would not fill")
    execution_price = current_price

    fees = fee_engine.calculate(
        price=execution_price,
        quantity=quantity,
        side=side,
        trade_type="delivery",
    )
    total_cost = execution_price * quantity + fees.total

    # position_size_pct is a ratio, not a stored money amount — TradeRecord
    # stores it as a plain Float column, so drop out of Decimal here.
    pre_trade_portfolio_value = portfolio.cash_balance
    position_size_pct = (
        float((execution_price * quantity) / pre_trade_portfolio_value)
        if pre_trade_portfolio_value > 0 else 0.0
    )

    if side == "buy":
        # Guarded UPDATE backstop: with_for_update() is a silent no-op on
        # SQLite, so this conditional UPDATE is the only thing that actually
        # prevents overdraw there. rowcount == 0 means another concurrent
        # trade already spent the balance this order needed.
        debit_result = await db.execute(
            update(Portfolio)
            .where(Portfolio.id == portfolio.id, Portfolio.cash_balance >= total_cost)
            .values(cash_balance=Portfolio.cash_balance - total_cost)
            .execution_options(synchronize_session=False)
        )
        if debit_result.rowcount == 0:
            raise TradeRejected(
                f"Insufficient balance. Required: ₹{total_cost:,.2f}, Available: ₹{portfolio.cash_balance:,.2f}"
            )
        portfolio.cash_balance -= total_cost

        settlement_date = settlement_engine.calculate_settlement_date(datetime.utcnow())

        # Check for existing position with lock to prevent TOCTOU
        pos_result = await db.execute(
            select(Position).where(
                Position.portfolio_id == portfolio.id,
                Position.ticker == ticker,
            ).with_for_update()
        )
        existing_pos = pos_result.scalar_one_or_none()

        if existing_pos:
            total_qty = existing_pos.quantity + quantity
            existing_pos.avg_price = (
                (existing_pos.avg_price * existing_pos.quantity + execution_price * quantity) / total_qty
            )
            existing_pos.quantity = total_qty
        else:
            db.add(Position(
                portfolio_id=portfolio.id,
                ticker=ticker,
                quantity=quantity,
                avg_price=execution_price,
                state="pending",
                settlement_date=settlement_date,
            ))

    elif side == "sell":
        # Lock target position to prevent concurrent sells exceeding holdings
        pos_result = await db.execute(
            select(Position).where(
                Position.portfolio_id == portfolio.id,
                Position.ticker == ticker,
                Position.state == "confirmed",
            ).with_for_update()
        )
        existing_pos = pos_result.scalar_one_or_none()

        if not existing_pos or existing_pos.quantity < quantity:
            available = existing_pos.quantity if existing_pos else 0
            raise TradeRejected(
                f"Insufficient shares. Available: {available}, Requested: {quantity}"
            )

        # Guarded UPDATE backstop, same reasoning as the buy-side debit above.
        debit_result = await db.execute(
            update(Position)
            .where(Position.id == existing_pos.id, Position.quantity >= quantity)
            .values(quantity=Position.quantity - quantity)
            .execution_options(synchronize_session=False)
        )
        if debit_result.rowcount == 0:
            raise TradeRejected(
                f"Insufficient shares. Available: {existing_pos.quantity}, Requested: {quantity}"
            )

        sell_value = execution_price * quantity - fees.total
        portfolio.cash_balance += sell_value

        existing_pos.quantity -= quantity
        if existing_pos.quantity == 0:
            await db.delete(existing_pos)

    trade_record = TradeRecord(
        portfolio_id=portfolio.id,
        order_id=Order().id,
        ticker=ticker,
        side=side,
        order_type=order_type,
        quantity=quantity,
        price=execution_price,
        fees=fees.total,
        settlement_date=settlement_engine.calculate_settlement_date(datetime.utcnow()),
        stop_loss_set=stop_loss_price > 0,
        position_size_pct=round(position_size_pct, 4),
        source=source,
    )
    db.add(trade_record)

    return TradeResult(
        ticker=ticker,
        side=side,
        order_type=order_type,
        quantity=quantity,
        price=execution_price,
        fees=fees,
        total_cost=total_cost,
        remaining_balance=portfolio.cash_balance,
    )
