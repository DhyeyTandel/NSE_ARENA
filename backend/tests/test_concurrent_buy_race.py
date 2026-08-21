# tests/test_concurrent_buy_race.py
"""Item 2 (ANTIGRAVITY_NEXT.md): dialect-agnostic guarded UPDATE backstop.

`.with_for_update()` is a silent no-op on SQLite, so the TOCTOU race on
Portfolio.cash_balance is only actually closed by the guarded conditional
UPDATE in trades.py. This fires N concurrent buys that individually fit
inside a 100k balance but collectively exceed it, and asserts exactly one
succeeds and the balance never goes negative.

Uses a file-based SQLite DB (not `sqlite+aiosqlite://` in-memory) so
concurrent requests get real, separate connections subject to SQLite's own
transaction locking — an in-memory DB defaults to a single shared
StaticPool connection, where interleaved sessions can roll back each
other's commits and the test would not exercise real concurrency.
"""
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
import pytz
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from unittest.mock import AsyncMock, patch
import asyncio

from database import Base, get_db
from db.models import Season, Portfolio
from main import app

# price=990, qty=100 -> total_cost (incl. fees) is ~99,144.57 — affordable
# once out of a 100,000 balance, but not twice.
MOCK_PRICE = {"ticker": "RELIANCE", "price": 990.0, "previous_close": 1000.0}


@pytest_asyncio.fixture
async def test_db(tmp_path):
    db_path = tmp_path / "race.db"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        echo=False,
        connect_args={"timeout": 15},
    )
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as db:
        season = Season(
            name="Season 1",
            start_date=datetime.now(timezone.utc) - timedelta(days=1),
            end_date=datetime.now(timezone.utc) + timedelta(days=30),
            starting_capital=100000.0,
            is_active=True,
        )
        db.add(season)
        await db.commit()

    yield async_session

    await engine.dispose()


@pytest.mark.asyncio
async def test_concurrent_buys_race_on_sqlite(test_db):
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

    monday_patch = patch("engine.validator.datetime")

    try:
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
            headers = {"Authorization": f"Bearer {token}"}

            IST = pytz.timezone("Asia/Kolkata")
            open_monday = IST.localize(datetime(2026, 3, 16, 10, 0))
            mock_dt = monday_patch.start()
            mock_dt.now.return_value = open_monday
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

            async def fire():
                return await client.post("/trades", headers=headers, json={
                    "ticker": "RELIANCE",
                    "side": "buy",
                    "order_type": "market",
                    "quantity": 100,
                })

            responses = await asyncio.gather(*(fire() for _ in range(10)))
    finally:
        monday_patch.stop()
        app.dependency_overrides.pop(get_db, None)

    statuses = [r.status_code for r in responses]
    assert statuses.count(200) == 1, f"expected exactly one fill, got statuses={statuses}"
    assert statuses.count(400) == 9

    async with test_db() as session:
        portfolio = (await session.execute(select(Portfolio))).scalar_one()
        assert portfolio.cash_balance >= 0
        # Only the one successful ~99,144.57 buy should have been deducted.
        # cash_balance is Decimal (Numeric column); cast to float to compare
        # against pytest.approx's float tolerance arithmetic.
        assert float(portfolio.cash_balance) == pytest.approx(100000.0 - 99144.57, abs=0.01)
