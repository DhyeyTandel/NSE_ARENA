# tests/test_username_index.py
"""Case-insensitive username uniqueness enforced by the database."""
from unittest.mock import patch

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import database
from database import Base
from db.models import User


def _user(name, email):
    return User(username=name, email=email, hashed_password="x")


@pytest.mark.asyncio
async def test_create_all_builds_lower_username_unique_index():
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as db:
        db.add(_user("Admin", "a@x.io"))
        await db.commit()
        db.add(_user("admin", "b@x.io"))
        with pytest.raises(IntegrityError):
            await db.commit()
    await engine.dispose()


@pytest.mark.asyncio
async def test_ensure_index_is_idempotent_on_existing_table():
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        # a pre-existing table without the index
        await conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, username VARCHAR(50))"))
    with patch.object(database, "engine", engine):
        await database._ensure_username_lower_index()
        await database._ensure_username_lower_index()  # second run: no error
    async with engine.begin() as conn:
        await conn.execute(text("INSERT INTO users (username) VALUES ('Bob')"))
        with pytest.raises(IntegrityError):
            await conn.execute(text("INSERT INTO users (username) VALUES ('bOB')"))
    await engine.dispose()


@pytest.mark.asyncio
async def test_ensure_index_warns_and_continues_when_rows_collide(caplog):
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, username VARCHAR(50))"))
        await conn.execute(text("INSERT INTO users (username) VALUES ('Bob'), ('bob')"))
    with patch.object(database, "engine", engine), caplog.at_level("WARNING"):
        await database._ensure_username_lower_index()  # must not raise
    assert "case-insensitive username index" in caplog.text
    await engine.dispose()
