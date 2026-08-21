# database.py
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from config import DATABASE_URL

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def db_utcnow() -> datetime:
    """Naive UTC 'now' for anything stored in or compared against a
    DateTime column. Every DateTime column in this schema is naive —
    SQLite/aiosqlite silently drops tzinfo on read-back even with
    DateTime(timezone=True) (verified: a value written aware comes back
    with tzinfo=None), so storing an aware value here would just make
    writes and reads inconsistent with each other. This is the
    non-deprecated replacement for datetime.utcnow(): the identical
    naive-UTC value, just not the removed API."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
