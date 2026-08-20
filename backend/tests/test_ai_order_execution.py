# tests/test_ai_order_execution.py
"""P0 audit fix: ai/scheduler.py used to hardcode
AIAgent(portfolio_data, order_engine=None). There is no OrderEngine class
anywhere, so any guardrail-approved decision hit
self.order_engine.submit(...) on None -> AttributeError, which was outside
the agent's own try/except and got swallowed by scheduler.py's broad
`except Exception` -- the AI could never place a real trade, and it failed
silently (no AIDecision row was even written for that cycle).

This drives AIScheduler._run_ai_cycle() end-to-end -- the exact path
production uses -- with only Gemini and the yfinance-backed price fetcher
mocked, and asserts a guardrail-approved decision actually lands: cash and
position move, and an AIDecision row is written.
"""
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
import pytest_asyncio
import pytz
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

import ai.execution as execution_module
from ai.scheduler import AIScheduler
from database import Base
from db.models import AIDecision, Portfolio, Position, Season, TradeRecord, User

IST = pytz.timezone("Asia/Kolkata")
MOCK_PRICE = {"price": 1000.0, "previous_close": 1000.0}


@pytest_asyncio.fixture
async def test_db():
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_maker() as db:
        season = Season(
            name="Season 1",
            start_date=datetime.utcnow() - timedelta(days=1),
            end_date=datetime.utcnow() + timedelta(days=30),
            starting_capital=100000.0,
            is_active=True,
        )
        db.add(season)
        await db.flush()

        ai_user = User(
            username="ai_trader", email="ai_trader@nse-arena.com",
            hashed_password="x", is_ai=True,
        )
        db.add(ai_user)
        await db.flush()

        db.add(Portfolio(user_id=ai_user.id, season_id=season.id, cash_balance=100000.0))
        await db.commit()
        ai_user_id = ai_user.id

    yield session_maker, ai_user_id

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


def _open_monday_patch():
    open_monday = IST.localize(datetime(2026, 3, 16, 10, 0))
    p = patch("engine.validator.datetime")
    mock_dt = p.start()
    mock_dt.now.return_value = open_monday
    mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
    return p


def _mock_gemini_response(action: str):
    class FakeResponse:
        text = (
            '{"action": "%s", "ticker": "RELIANCE", "quantity": 5, '
            '"stop_loss_price": 900.0, "position_size_pct": 0.05, '
            '"reasoning": "test cycle", "confidence": 0.8}' % action
        )

    async def fake_generate(*args, **kwargs):
        return FakeResponse()

    return fake_generate


@pytest.mark.asyncio
async def test_approved_buy_decision_executes_a_real_trade(test_db, monkeypatch):
    session_maker, ai_user_id = test_db
    # scheduler.py does `from database import async_session` inside the
    # method body, so patching the attribute on the database module is
    # picked up at call time. ai/execution.py imports it at module load
    # time, so that binding needs patching directly too.
    monkeypatch.setattr("database.async_session", session_maker)
    monkeypatch.setattr(execution_module, "async_session", session_maker)
    monkeypatch.setattr(
        "market_data.fetcher.MarketDataFetcher.get_price",
        lambda ticker: {"ticker": ticker, **MOCK_PRICE},
    )
    monkeypatch.setattr(
        "google.generativeai.GenerativeModel.generate_content_async",
        _mock_gemini_response("buy"),
    )

    p = _open_monday_patch()
    try:
        scheduler = AIScheduler()
        await scheduler._run_ai_cycle()
    finally:
        p.stop()

    async with session_maker() as check_db:
        portfolio = (await check_db.execute(
            select(Portfolio).where(Portfolio.user_id == ai_user_id)
        )).scalar_one()
        assert portfolio.cash_balance < 100000.0, "AI buy must debit cash"

        position = (await check_db.execute(
            select(Position).where(
                Position.portfolio_id == portfolio.id, Position.ticker == "RELIANCE"
            )
        )).scalar_one()
        assert position.quantity == 5

        trade = (await check_db.execute(
            select(TradeRecord).where(TradeRecord.portfolio_id == portfolio.id)
        )).scalar_one()
        assert trade.side == "buy"
        assert trade.source == "ai_agent"

        decision_row = (await check_db.execute(select(AIDecision))).scalar_one()
        assert decision_row.action == "buy"
        assert decision_row.guardrail_status == "approved"


@pytest.mark.asyncio
async def test_hold_decision_writes_no_trade(test_db, monkeypatch):
    """Sanity check: a "hold" decision must not touch the order engine at
    all, and still gets its AIDecision row written."""
    session_maker, ai_user_id = test_db
    monkeypatch.setattr("database.async_session", session_maker)
    monkeypatch.setattr(execution_module, "async_session", session_maker)
    monkeypatch.setattr(
        "market_data.fetcher.MarketDataFetcher.get_price",
        lambda ticker: {"ticker": ticker, **MOCK_PRICE},
    )
    monkeypatch.setattr(
        "google.generativeai.GenerativeModel.generate_content_async",
        _mock_gemini_response("hold"),
    )

    p = _open_monday_patch()
    try:
        scheduler = AIScheduler()
        await scheduler._run_ai_cycle()
    finally:
        p.stop()

    async with session_maker() as check_db:
        portfolio = (await check_db.execute(
            select(Portfolio).where(Portfolio.user_id == ai_user_id)
        )).scalar_one()
        assert portfolio.cash_balance == 100000.0

        trades = (await check_db.execute(select(TradeRecord))).scalars().all()
        assert trades == []

        decision_row = (await check_db.execute(select(AIDecision))).scalar_one()
        assert decision_row.action == "hold"
