"""
Smoke test: Start backend with SQLite, register a user,
and verify the auth flow works end-to-end.
Run from backend/: python tests/smoke_test.py
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Override DATABASE_URL to use SQLite for testing
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///test_smoke.db"


async def run():
    # Patch database module to use SQLite
    import config
    config.DATABASE_URL = "sqlite+aiosqlite:///test_smoke.db"

    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from database import Base

    engine = create_async_engine("sqlite+aiosqlite:///test_smoke.db", echo=False)
    test_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Database tables created")

    # Test via httpx
    from unittest.mock import patch, AsyncMock
    from httpx import AsyncClient, ASGITransport
    import database

    # Patch the session and init_db
    database.engine = engine
    database.async_session = test_session

    from main import app

    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Root endpoint
        resp = await client.get("/")
        assert resp.status_code == 200
        print(f"✅ GET / → {resp.json()}")

        # 2. Register a user
        resp = await client.post("/auth/register", json={
            "username": "testuser",
            "email": "test@nse-arena.com",
            "password": "password123"
        })
        assert resp.status_code == 200, f"Register failed: {resp.text}"
        token = resp.json()["access_token"]
        print(f"✅ POST /auth/register → token received")

        # 3. Get portfolio
        resp = await client.get("/portfolio", headers={
            "Authorization": f"Bearer {token}"
        })
        assert resp.status_code == 200, f"Portfolio failed: {resp.text}"
        portfolio = resp.json()
        assert portfolio["cash_balance"] == 100000.0
        print(f"✅ GET /portfolio → cash_balance=₹{portfolio['cash_balance']:,.2f}")

        # 4. Get trade history (should be empty)
        resp = await client.get("/trades", headers={
            "Authorization": f"Bearer {token}"
        })
        assert resp.status_code == 200
        assert resp.json() == []
        print(f"✅ GET /trades → empty (no trades yet)")

    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

    # Remove test DB file
    if os.path.exists("test_smoke.db"):
        os.remove("test_smoke.db")

    print("\n🎉 All smoke tests passed!")


if __name__ == "__main__":
    asyncio.run(run())
