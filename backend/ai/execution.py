# ai/execution.py
"""Order execution backend for AIAgent (agent.py's `order_engine`).

Before this existed, ai/scheduler.py constructed AIAgent(portfolio_data,
order_engine=None) — any guardrail-approved decision hit
`self.order_engine.submit(...)` on None, raised an AttributeError outside
the agent's own try/except, and was swallowed by scheduler.py's broad
`except Exception`. The AI could never place a real trade, and it failed
silently: no AIDecision row was even written for that cycle.

This routes an approved decision through the exact same validated trade
path api/routes/trades.py uses (services.trading.execute_validated_trade)
rather than the unwired engine/matching.py order book — same Validator
checks, same atomic guarded-UPDATE cash/position mutation, same
TradeRecord bookkeeping the human path gets.
"""
import logging

from sqlalchemy import select

from database import async_session
from db.models import Portfolio, Season
from engine.models import Order
from services.trading import TradeRejected, execute_validated_trade

logger = logging.getLogger(__name__)


class AIOrderExecutionService:
    """order_engine implementation for AIAgent. Resolves the AI user's
    active portfolio and routes the order through the shared, validated
    trade service in its own DB transaction."""

    def __init__(self, ai_user_id: int):
        self.ai_user_id = ai_user_id

    async def submit(self, order: Order, market_data: dict):
        """Execute `order` at the current price for its ticker, looked up
        in `market_data` (the same watchlist quotes the scheduler already
        fetched for this cycle). Raises TradeRejected if there's no quote
        for the ticker or the trade fails validation/fill."""
        quote = market_data.get(order.ticker)
        current_price = (quote or {}).get("price") or 0.0
        if current_price <= 0:
            raise TradeRejected(f"no market data available for {order.ticker}")
        previous_close = (quote or {}).get("previous_close") or 0.0

        async with async_session() as db:
            season_result = await db.execute(select(Season).where(Season.is_active == True))
            season = season_result.scalar_one_or_none()
            if not season:
                raise TradeRejected("no active season")

            portfolio_result = await db.execute(
                select(Portfolio).where(
                    Portfolio.user_id == self.ai_user_id,
                    Portfolio.season_id == season.id,
                ).with_for_update()
            )
            portfolio = portfolio_result.scalar_one_or_none()
            if not portfolio:
                raise TradeRejected("no portfolio for AI user")

            result = await execute_validated_trade(
                db,
                user_id=self.ai_user_id,
                portfolio=portfolio,
                ticker=order.ticker,
                side=order.side.value,
                order_type=order.order_type.value,
                quantity=order.quantity,
                current_price=current_price,
                previous_close=previous_close,
                limit_price=order.limit_price,
                source="ai_agent",
            )
            await db.commit()
            logger.info(
                "AI order executed: %s %s x%s @ %.2f",
                result.side, result.ticker, result.quantity, result.price,
            )
            return result
