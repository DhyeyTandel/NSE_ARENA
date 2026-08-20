# tests/test_rate_limiting.py
"""Item 5 (ANTIGRAVITY_NEXT.md): Redis-backed rate limiting.

/api/scripts/run, /auth/login (+ /auth/login/json), and /auth/register had
no rate limiting at all — wide open to brute-force/enumeration and
unbounded script execution. Uses a small in-memory fake standing in for
the Redis client (AsyncMock's default children aren't awaitable, so the
rate limiter's fail-open path would silently no-op against a bare
AsyncMock and never actually exercise the 429 path).
"""
import time
import uuid
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from unittest.mock import AsyncMock

from database import Base, get_db
from db.models import Season
from main import app


class FakeRedis:
    """Minimal async fake matching the subset of redis.asyncio.Redis used
    by api/rate_limit.py: INCR + EXPIRE against an in-memory dict."""

    def __init__(self):
        self._counts: dict[str, int] = {}

    async def incr(self, key: str) -> int:
        self._counts[key] = self._counts.get(key, 0) + 1
        return self._counts[key]

    async def expire(self, key: str, seconds: int) -> None:
        pass


@pytest_asyncio.fixture
async def test_db():
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
    app.state.broadcaster = AsyncMock()
    app.state.broadcaster.redis = FakeRedis()
    app.state.broadcaster.get_cached_price = AsyncMock(return_value=None)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_login_rate_limited_after_5_per_minute(client):
    # Wrong password every time — we only care about the rate limiter
    # firing before the 401s would otherwise just keep coming.
    statuses = []
    for _ in range(6):
        resp = await client.post("/auth/login/json", json={
            "username": "nobody",
            "password": "wrong",
        })
        statuses.append(resp.status_code)

    assert statuses[:5] == [401] * 5
    assert statuses[5] == 429


@pytest.mark.asyncio
async def test_login_and_login_json_share_one_rate_limit_bucket(client):
    """An attacker shouldn't be able to dodge the limit by switching
    between /auth/login and /auth/login/json."""
    for _ in range(5):
        resp = await client.post("/auth/login/json", json={
            "username": "nobody", "password": "wrong",
        })
        assert resp.status_code == 401

    resp = await client.post(
        "/auth/login",
        data={"username": "nobody", "password": "wrong"},
    )
    assert resp.status_code == 429


@pytest.mark.asyncio
async def test_register_rate_limited_after_3_per_hour(client):
    statuses = []
    for _ in range(4):
        username = f"user_{uuid.uuid4().hex[:8]}"
        resp = await client.post("/auth/register", json={
            "username": username,
            "email": f"{username}@nse-arena.com",
            "password": "password123",
        })
        statuses.append(resp.status_code)

    assert statuses[:3] == [200, 200, 200]
    assert statuses[3] == 429


@pytest.mark.asyncio
async def test_trades_rate_limited_after_20_per_minute(client, monkeypatch):
    """P1 audit fix: POST /trades was the one financial-mutation endpoint
    with no rate limit at all, and each cache miss also triggers a real
    upstream yfinance call. Mock the price fetch to fail fast and
    deterministically (a 503, unrelated to the rate limiter) so every
    request past the limiter behaves the same regardless of real-world
    weekday/market-hours at test-run time."""
    monkeypatch.setattr(
        "market_data.fetcher.MarketDataFetcher.get_price",
        lambda ticker: (_ for _ in ()).throw(Exception("upstream unavailable")),
    )

    username = f"user_{uuid.uuid4().hex[:8]}"
    resp = await client.post("/auth/register", json={
        "username": username,
        "email": f"{username}@nse-arena.com",
        "password": "password123",
    })
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    statuses = []
    for _ in range(21):
        resp = await client.post("/trades", headers=headers, json={
            "ticker": "RELIANCE", "side": "buy", "order_type": "market", "quantity": 1,
        })
        statuses.append(resp.status_code)

    assert statuses[:20] == [503] * 20
    assert statuses[20] == 429


@pytest.mark.asyncio
async def test_scripts_run_rate_limited_after_10_per_minute(client):
    username = f"user_{uuid.uuid4().hex[:8]}"
    resp = await client.post("/auth/register", json={
        "username": username,
        "email": f"{username}@nse-arena.com",
        "password": "password123",
    })
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    statuses = []
    for _ in range(11):
        resp = await client.post("/api/scripts/run", headers=headers, json={
            "code": "",  # empty code -> fast 400, we only care about the 429
            "ticker": "RELIANCE",
        })
        statuses.append(resp.status_code)

    assert statuses[:10] == [400] * 10
    assert statuses[10] == 429
