# tests/test_readiness_fixes.py
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from database import Base, get_db
from db.models import User, Season, Portfolio, Position
from datetime import datetime, timedelta
import os
import time
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock
from main import app
from engine.validator import Validator
from engine.models import Order, OrderSide
from scripting.engine import PineEngine
import pytest_asyncio
import pytz

IST = pytz.timezone("Asia/Kolkata")

@pytest_asyncio.fixture(scope="module")
async def test_db():
    # Override config database URL to in-memory SQLite
    import config
    original_db_url = config.DATABASE_URL
    config.DATABASE_URL = "sqlite+aiosqlite://"

    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    # Ensure there is an active season created exactly once
    async with async_session() as db:
        season = Season(
            name="Season 1",
            start_date=datetime.utcnow() - timedelta(days=1),
            end_date=datetime.utcnow() + timedelta(days=30),
            starting_capital=100000.0,
            is_active=True
        )
        db.add(season)
        await db.commit()

    yield async_session
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
    config.DATABASE_URL = original_db_url


@pytest_asyncio.fixture
async def client_and_token(test_db):
    # Override get_db dependency
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
    
    # Mock app.state.broadcaster for the test environment
    app.state.broadcaster = AsyncMock()
    app.state.broadcaster.get_cached_price = AsyncMock(return_value=None)
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Register user (which automatically creates a portfolio for the active season)
        import uuid
        username = f"user_{uuid.uuid4().hex[:8]}"
        resp = await client.post("/auth/register", json={
            "username": username,
            "email": f"{username}@nse-arena.com",
            "password": "password123"
        })
        assert resp.status_code == 200
        token = resp.json()["access_token"]
        yield client, token
        
    app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_negative_quantity_rejected(client_and_token):
    """POST /trades with quantity <= 0 should be rejected by Pydantic."""
    client, token = client_and_token
    headers = {"Authorization": f"Bearer {token}"}
    
    resp = await client.post("/trades", headers=headers, json={
        "ticker": "RELIANCE",
        "side": "buy",
        "order_type": "market",
        "quantity": -10,
    })
    # Pydantic validation returns 422 for Field(gt=0)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_limit_far_below_market_rejected(client_and_token):
    """Limit buy order far below market price should be rejected by the circuit breaker."""
    client, token = client_and_token
    headers = {"Authorization": f"Bearer {token}"}

    # Mock market hours to be open (Monday 10:00 AM IST)
    open_monday = IST.localize(datetime(2026, 3, 16, 10, 0))
    
    mock_price_data = {
        "ticker": "RELIANCE",
        "price": 1000.0,
        "previous_close": 1000.0,
    }

    with patch("engine.validator.datetime") as mock_dt, \
         patch("market_data.broadcaster.PriceBroadcaster.get_cached_price", new_callable=AsyncMock, return_value=mock_price_data):
        mock_dt.now.return_value = open_monday
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        
        # Limit buy at ₹10 (far below ₹900 circuit limit)
        resp = await client.post("/trades", headers=headers, json={
            "ticker": "RELIANCE",
            "side": "buy",
            "order_type": "limit",
            "quantity": 10,
            "limit_price": 10.0
        })
        assert resp.status_code == 400
        assert "circuit breaker" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_trade_rejected_outside_market_hours(client_and_token):
    """POST /trades outside market hours should be rejected."""
    client, token = client_and_token
    headers = {"Authorization": f"Bearer {token}"}

    # Sunday 10:00 AM IST (weekend)
    weekend_time = IST.localize(datetime(2026, 3, 15, 10, 0))
    
    mock_price_data = {
        "ticker": "RELIANCE",
        "price": 1000.0,
        "previous_close": 1000.0,
    }

    with patch("engine.validator.datetime") as mock_dt, \
         patch("market_data.broadcaster.PriceBroadcaster.get_cached_price", new_callable=AsyncMock, return_value=mock_price_data):
        mock_dt.now.return_value = weekend_time
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        
        resp = await client.post("/trades", headers=headers, json={
            "ticker": "RELIANCE",
            "side": "buy",
            "order_type": "market",
            "quantity": 10,
        })
        assert resp.status_code == 400
        assert "Market is closed" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_script_run_requires_auth(fastapi_app):
    """POST /api/scripts/run without bearer token should be rejected with 401."""
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/scripts/run", json={
            "code": "plot(close)",
            "ticker": "RELIANCE"
        })
    assert resp.status_code == 401


def test_script_timeout_aborts_engine():
    """PineEngine should abort execution if it runs for too long (CPU timeout)."""
    ohlcv = [{"open": 10.0, "high": 12.0, "low": 9.0, "close": 11.0, "volume": 100}]
    timestamps = [1710000000]
    
    engine = PineEngine(ohlcv, timestamps)
    # Simulate start time 10 seconds in the past to trigger timeout instantly
    engine.start_time = time.perf_counter() - 10.0
    
    with pytest.raises(TimeoutError, match="timed out"):
        engine.execute("plot(close)")
