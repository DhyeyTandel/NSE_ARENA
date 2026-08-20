# tests/test_script_error_leak.py
"""P2 audit fix: POST /api/scripts/run returned raw Python exception text
(f"Script execution error: {str(e)}") directly to the client on script
failure — internal error details (paths, internals) leaking straight into
an HTTP response. It must now return a generic message while still
logging the real exception server-side.
"""
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from database import Base, get_db
from db.models import Season
from main import app

SENSITIVE_DETAIL = "Traceback: /internal/secret/path/engine.py line 42, db password rotated"


@pytest_asyncio.fixture
async def client():
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_maker() as db:
        db.add(Season(
            name="Season 1",
            start_date=datetime.utcnow() - timedelta(days=1),
            end_date=datetime.utcnow() + timedelta(days=30),
            starting_capital=100000.0,
            is_active=True,
        ))
        await db.commit()

    async def override_get_db():
        async with session_maker() as session:
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

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    app.dependency_overrides.pop(get_db, None)
    await engine.dispose()


@pytest.mark.asyncio
async def test_script_execution_error_does_not_leak_exception_text(client, monkeypatch):
    monkeypatch.setattr(
        "market_data.fetcher.MarketDataFetcher.get_ohlcv",
        lambda ticker, period: [
            {"time": 1710000000, "open": 10.0, "high": 12.0, "low": 9.0, "close": 11.0, "volume": 100},
        ],
    )

    def _raise(*args, **kwargs):
        raise RuntimeError(SENSITIVE_DETAIL)

    monkeypatch.setattr("api.routes.scripts.run_script", _raise)

    username = f"user_{uuid.uuid4().hex[:8]}"
    resp = await client.post("/auth/register", json={
        "username": username,
        "email": f"{username}@nse-arena.com",
        "password": "password123",
    })
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post("/api/scripts/run", headers=headers, json={
        "code": "plot(close)",
        "ticker": "RELIANCE",
    })

    assert resp.status_code == 500
    assert SENSITIVE_DETAIL not in resp.text
    assert resp.json()["detail"] == "Script execution failed — check your script for errors."
