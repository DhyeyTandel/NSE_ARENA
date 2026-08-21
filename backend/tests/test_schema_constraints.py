# tests/test_schema_constraints.py
"""P1 audit fix: schema hardening.
- TraderScore.season_id was a bare Integer, not a ForeignKey, inconsistent
  with Portfolio.season_id which correctly is one.
- No CheckConstraint enforced Position.quantity >= 0 or
  TradeRecord.quantity > 0 at the DB layer.
"""
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from database import Base
from db.models import Portfolio, Position, Season, TradeRecord, TraderScore, User


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield session_maker
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


async def _seeded(session_maker):
    async with session_maker() as session:
        season = Season(
            name="Season 1",
            start_date=datetime.now(timezone.utc) - timedelta(days=1),
            end_date=datetime.now(timezone.utc) + timedelta(days=30),
            starting_capital=100000.0,
            is_active=True,
        )
        user = User(username="u1", email="u1@nse-arena.com", hashed_password="x")
        session.add_all([season, user])
        await session.flush()
        portfolio = Portfolio(user_id=user.id, season_id=season.id, cash_balance=100000.0)
        session.add(portfolio)
        await session.commit()
        return season.id, user.id, portfolio.id


def test_trader_score_season_id_is_a_real_foreign_key():
    """SQLite doesn't enforce FK constraints at runtime unless
    `PRAGMA foreign_keys=ON` is set per-connection (production runs
    Postgres, which always enforces them) — verify at the schema-metadata
    level instead of relying on SQLite runtime behavior."""
    fks = TraderScore.__table__.c.season_id.foreign_keys
    assert len(fks) == 1
    assert next(iter(fks)).target_fullname == "seasons.id"


@pytest.mark.asyncio
async def test_position_negative_quantity_rejected(db):
    _season_id, _user_id, portfolio_id = await _seeded(db)
    async with db() as session:
        session.add(Position(portfolio_id=portfolio_id, ticker="RELIANCE", quantity=-5, avg_price=1000.0))
        with pytest.raises(IntegrityError):
            await session.commit()


@pytest.mark.asyncio
async def test_trade_record_zero_quantity_rejected(db):
    _season_id, _user_id, portfolio_id = await _seeded(db)
    async with db() as session:
        session.add(TradeRecord(
            portfolio_id=portfolio_id, order_id="x", ticker="RELIANCE",
            side="buy", order_type="market", quantity=0, price=1000.0,
        ))
        with pytest.raises(IntegrityError):
            await session.commit()


@pytest.mark.asyncio
async def test_position_zero_quantity_is_allowed(db):
    """quantity >= 0, not > 0 — zero is a valid (if transient) state, only
    negative is rejected."""
    _season_id, _user_id, portfolio_id = await _seeded(db)
    async with db() as session:
        session.add(Position(portfolio_id=portfolio_id, ticker="RELIANCE", quantity=0, avg_price=1000.0))
        await session.commit()  # must not raise
