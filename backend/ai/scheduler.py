# ai/scheduler.py
"""
AI Agent Scheduler — runs the AI trading bot on a cron schedule
during Indian market hours (9:15 AM – 3:30 PM IST, Mon–Fri).
"""
import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config import GROQ_API_KEY

logger = logging.getLogger(__name__)

# Watchlist of tickers the AI agent monitors
AI_WATCHLIST = [
    "RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK",
    "ITC", "SBIN", "BHARTIARTL", "KOTAKBANK", "LT",
]


class AIScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self._started = False

    async def start(self):
        """Start the AI agent scheduler if Groq API key is configured"""
        if not GROQ_API_KEY:
            logger.warning(
                "GROQ_API_KEY not set — AI agent scheduler disabled. "
                "Set the key in backend/.env to enable AI trading."
            )
            return

        # Run every 30 minutes during market hours: 9:15–15:30 IST (Mon–Fri)
        # UTC offset: IST is UTC+5:30, so 9:15 IST = 3:45 UTC, 15:30 IST = 10:00 UTC
        trigger = CronTrigger(
            day_of_week="mon-fri",
            hour="3-9",          # UTC hours covering 9:15–15:30 IST
            minute="15,45",      # Every 30 minutes
            timezone="Asia/Kolkata",
        )

        # Override with IST-based cron for clarity
        trigger = CronTrigger(
            day_of_week="mon-fri",
            hour="9-15",
            minute="15,45",
            timezone="Asia/Kolkata",
        )

        self.scheduler.add_job(
            self._run_ai_cycle,
            trigger=trigger,
            id="ai_trading_cycle",
            name="AI Trading Cycle",
            replace_existing=True,
        )

        self.scheduler.start()
        self._started = True
        logger.info("AI agent scheduler started — runs every 30 min during market hours (IST)")

    async def stop(self):
        """Gracefully shut down the scheduler"""
        if self._started:
            self.scheduler.shutdown(wait=False)
            self._started = False
            logger.info("AI agent scheduler stopped")

    async def _run_ai_cycle(self):
        """Execute one AI trading cycle"""
        from sqlalchemy import select
        from database import async_session, db_utcnow
        from db.models import User, Portfolio, Position, Season, AIDecision
        from market_data.fetcher import MarketDataFetcher
        from ai.agent import AIAgent
        from ai.execution import AIOrderExecutionService
        from ai.risk_memory import AIRiskMemory
        from ai.guardrails import STOP_LOSS_PCT, find_stop_loss_breaches, pct_label
        from engine.models import Order, OrderSide, OrderType
        from services.trading import TradeRejected

        logger.info("AI cycle starting...")

        try:
            async with async_session() as db:
                # Get the AI user
                result = await db.execute(
                    select(User).where(User.is_ai == True)
                )
                ai_user = result.scalar_one_or_none()

                if not ai_user:
                    logger.info("No AI user found — skipping cycle")
                    return

                # Get active season
                result = await db.execute(
                    select(Season).where(Season.is_active == True)
                )
                season = result.scalar_one_or_none()
                if not season:
                    logger.info("No active season — skipping cycle")
                    return

                # Get portfolio
                result = await db.execute(
                    select(Portfolio).where(
                        Portfolio.user_id == ai_user.id,
                        Portfolio.season_id == season.id,
                    )
                )
                portfolio = result.scalar_one_or_none()
                if not portfolio:
                    logger.info("No portfolio for AI user — skipping cycle")
                    return

                # Get positions
                result = await db.execute(
                    select(Position).where(
                        Position.portfolio_id == portfolio.id
                    )
                )
                positions = result.scalars().all()

                now = db_utcnow()
                days_remaining = max(0, (season.end_date - now).days)

                # Fetch market data for watchlist
                market_data = {}
                for ticker in AI_WATCHLIST:
                    try:
                        price = await asyncio.to_thread(MarketDataFetcher.get_price, ticker)
                        market_data[ticker] = price
                    except Exception:
                        pass

                if not market_data:
                    logger.warning("Could not fetch any market data - skipping cycle")
                    return

                order_engine = AIOrderExecutionService(ai_user.id)

                # Deterministic stop loss, independent of the model: sell in
                # full any holding down more than STOP_LOSS_PCT from its
                # average price, through the same validated trade path the
                # agent uses. Holdings with no usable quote are left alone.
                breaches = find_stop_loss_breaches(
                    [
                        {"ticker": p.ticker, "quantity": p.quantity, "avg_price": float(p.avg_price)}
                        for p in positions
                    ],
                    market_data,
                )
                for b in breaches:
                    reason = (
                        f"Stop loss triggered: {b['ticker']} down {b['loss_pct']:.1%} from "
                        f"average price ₹{b['avg_price']:,.2f} (now ₹{b['price']:,.2f}); "
                        f"limit is {pct_label(STOP_LOSS_PCT)}. Sold {b['quantity']} shares."
                    )
                    row = AIDecision(
                        action="sell", ticker=b["ticker"], quantity=b["quantity"],
                        reasoning=reason, confidence=1.0,
                        guardrail_status="approved",
                    )
                    try:
                        await order_engine.submit(
                            Order(
                                user_id="ai_agent", ticker=b["ticker"], side=OrderSide.SELL,
                                order_type=OrderType.MARKET, quantity=b["quantity"],
                                source="ai_agent",
                            ),
                            market_data,
                        )
                    except TradeRejected as e:
                        # e.g. shares still pending T+1 settlement, or market closed
                        row = AIDecision(
                            action="blocked", ticker=b["ticker"], quantity=b["quantity"],
                            reasoning=f"Stop loss triggered for {b['ticker']} "
                                      f"(down {b['loss_pct']:.1%}) but the sell was rejected.",
                            guardrail_status="blocked", guardrail_reason=str(e),
                        )
                        logger.warning("Stop loss sell rejected for %s: %s", b["ticker"], e)
                    except Exception:
                        logger.error("Stop loss sell failed for %s", b["ticker"], exc_info=True)
                        await db.rollback()
                        continue
                    db.add(row)
                    await db.commit()

                if breaches:
                    # Execution used its own session; reload so the agent
                    # sees post-sale cash and positions.
                    await db.refresh(portfolio)
                    result = await db.execute(
                        select(Position)
                        .where(Position.portfolio_id == portfolio.id)
                        .execution_options(populate_existing=True)
                    )
                    positions = result.scalars().all()

                # Build portfolio dict for the AI agent.
                # cash_balance/avg_price are Decimal (the DB ledger); this
                # dict is prompt/display/ratio input for the AI, not a
                # source of truth for stored money, so it drops to float
                # here rather than carrying Decimal into ratio arithmetic
                # (agent.py's drawdown calc) mixed with Season.starting_capital,
                # which stays float (not a money field we migrated).
                # current_value marks holdings to market (cost basis where
                # there is no usable quote) so the position cap and the
                # drawdown kill switch see real portfolio value.
                def _mark(p):
                    price = market_data.get(p.ticker, {}).get("price")
                    try:
                        price = float(price)
                    except (TypeError, ValueError):
                        price = 0.0
                    return price if price > 0 and price == price and price != float("inf") else float(p.avg_price)

                portfolio_data = {
                    "starting_capital": season.starting_capital,
                    "current_value": float(portfolio.cash_balance) + sum(
                        _mark(p) * p.quantity for p in positions
                    ),
                    "cash_balance": float(portfolio.cash_balance),
                    "days_remaining": days_remaining,
                    "positions": [
                        {
                            "ticker": p.ticker,
                            "quantity": p.quantity,
                            "avg_price": float(p.avg_price),
                        }
                        for p in positions
                    ],
                }

                # Rehydrate risk memory from persisted history instead of
                # starting fresh every cycle — AIAgent is reconstructed here
                # each run, so without this format_for_prompt() would report
                # "No previous decisions recorded" on essentially every cycle.
                risk_memory = AIRiskMemory()
                past_result = await db.execute(
                    select(AIDecision).order_by(AIDecision.created_at.desc()).limit(50)
                )
                for past in reversed(past_result.scalars().all()):
                    if past.guardrail_status == "blocked":
                        risk_memory.record_violation(
                            {"action": past.action, "ticker": past.ticker},
                            past.guardrail_reason or "",
                            timestamp=past.created_at,
                        )
                    else:
                        risk_memory.record_decision({
                            "action": past.action,
                            "ticker": past.ticker,
                            "quantity": past.quantity or 0,
                            "reasoning": past.reasoning or "",
                            "confidence": past.confidence or 0.0,
                        }, timestamp=past.created_at)

                # Run AI agent
                agent = AIAgent(portfolio_data, order_engine=order_engine, risk_memory=risk_memory)
                decision = await agent.run_cycle(market_data)

                # Record the decision
                ai_decision = AIDecision(
                    action=decision.get("action", "hold"),
                    ticker=decision.get("ticker"),
                    quantity=decision.get("quantity"),
                    reasoning=decision.get("reasoning") or decision.get("reason"),
                    confidence=decision.get("confidence"),
                    stop_loss_price=decision.get("stop_loss_price"),
                    position_size_pct=decision.get("position_size_pct"),
                    guardrail_status="blocked" if decision.get("action") == "blocked" else "approved",
                    guardrail_reason=decision.get("reason") if decision.get("action") == "blocked" else None,
                )
                db.add(ai_decision)
                await db.commit()

                logger.info(
                    "AI cycle complete: action=%s ticker=%s confidence=%s",
                    decision.get("action"),
                    decision.get("ticker", "—"),
                    decision.get("confidence", "—"),
                )

        except Exception as e:
            logger.error("AI cycle failed: %s", e, exc_info=True)


# Singleton instance
ai_scheduler = AIScheduler()
