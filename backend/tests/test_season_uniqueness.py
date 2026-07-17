# tests/test_season_uniqueness.py
"""FOLLOWUP 'also verify': Season.is_active had no DB-level uniqueness —
ensure_active_season() at boot did a check-then-insert with no lock, so
two workers starting simultaneously could both see no active season and
both create one. A partial unique index (WHERE is_active) now makes the
second INSERT fail with an IntegrityError; ensure_active_season() treats
that as "another worker already created it" rather than crashing.
"""
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from database import Base
from db.models import Season


@pytest_asyncio.fixture
async def db_session(tmp_path):
    # File-based, not `sqlite+aiosqlite://` in-memory: an in-memory DB
    # defaults to a single shared StaticPool connection, where a rollback
    # on one interleaved session can undo another session's already-
    # committed work — exactly the kind of false negative/positive this
    # test needs to avoid when genuinely racing two coroutines.
    db_path = tmp_path / "season_race.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_session
    await engine.dispose()


def _season(name="Season 1", active=True):
    return Season(
        name=name,
        start_date=datetime.utcnow(),
        end_date=datetime.utcnow() + timedelta(days=30),
        starting_capital=100000.0,
        is_active=active,
    )


@pytest.mark.asyncio
async def test_second_active_season_insert_raises_integrity_error(db_session):
    async with db_session() as db1:
        db1.add(_season("Season 1"))
        await db1.commit()

    async with db_session() as db2:
        db2.add(_season("Season 1 Duplicate"))
        with pytest.raises(IntegrityError):
            await db2.commit()


@pytest.mark.asyncio
async def test_multiple_inactive_seasons_are_allowed(db_session):
    """The index is partial — only one active season at a time, but any
    number of inactive (past) seasons."""
    async with db_session() as db:
        db.add(_season("Season 1", active=False))
        db.add(_season("Season 2", active=False))
        db.add(_season("Season 3", active=False))
        await db.commit()  # must not raise

    async with db_session() as db2:
        from sqlalchemy import select
        count = len((await db2.execute(select(Season))).scalars().all())
        assert count == 3


@pytest.mark.asyncio
async def test_ensure_active_season_handles_concurrent_creation(monkeypatch, db_session):
    """Simulate the actual boot race with two interleaved calls to
    ensure_active_season() against a DB with no active season yet
    (asyncio.gather, not sequential awaits, so both coroutines' SELECTs
    can genuinely run before either commits) — neither call may crash
    the app, and exactly one active season must exist afterward."""
    import asyncio
    import main as main_module
    from sqlalchemy import select

    monkeypatch.setattr(main_module, "async_session", db_session)

    await asyncio.gather(
        main_module.ensure_active_season(),
        main_module.ensure_active_season(),
    )

    async with db_session() as db:
        active = (await db.execute(
            select(Season).where(Season.is_active == True)
        )).scalars().all()
        assert len(active) == 1
