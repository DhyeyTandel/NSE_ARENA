# tests/test_money_decimal.py
"""P1 audit fix: money fields (Portfolio.cash_balance, Position.avg_price,
TradeRecord.price/fees, DailyPortfolioValue.total_value) are now
Numeric/Decimal end-to-end instead of Float, closing the classic
trading-platform "cent-level drift from float arithmetic" risk.

These tests exercise the full HTTP path (not just the unit-level
fee_engine/validator tests) to catch the class of bug this migration
actually introduced during development: routes that mix a Decimal DB
field with a live float market quote (api/routes/portfolio.py,
api/routes/leaderboard.py) raising TypeError instead of computing PnL.
"""
import time
import uuid
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from unittest.mock import AsyncMock, patch

from database import Base, get_db
from db.models import Portfolio, Season, TradeRecord
from main import app

MOCK_PRICE = {"ticker": "RELIANCE", "price": 1000.0, "previous_close": 1000.0}


@pytest_asyncio.fixture
async def test_db():
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as db:
        db.add(Season(
            name="Season 1",
            start_date=datetime.utcnow() - timedelta(days=1),
            end_date=datetime.utcnow() + timedelta(days=30),
            starting_capital=100000.0,
            is_active=True,
        ))
        await db.commit()

    yield async_session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def client_and_token(test_db):
    async def override_get_db():
        async with test_db() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    app.dependency_overrides[get_db] = override_get_db

    app.state.broadcaster = AsyncMock()
    app.state.broadcaster.get_cached_price = AsyncMock(
        return_value={**MOCK_PRICE, "fetched_at": time.time()}
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        username = f"user_{uuid.uuid4().hex[:8]}"
        resp = await client.post("/auth/register", json={
            "username": username,
            "email": f"{username}@nse-arena.com",
            "password": "password123",
        })
        assert resp.status_code == 200
        token = resp.json()["access_token"]
        yield client, token, username

    app.dependency_overrides.pop(get_db, None)


def _open_monday_patch():
    from datetime import datetime as real_datetime
    import pytz

    IST = pytz.timezone("Asia/Kolkata")
    open_monday = IST.localize(real_datetime(2026, 3, 16, 10, 0))

    p = patch("engine.validator.datetime")
    mock_dt = p.start()
    mock_dt.now.return_value = open_monday
    mock_dt.side_effect = lambda *a, **kw: real_datetime(*a, **kw)
    return p


@pytest.mark.asyncio
async def test_portfolio_and_leaderboard_after_a_buy(test_db, client_and_token):
    """A buy leaves cash_balance/avg_price stored as Decimal; both
    /portfolio and /leaderboard must still compute PnL against a live
    float quote without raising, and return correct numbers."""
    client, token, username = client_and_token
    headers = {"Authorization": f"Bearer {token}"}

    p = _open_monday_patch()
    try:
        resp = await client.post("/trades", headers=headers, json={
            "ticker": "RELIANCE", "side": "buy", "order_type": "market", "quantity": 10,
        })
        assert resp.status_code == 200, resp.text

        portfolio_resp = await client.get("/portfolio", headers=headers)
        assert portfolio_resp.status_code == 200, portfolio_resp.text
        body = portfolio_resp.json()
        assert body["cash_balance"] < 100000.0
        assert len(body["holdings"]) == 1
        assert body["holdings"][0]["avg_price"] == 1000.0
        assert body["holdings"][0]["current_value"] == 10000.0

        leaderboard_resp = await client.get("/leaderboard")
        assert leaderboard_resp.status_code == 200, leaderboard_resp.text
        entries = leaderboard_resp.json()
        assert len(entries) == 1
        assert entries[0]["username"] == username
        assert entries[0]["total_value"] < 100000.0
    finally:
        p.stop()


@pytest.mark.asyncio
async def test_cash_balance_and_trade_fields_are_stored_as_decimal(test_db, client_and_token):
    client, token, username = client_and_token
    headers = {"Authorization": f"Bearer {token}"}

    p = _open_monday_patch()
    try:
        resp = await client.post("/trades", headers=headers, json={
            "ticker": "RELIANCE", "side": "buy", "order_type": "market", "quantity": 10,
        })
        assert resp.status_code == 200, resp.text
    finally:
        p.stop()

    async with test_db() as session:
        portfolio = (await session.execute(select(Portfolio))).scalar_one()
        assert isinstance(portfolio.cash_balance, Decimal)

        trade = (await session.execute(select(TradeRecord))).scalar_one()
        assert isinstance(trade.price, Decimal)
        assert isinstance(trade.fees, Decimal)
        assert trade.price == Decimal("1000.00")
