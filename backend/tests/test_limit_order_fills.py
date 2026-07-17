# tests/test_limit_order_fills.py
"""Item 1 (ANTIGRAVITY_NEXT.md): limit-order fill semantics.

A limit order must never fill at the user's own limit_price — it either
fills at the current market price (if the limit would be satisfied) or is
rejected outright. This closes the fake-profit exploit where a limit buy
placed inside the +-10% circuit-breaker band but below market price filled
instantly at the user's chosen price.
"""
import time
import uuid
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from unittest.mock import AsyncMock

from sqlalchemy import select

from database import Base, get_db
from db.models import Season, User, Portfolio, Position
from main import app

MOCK_PRICE = {"ticker": "RELIANCE", "price": 1000.0, "previous_close": 1000.0}


@pytest_asyncio.fixture
async def test_db():
    # Function-scoped (not module-scoped): pytest-asyncio gives each test
    # function its own event loop by default, and a static-pooled in-memory
    # SQLite connection created in one test's loop misbehaves when reused
    # from another test's loop. One engine per test keeps everything on a
    # single event loop.
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as db:
        season = Season(
            name="Season 1",
            start_date=datetime.utcnow() - timedelta(days=1),
            end_date=datetime.utcnow() + timedelta(days=30),
            starting_capital=100000.0,
            is_active=True,
        )
        db.add(season)
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


async def _give_confirmed_position(test_db, username, ticker, quantity, avg_price):
    """Directly seed a confirmed, sellable position for the test user."""
    async with test_db() as session:
        user = (await session.execute(select(User).where(User.username == username))).scalar_one()
        portfolio = (await session.execute(
            select(Portfolio).where(Portfolio.user_id == user.id)
        )).scalar_one()
        session.add(Position(
            portfolio_id=portfolio.id,
            ticker=ticker,
            quantity=quantity,
            avg_price=avg_price,
            state="confirmed",
        ))
        await session.commit()


def _open_monday_patch():
    """Patch validator's market-hours clock to a normal trading window."""
    from unittest.mock import patch
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
async def test_limit_buy_below_market_rejected(client_and_token):
    client, token, _username = client_and_token
    headers = {"Authorization": f"Bearer {token}"}
    p = _open_monday_patch()
    try:
        # 9% below market (1000), inside the +-10% circuit-breaker band.
        resp = await client.post("/trades", headers=headers, json={
            "ticker": "RELIANCE",
            "side": "buy",
            "order_type": "limit",
            "quantity": 10,
            "limit_price": 910.0,
        })
        assert resp.status_code == 400
        assert "would not fill" in resp.json()["detail"]
    finally:
        p.stop()


@pytest.mark.asyncio
async def test_limit_buy_above_market_fills_at_market(client_and_token):
    client, token, _username = client_and_token
    headers = {"Authorization": f"Bearer {token}"}
    p = _open_monday_patch()
    try:
        resp = await client.post("/trades", headers=headers, json={
            "ticker": "RELIANCE",
            "side": "buy",
            "order_type": "limit",
            "quantity": 10,
            "limit_price": 1050.0,
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["price"] == MOCK_PRICE["price"]
    finally:
        p.stop()


@pytest.mark.asyncio
async def test_limit_buy_equal_to_market_fills(client_and_token):
    client, token, _username = client_and_token
    headers = {"Authorization": f"Bearer {token}"}
    p = _open_monday_patch()
    try:
        resp = await client.post("/trades", headers=headers, json={
            "ticker": "RELIANCE",
            "side": "buy",
            "order_type": "limit",
            "quantity": 5,
            "limit_price": 1000.0,
        })
        assert resp.status_code == 200
        assert resp.json()["price"] == MOCK_PRICE["price"]
    finally:
        p.stop()


@pytest.mark.asyncio
async def test_limit_sell_above_market_rejected(test_db, client_and_token):
    client, token, username = client_and_token
    headers = {"Authorization": f"Bearer {token}"}
    # Seed a confirmed, sellable position directly (positions bought via the
    # API settle T+1 and aren't sellable immediately).
    await _give_confirmed_position(test_db, username, "RELIANCE", 20, 900.0)
    p = _open_monday_patch()
    try:
        resp = await client.post("/trades", headers=headers, json={
            "ticker": "RELIANCE",
            "side": "sell",
            "order_type": "limit",
            "quantity": 10,
            "limit_price": 1100.0,
        })
        assert resp.status_code == 400
        assert "would not fill" in resp.json()["detail"]
    finally:
        p.stop()


@pytest.mark.asyncio
async def test_no_trade_executes_at_price_other_than_market(client_and_token):
    """Every successful fill must execute at exactly the current market price."""
    client, token, _username = client_and_token
    headers = {"Authorization": f"Bearer {token}"}
    p = _open_monday_patch()
    try:
        for order_type, limit_price in [("market", 0.0), ("limit", 1000.0), ("limit", 1080.0)]:
            resp = await client.post("/trades", headers=headers, json={
                "ticker": "RELIANCE",
                "side": "buy",
                "order_type": order_type,
                "quantity": 1,
                "limit_price": limit_price,
            })
            assert resp.status_code == 200, resp.text
            assert resp.json()["price"] == MOCK_PRICE["price"]
    finally:
        p.stop()
