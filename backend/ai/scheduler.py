# ai/scheduler.py
"""
AI Agent Scheduler — runs the AI trading bot on a cron schedule
during Indian market hours (9:15 AM – 3:30 PM IST, Mon–Fri).
"""
import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config import GEMINI_API_KEY

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
        """Start the AI agent scheduler if Gemini API key is configured"""
        if not GEMINI_API_KEY:
            logger.warning(
                "GEMINI_API_KEY not set — AI agent scheduler disabled. "
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
        from database import async_session
        from db.models import User, Portfolio, Position, Season, AIDecision
        from market_data.fetcher import MarketDataFetcher
        from ai.agent import AIAgent

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

                # Build portfolio dict for the AI agent
                now = datetime.utcnow()
                days_remaining = max(0, (season.end_date - now).days)

                portfolio_data = {
                    "starting_capital": season.starting_capital,
                    "current_value": portfolio.cash_balance + sum(
                        p.avg_price * p.quantity for p in positions
                    ),
                    "cash_balance": portfolio.cash_balance,
                    "days_remaining": days_remaining,
                    "positions": [
                        {
                            "ticker": p.ticker,
                            "quantity": p.quantity,
                            "avg_price": p.avg_price,
                        }
                        for p in positions
                    ],
                }

                # Fetch market data for watchlist
                market_data = {}
                for ticker in AI_WATCHLIST:
                    try:
                        price = MarketDataFetcher.get_price(ticker)
                        market_data[ticker] = price
                    except Exception:
                        pass

                if not market_data:
                    logger.warning("Could not fetch any market data — skipping cycle")
                    return

                # Run AI agent
                agent = AIAgent(portfolio_data, order_engine=None)
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
