# tests/test_price_staleness.py
"""FOLLOWUP Gap 4: trades must not execute on a stale cached price.

The Redis price cache has a 120s TTL — fine for portfolio/display, but
submit_trade previously used whatever was cached with no freshness check,
so a trade could execute on a price up to 2 minutes old. cache_price now
stamps fetched_at, and submit_trade refetches (threaded) if the cached
entry is older than STALE_PRICE_THRESHOLD_SECONDS, rejecting the trade if
that refetch also fails.
"""
import time
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
from api.routes.trades import STALE_PRICE_THRESHOLD_SECONDS

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
async def test_fresh_cached_price_used_without_refetch(client):
    app.state.broadcaster = AsyncMock()
    app.state.broadcaster.get_cached_price = AsyncMock(return_value={
        "ticker": "RELIANCE", "price": 1000.0, "previous_close": 1000.0,
        "fetched_at": time.time(),
    })

    p = _open_monday_patch()
    try:
        with patch(
            "api.routes.trades.MarketDataFetcher.get_price",
            side_effect=AssertionError("refetch should not have been called"),
        ):
            resp = await client.post("/trades", json={
                "ticker": "RELIANCE", "side": "buy", "order_type": "market", "quantity": 1,
            })
        assert resp.status_code == 200, resp.text
    finally:
        p.stop()


@pytest.mark.asyncio
async def test_stale_cached_price_triggers_refetch_and_uses_fresh_value(client):
    """A cache entry older than the staleness threshold must not be
    trusted, even though it's well within the 120s Redis TTL."""
    stale_at = time.time() - (STALE_PRICE_THRESHOLD_SECONDS + 5)
    app.state.broadcaster = AsyncMock()
    app.state.broadcaster.get_cached_price = AsyncMock(return_value={
        "ticker": "RELIANCE", "price": 500.0,  # a stale, wildly different price
        "previous_close": 1000.0,
        "fetched_at": stale_at,
    })

    p = _open_monday_patch()
    try:
        with patch(
            "api.routes.trades.MarketDataFetcher.get_price",
            return_value={"ticker": "RELIANCE", "price": 1000.0, "previous_close": 1000.0},
        ) as mock_fetch:
            resp = await client.post("/trades", json={
                "ticker": "RELIANCE", "side": "buy", "order_type": "market", "quantity": 1,
            })
        assert mock_fetch.called
        assert resp.status_code == 200, resp.text
        # Executed at the refetched (fresh) price, not the stale cached one.
        assert resp.json()["price"] == 1000.0
    finally:
        p.stop()


@pytest.mark.asyncio
async def test_stale_price_refetch_failure_rejects_trade(client):
    """If the cache is stale and the refetch also fails, reject the trade
    rather than falling back to the stale price."""
    stale_at = time.time() - (STALE_PRICE_THRESHOLD_SECONDS + 5)
    app.state.broadcaster = AsyncMock()
    app.state.broadcaster.get_cached_price = AsyncMock(return_value={
        "ticker": "RELIANCE", "price": 500.0, "previous_close": 1000.0,
        "fetched_at": stale_at,
    })

    p = _open_monday_patch()
    try:
        with patch(
            "api.routes.trades.MarketDataFetcher.get_price",
            side_effect=Exception("upstream unavailable"),
        ):
            resp = await client.post("/trades", json={
                "ticker": "RELIANCE", "side": "buy", "order_type": "market", "quantity": 1,
            })
        assert resp.status_code == 503
    finally:
        p.stop()


@pytest.mark.asyncio
async def test_missing_fetched_at_treated_as_stale(client):
    """A cache entry with no fetched_at at all (e.g. pre-upgrade data)
    must not be trusted implicitly — it should trigger a refetch just
    like a genuinely stale entry."""
    app.state.broadcaster = AsyncMock()
    app.state.broadcaster.get_cached_price = AsyncMock(return_value={
        "ticker": "RELIANCE", "price": 500.0, "previous_close": 1000.0,
        # no fetched_at key
    })

    p = _open_monday_patch()
    try:
        with patch(
            "api.routes.trades.MarketDataFetcher.get_price",
            return_value={"ticker": "RELIANCE", "price": 1000.0, "previous_close": 1000.0},
        ) as mock_fetch:
            resp = await client.post("/trades", json={
                "ticker": "RELIANCE", "side": "buy", "order_type": "market", "quantity": 1,
            })
        assert mock_fetch.called
        assert resp.status_code == 200, resp.text
    finally:
        p.stop()
