# tests/test_cookie_auth.py
"""Item 7 (ANTIGRAVITY_NEXT.md): JWT out of localStorage.

The browser now authenticates via an httpOnly cookie set on
login/register (JS can't read it, so XSS can't exfiltrate the token).
get_current_user accepts the cookie with a Bearer-header fallback for API
clients/tests. Cookie-authenticated mutating requests must carry
X-Requested-With (CSRF guard — cross-site form posts can send our cookie
but can't set custom headers). /auth/logout clears the cookie. The
WebSocket handshake accepts the same cookie (tested in
test_websocket_auth.py's first-frame fallback plus the cookie test here).
"""
import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from unittest.mock import AsyncMock

from database import Base, get_db
from db.models import Season
from api.dependencies import AUTH_COOKIE_NAME
from main import app


class FakeRedis:
    def __init__(self):
        self._counts = {}

    async def incr(self, key):
        self._counts[key] = self._counts.get(key, 0) + 1
        return self._counts[key]

    async def expire(self, key, seconds):
        pass


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
    app.state.broadcaster.get_all_cached_prices = AsyncMock(return_value={})

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    app.dependency_overrides.pop(get_db, None)


async def _register(client):
    username = f"user_{uuid.uuid4().hex[:8]}"
    resp = await client.post("/auth/register", json={
        "username": username,
        "email": f"{username}@nse-arena.com",
        "password": "password123",
    })
    assert resp.status_code == 200
    return resp


@pytest.mark.asyncio
async def test_register_sets_httponly_cookie(client):
    resp = await _register(client)
    set_cookie = resp.headers.get("set-cookie", "")
    assert AUTH_COOKIE_NAME in set_cookie
    assert "HttpOnly" in set_cookie
    assert "SameSite=lax" in set_cookie.lower() or "samesite=lax" in set_cookie.lower()


@pytest.mark.asyncio
async def test_cookie_authenticates_get_me_without_bearer_header(client):
    await _register(client)
    # httpx client carries the cookie jar forward automatically.
    resp = await client.get("/auth/me")
    assert resp.status_code == 200
    assert "username" in resp.json()


@pytest.mark.asyncio
async def test_cookie_mutation_without_csrf_header_rejected(client):
    await _register(client)
    resp = await client.post("/api/scripts/save", json={"name": "x", "code": "plot(close)"})
    assert resp.status_code == 403
    assert "X-Requested-With" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_cookie_mutation_with_csrf_header_accepted(client):
    await _register(client)
    resp = await client.post(
        "/api/scripts/save",
        json={"name": "x", "code": "plot(close)"},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_bearer_header_skips_csrf_requirement(client):
    resp = await _register(client)
    token = resp.json()["access_token"]
    client.cookies.clear()
    resp = await client.post(
        "/api/scripts/save",
        json={"name": "x", "code": "plot(close)"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_logout_clears_cookie(client):
    await _register(client)
    resp = await client.post("/auth/logout")
    assert resp.status_code == 200
    # After logout the cookie jar no longer authenticates us.
    resp = await client.get("/auth/me")
    assert resp.status_code == 401


def test_websocket_accepts_auth_cookie():
    from api.routes import websocket as ws_module
    from api.routes.auth import create_access_token

    app.state.broadcaster = AsyncMock()
    app.state.broadcaster.get_all_cached_prices = AsyncMock(return_value={})
    ws_module.connected_clients.clear()
    ws_module._ip_connection_counts.clear()

    token = create_access_token({"sub": "1"})
    tc = TestClient(app, cookies={AUTH_COOKIE_NAME: token})
    with tc.websocket_connect("/ws/prices"):
        # No first-frame token sent — the cookie authenticated the
        # handshake, so the connection stays open (no 4401 close frame).
        assert len(ws_module.connected_clients) == 1
