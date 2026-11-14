# tests/test_ai_agent_seed.py
"""The scheduler trades as the single User with is_ai=True and skips the
cycle when that user or its portfolio is missing. Nothing created either,
so the agent never traded. ensure_ai_agent() seeds both at startup.
"""
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

import main
from database import Base
from db.models import Season, User, Portfolio


@pytest_asyncio.fixture
async def session_factory(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'seed.db'}", echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    monkeypatch.setattr(main, "async_session", factory)
    yield factory
    await engine.dispose()


async def _add_season(factory, capital=100000.0):
    async with factory() as db:
        db.add(Season(
            name="Season 1",
            start_date=datetime.now(timezone.utc),
            end_date=datetime.now(timezone.utc) + timedelta(days=30),
            starting_capital=capital,
        ))
        await db.commit()


async def _ai_rows(factory):
    async with factory() as db:
        users = (await db.execute(select(User).where(User.is_ai == True))).scalars().all()
        portfolios = (await db.execute(select(Portfolio))).scalars().all()
        return users, portfolios


@pytest.mark.asyncio
async def test_seeds_ai_user_and_portfolio(session_factory):
    await _add_season(session_factory, capital=250000.0)

    await main.ensure_ai_agent()

    users, portfolios = await _ai_rows(session_factory)
    assert len(users) == 1
    assert users[0].username == main.AI_AGENT_USERNAME
    assert len(portfolios) == 1
    assert portfolios[0].user_id == users[0].id
    assert float(portfolios[0].cash_balance) == 250000.0


@pytest.mark.asyncio
async def test_seeding_is_idempotent(session_factory):
    await _add_season(session_factory)

    await main.ensure_ai_agent()
    await main.ensure_ai_agent()

    users, portfolios = await _ai_rows(session_factory)
    assert len(users) == 1
    assert len(portfolios) == 1


@pytest.mark.asyncio
async def test_no_active_season_creates_user_only(session_factory):
    await main.ensure_ai_agent()

    users, portfolios = await _ai_rows(session_factory)
    assert len(users) == 1
    assert portfolios == []


@pytest.mark.asyncio
async def test_seeded_account_cannot_be_logged_into(session_factory):
    from api.routes.auth import pwd_context

    await main.ensure_ai_agent()

    users, _ = await _ai_rows(session_factory)
    for guess in ("", "ai-agent", "password"):
        assert pwd_context.verify(guess, users[0].hashed_password) is False
