# tests/test_ai_rule_enforcement.py
"""The AI account's stated rules (stop loss, per-ticker position cap) are
enforced in code, independent of what the model returns."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import pytest_asyncio
import pytz
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

import ai.execution as execution_module
from ai.guardrails import (
    MAX_POSITION_PCT, STOP_LOSS_PCT, RiskGuardrail, find_stop_loss_breaches,
)
from ai.prompts import RESPONSE_FORMAT, SYSTEM_PROMPT
from ai.scheduler import AIScheduler
from database import Base
from db.models import AIDecision, Portfolio, Position, Season, TradeRecord, User

IST = pytz.timezone("Asia/Kolkata")
guardrail = RiskGuardrail()


# ---- pure functions -------------------------------------------------------

def test_constants_are_in_the_prompt():
    assert "20%" in SYSTEM_PROMPT and "0.20" in RESPONSE_FORMAT
    assert (MAX_POSITION_PCT, STOP_LOSS_PCT) == (0.20, 0.08)


def test_breach_detected_past_threshold_only():
    pos = [{"ticker": "A", "quantity": 10, "avg_price": 100.0},
           {"ticker": "B", "quantity": 10, "avg_price": 100.0}]
    md = {"A": {"price": 91.0}, "B": {"price": 93.0}}  # -9% vs -7%
    out = find_stop_loss_breaches(pos, md)
    assert [b["ticker"] for b in out] == ["A"]


@pytest.mark.parametrize("quote", [None, {}, {"price": None}, {"price": 0},
                                   {"price": float("nan")}, {"price": "abc"}, {"price": -5}])
def test_missing_or_bad_price_means_no_breach(quote):
    pos = [{"ticker": "A", "quantity": 10, "avg_price": 100.0}]
    md = {} if quote is None else {"A": quote}
    assert find_stop_loss_breaches(pos, md) == []


def _pf(positions, value=100000.0):
    return {"current_value": value, "positions": positions}


def test_cap_trims_buy():
    # holds 100 @1000 = 100k... use 100k portfolio: cap 20k, holds 10 -> 10k, room 10k
    d = {"action": "buy", "ticker": "X", "quantity": 15}
    qty, note = guardrail.cap_buy_quantity(
        d, _pf([{"ticker": "X", "quantity": 10, "avg_price": 1000.0}]), {"X": {"price": 1000.0}})
    assert qty == 10 and "reduced" in note


def test_cap_blocks_when_full():
    d = {"action": "buy", "ticker": "X", "quantity": 1}
    qty, note = guardrail.cap_buy_quantity(
        d, _pf([{"ticker": "X", "quantity": 20, "avg_price": 1000.0}]), {"X": {"price": 1000.0}})
    assert qty == 0 and "skipped" in note


def test_cap_leaves_fitting_buy_alone_and_ignores_other_tickers():
    d = {"action": "buy", "ticker": "X", "quantity": 5}
    qty, note = guardrail.cap_buy_quantity(
        d, _pf([{"ticker": "Y", "quantity": 99, "avg_price": 1.0}]), {"X": {"price": 1000.0}})
    assert (qty, note) == (5, "")


def test_cap_no_price_blocks():
    d = {"action": "buy", "ticker": "X", "quantity": 5}
    qty, _ = guardrail.cap_buy_quantity(d, _pf([]), {})
    assert qty == 0


# ---- end to end through the scheduler ------------------------------------

@pytest_asyncio.fixture
async def env():
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    sm = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with sm() as db:
        season = Season(
            name="S", start_date=datetime.now(timezone.utc) - timedelta(days=1),
            end_date=datetime.now(timezone.utc) + timedelta(days=30),
            starting_capital=100000.0, is_active=True)
        db.add(season)
        await db.flush()
        u = User(username="ai", email="ai@x.com", hashed_password="x", is_ai=True)
        db.add(u)
        await db.flush()
        db.add(Portfolio(user_id=u.id, season_id=season.id, cash_balance=80000.0))
        await db.commit()
        uid = u.id
    yield sm, uid
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


async def _add_position(sm, uid, ticker, qty, avg, state="confirmed"):
    async with sm() as db:
        pf = (await db.execute(select(Portfolio).where(Portfolio.user_id == uid))).scalar_one()
        db.add(Position(portfolio_id=pf.id, ticker=ticker, quantity=qty,
                        avg_price=avg, state=state))
        await db.commit()


def _groq(payload: str):
    async def fake(*a, **k):
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=payload))])
    return fake


def _buy_json(qty):
    return ('{"action": "buy", "ticker": "RELIANCE", "quantity": %d, '
            '"stop_loss_price": 900.0, "position_size_pct": 0.05, '
            '"reasoning": "r", "confidence": 0.8}' % qty)

HOLD = '{"action": "hold", "reasoning": "r", "confidence": 0.5}'


async def _run(monkeypatch, sm, price_fn, groq_payload):
    monkeypatch.setattr("database.async_session", sm)
    monkeypatch.setattr(execution_module, "async_session", sm)
    monkeypatch.setattr("market_data.fetcher.MarketDataFetcher.get_price", price_fn)
    monkeypatch.setattr("groq.resources.chat.completions.AsyncCompletions.create", _groq(groq_payload))
    monday = IST.localize(datetime(2026, 3, 16, 10, 0))
    p = patch("engine.validator.datetime")
    m = p.start()
    m.now.return_value = monday
    m.side_effect = lambda *a, **kw: datetime(*a, **kw)
    try:
        await AIScheduler()._run_ai_cycle()
    finally:
        p.stop()


def _price(price, only=None):
    def f(ticker):
        if only and ticker != only:
            raise RuntimeError("no quote")
        return {"ticker": ticker, "price": price, "previous_close": price}
    return f


@pytest.mark.asyncio
async def test_stop_loss_sells_position_even_if_model_holds(env, monkeypatch):
    sm, uid = env
    await _add_position(sm, uid, "RELIANCE", 10, 1000.0)
    await _run(monkeypatch, sm, _price(900.0), HOLD)  # -10%
    async with sm() as db:
        assert (await db.execute(select(Position))).scalars().all() == []
        t = (await db.execute(select(TradeRecord))).scalar_one()
        assert (t.side, t.quantity, t.source) == ("sell", 10, "ai_agent")
        rows = (await db.execute(select(AIDecision).order_by(AIDecision.id))).scalars().all()
        assert rows[0].action == "sell" and "Stop loss triggered" in rows[0].reasoning
        assert rows[-1].action == "hold"


@pytest.mark.asyncio
async def test_no_stop_loss_within_threshold(env, monkeypatch):
    sm, uid = env
    await _add_position(sm, uid, "RELIANCE", 10, 1000.0)
    await _run(monkeypatch, sm, _price(950.0), HOLD)  # -5%
    async with sm() as db:
        assert (await db.execute(select(Position))).scalar_one().quantity == 10
        assert (await db.execute(select(TradeRecord))).scalars().all() == []


@pytest.mark.asyncio
async def test_stop_loss_skipped_when_price_missing(env, monkeypatch):
    sm, uid = env
    await _add_position(sm, uid, "RELIANCE", 10, 1000.0)
    # only TCS has a quote; RELIANCE (down or not) has none -> no forced action, no crash
    await _run(monkeypatch, sm, _price(500.0, only="TCS"), HOLD)
    async with sm() as db:
        assert (await db.execute(select(Position))).scalar_one().quantity == 10
        assert (await db.execute(select(TradeRecord))).scalars().all() == []
        assert (await db.execute(select(AIDecision))).scalar_one().action == "hold"


@pytest.mark.asyncio
async def test_stop_loss_on_pending_position_is_logged_not_crashed(env, monkeypatch):
    """T+1: unsettled shares cannot be sold; the rejection is recorded."""
    sm, uid = env
    await _add_position(sm, uid, "RELIANCE", 10, 1000.0, state="pending")
    await _run(monkeypatch, sm, _price(900.0), HOLD)
    async with sm() as db:
        assert (await db.execute(select(Position))).scalar_one().quantity == 10
        rows = (await db.execute(select(AIDecision).order_by(AIDecision.id))).scalars().all()
        assert rows[0].action == "blocked" and "Stop loss triggered" in rows[0].reasoning


@pytest.mark.asyncio
async def test_cap_trims_repeated_buy(env, monkeypatch):
    sm, uid = env
    # Total value 90k (80k cash + 10 @ 1000), cap 18k, so room for 8 more.
    await _add_position(sm, uid, "RELIANCE", 10, 1000.0)
    await _run(monkeypatch, sm, _price(1000.0), _buy_json(15))  
    async with sm() as db:
        pos = (await db.execute(select(Position).where(Position.ticker == "RELIANCE"))).scalar_one()
        total = 80000.0 + 10 * 1000.0
        assert pos.quantity * 1000.0 <= MAX_POSITION_PCT * total + 1e-6
        assert pos.quantity == 18  # 15 requested, trimmed to the 8 that fit


@pytest.mark.asyncio
async def test_cap_blocks_when_position_full(env, monkeypatch):
    sm, uid = env
    await _add_position(sm, uid, "RELIANCE", 20, 1000.0)  # 20k of 100k
    await _run(monkeypatch, sm, _price(1000.0), _buy_json(5))
    async with sm() as db:
        assert (await db.execute(select(Position))).scalar_one().quantity == 20
        assert (await db.execute(select(TradeRecord))).scalars().all() == []
        row = (await db.execute(select(AIDecision))).scalar_one()
        assert row.action == "blocked" and "Position cap" in row.guardrail_reason
