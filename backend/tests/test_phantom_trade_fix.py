# tests/test_phantom_trade_fix.py
"""P0 audit fix: `side`/`order_type` were typed as bare `str` on
TradeRequest, so a non-canonical value like "Sell" (capital S) passed
FastAPI validation, built an internal SELL order, got recorded as an
"executed" TradeRecord — but the state-mutation branches only match the
exact lowercase literals "buy"/"sell", so no cash or position ever moved.
Typing the fields as Literal["buy","sell"] / Literal["market","limit"]
makes FastAPI reject malformed values with 422 before the mutation path
is ever reached.
"""
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from unittest.mock import AsyncMock, patch

from database import Base, get_db
from db.models import Season, User, Portfolio, Position
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
            start_date=datetime.now(timezone.utc) - timedelta(days=1),
            end_date=datetime.now(timezone.utc) + timedelta(days=30),
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


async def _give_confirmed_position(test_db, username, ticker, quantity, avg_price):
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
async def test_malformed_side_capital_s_rejected_with_422(test_db, client_and_token):
    """The exact phantom-trade repro from the audit: a confirmed holder
    sends side="Sell" (capital S). Before the fix this passed validation,
    built a SELL order internally, and committed a TradeRecord marked
    "executed" without ever touching cash or the position. It must now be
    rejected outright by FastAPI's request validation."""
    client, token, username = client_and_token
    headers = {"Authorization": f"Bearer {token}"}
    await _give_confirmed_position(test_db, username, "RELIANCE", 10, 900.0)

    p = _open_monday_patch()
    try:
        resp = await client.post("/trades", headers=headers, json={
            "ticker": "RELIANCE",
            "side": "Sell",
            "order_type": "market",
            "quantity": 1,
        })
        assert resp.status_code == 422
    finally:
        p.stop()

    # Confirm nothing moved: position untouched, no trade record written.
    async with test_db() as session:
        user = (await session.execute(select(User).where(User.username == username))).scalar_one()
        portfolio = (await session.execute(
            select(Portfolio).where(Portfolio.user_id == user.id)
        )).scalar_one()
        pos = (await session.execute(
            select(Position).where(Position.portfolio_id == portfolio.id, Position.ticker == "RELIANCE")
        )).scalar_one()
        assert pos.quantity == 10
        assert portfolio.cash_balance == 100000.0


@pytest.mark.asyncio
async def test_malformed_ticker_rejected_with_422(client_and_token):
    """P2 audit fix: ticker had no format validation before reaching
    yfinance. A stray space/quote/path-like string must 422, not sail
    through to MarketDataFetcher.get_price()."""
    client, token, _username = client_and_token
    headers = {"Authorization": f"Bearer {token}"}
    p = _open_monday_patch()
    try:
        for bad_ticker in ["RELIANCE; DROP", "../../etc/passwd", "", "a" * 21, "reliance"]:
            resp = await client.post("/trades", headers=headers, json={
                "ticker": bad_ticker, "side": "buy", "order_type": "market", "quantity": 1,
            })
            assert resp.status_code == 422, f"{bad_ticker!r} should have been rejected"
    finally:
        p.stop()


@pytest.mark.asyncio
async def test_malformed_order_type_rejected_with_422(client_and_token):
    client, token, _username = client_and_token
    headers = {"Authorization": f"Bearer {token}"}
    p = _open_monday_patch()
    try:
        resp = await client.post("/trades", headers=headers, json={
            "ticker": "RELIANCE",
            "side": "buy",
            "order_type": "Market",
            "quantity": 1,
        })
        assert resp.status_code == 422
    finally:
        p.stop()


@pytest.mark.asyncio
async def test_wellformed_lowercase_sell_still_executes(test_db, client_and_token):
    """Sanity check the fix doesn't break legitimate sells: a well-formed
    lowercase "sell" must still move cash and reduce the position."""
    client, token, username = client_and_token
    headers = {"Authorization": f"Bearer {token}"}
    await _give_confirmed_position(test_db, username, "RELIANCE", 10, 900.0)

    p = _open_monday_patch()
    try:
        resp = await client.post("/trades", headers=headers, json={
            "ticker": "RELIANCE",
            "side": "sell",
            "order_type": "market",
            "quantity": 4,
        })
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "executed"
        assert body["side"] == "sell"
    finally:
        p.stop()

    async with test_db() as session:
        user = (await session.execute(select(User).where(User.username == username))).scalar_one()
        portfolio = (await session.execute(
            select(Portfolio).where(Portfolio.user_id == user.id)
        )).scalar_one()
        pos = (await session.execute(
            select(Position).where(Position.portfolio_id == portfolio.id, Position.ticker == "RELIANCE")
        )).scalar_one()
        assert pos.quantity == 6
        # sell_value = 1000 * 4 - fees.total; balance must have increased.
        assert portfolio.cash_balance > 100000.0
