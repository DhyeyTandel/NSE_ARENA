# tests/test_circuit_breaker_reference_price.py
"""FOLLOWUP Gap 2: circuit breaker must not silently pass when the cached
price is missing previous_close. If a Redis-cached quote lacks a usable
reference price, submit_trade refetches a full quote (threaded); if that
also comes up empty, the trade is rejected with 503 rather than executing
unverified.
"""
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
import pytz
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from database import Base, get_db
from db.models import Season
from main import app

IST = pytz.timezone("Asia/Kolkata")


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
async def client(test_db):
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

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        username = f"user_{uuid.uuid4().hex[:8]}"
        resp = await c.post("/auth/register", json={
            "username": username,
            "email": f"{username}@nse-arena.com",
            "password": "password123",
        })
        assert resp.status_code == 200
        token = resp.json()["access_token"]
        c.headers["Authorization"] = f"Bearer {token}"
        yield c

    app.dependency_overrides.pop(get_db, None)


def _open_monday_patch():
    p = patch("engine.validator.datetime")
    mock_dt = p.start()
    mock_dt.now.return_value = IST.localize(datetime(2026, 3, 16, 10, 0))
    mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
    return p


@pytest.mark.asyncio
async def test_missing_previous_close_triggers_refetch_and_rejects_if_still_missing(client):
    """Cache has price but no previous_close; the threaded refetch also
    fails to produce one -> reject with 503, not a silent pass."""
    app.state.broadcaster = AsyncMock()
    app.state.broadcaster.get_cached_price = AsyncMock(return_value={
        "ticker": "RELIANCE", "price": 1000.0,  # no previous_close key
    })

    p = _open_monday_patch()
    try:
        with patch(
            "api.routes.trades.MarketDataFetcher.get_price",
            side_effect=Exception("upstream unavailable"),
        ):
            resp = await client.post("/trades", json={
                "ticker": "RELIANCE",
                "side": "buy",
                "order_type": "market",
                "quantity": 1,
            })
        assert resp.status_code == 503
        assert "reference price" in resp.json()["detail"]
    finally:
        p.stop()


@pytest.mark.asyncio
async def test_missing_previous_close_refetch_recovers_and_trade_proceeds(client):
    """Cache is missing previous_close, but the refetch succeeds -> the
    circuit breaker runs for real against the recovered value and an
    in-band trade still executes."""
    app.state.broadcaster = AsyncMock()
    app.state.broadcaster.get_cached_price = AsyncMock(return_value={
        "ticker": "RELIANCE", "price": 1000.0,
    })

    p = _open_monday_patch()
    try:
        with patch(
            "api.routes.trades.MarketDataFetcher.get_price",
            return_value={"ticker": "RELIANCE", "price": 1000.0, "previous_close": 1000.0},
        ):
            resp = await client.post("/trades", json={
                "ticker": "RELIANCE",
                "side": "buy",
                "order_type": "market",
                "quantity": 1,
            })
        assert resp.status_code == 200, resp.text
    finally:
        p.stop()


@pytest.mark.asyncio
async def test_missing_previous_close_refetch_recovers_exploit_still_blocked(client):
    """Same recovery path, but the refetched previous_close reveals the
    order is actually outside the circuit-breaker band — must still
    reject, proving this isn't just a rubber-stamp refetch."""
    app.state.broadcaster = AsyncMock()
    app.state.broadcaster.get_cached_price = AsyncMock(return_value={
        "ticker": "RELIANCE", "price": 10.0,  # looks like the 0.01-style exploit price
    })

    p = _open_monday_patch()
    try:
        with patch(
            "api.routes.trades.MarketDataFetcher.get_price",
            return_value={"ticker": "RELIANCE", "price": 10.0, "previous_close": 1000.0},
        ):
            resp = await client.post("/trades", json={
                "ticker": "RELIANCE",
                "side": "buy",
                "order_type": "market",
                "quantity": 1,
            })
        assert resp.status_code == 400
        assert "circuit breaker" in resp.json()["detail"]
    finally:
        p.stop()


@pytest.mark.asyncio
async def test_present_previous_close_skips_refetch_entirely(client):
    """When the cache already has a usable previous_close, no refetch
    should happen — patch get_price to blow up and confirm it's never hit."""
    app.state.broadcaster = AsyncMock()
    app.state.broadcaster.get_cached_price = AsyncMock(return_value={
        "ticker": "RELIANCE", "price": 1000.0, "previous_close": 1000.0,
    })

    p = _open_monday_patch()
    try:
        with patch(
            "api.routes.trades.MarketDataFetcher.get_price",
            side_effect=AssertionError("refetch should not have been called"),
        ):
            resp = await client.post("/trades", json={
                "ticker": "RELIANCE",
                "side": "buy",
                "order_type": "market",
                "quantity": 1,
            })
        assert resp.status_code == 200, resp.text
    finally:
        p.stop()
