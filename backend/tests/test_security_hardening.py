# tests/test_security_hardening.py
"""Security-review fixes: client-IP derivation, /price hardening, script
concurrency cap, registration validation, login timing, JWT revocation."""
import asyncio
import json
import logging
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from jose import jwt
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

import config
from api import token_revocation
from api.rate_limit import resolve_client_ip, client_ip
from api.routes import auth as auth_module
from api.routes import scripts as scripts_module
from api.routes import websocket as ws_module
from api.routes.auth import create_access_token
from database import Base, get_db
from db.models import Season, User
from main import app

XHR = {"X-Requested-With": "XMLHttpRequest"}


class FakeRedis:
    def __init__(self):
        self.store: dict = {}
        self.ttls: dict = {}
        self.fail = False

    def _check(self):
        if self.fail:
            raise ConnectionError("redis down")

    async def incr(self, key):
        self._check()
        self.store[key] = int(self.store.get(key, 0)) + 1
        return self.store[key]

    async def expire(self, key, seconds):
        self._check()

    async def get(self, key):
        self._check()
        v = self.store.get(key)
        return v.encode() if isinstance(v, str) else v

    async def set(self, key, value, ex=None):
        self._check()
        self.store[key] = value
        self.ttls[key] = ex


@pytest_asyncio.fixture
async def env():
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with maker() as db:
        db.add(Season(name="S1", start_date=datetime.now(timezone.utc) - timedelta(days=1),
                      end_date=datetime.now(timezone.utc) + timedelta(days=30),
                      starting_capital=100000.0, is_active=True))
        await db.commit()

    async def override_get_db():
        async with maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    redis = FakeRedis()
    app.state.broadcaster = AsyncMock()
    app.state.broadcaster.redis = redis
    token_revocation._warned = False
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield SimpleNamespace(client=client, redis=redis, maker=maker)
    app.dependency_overrides.pop(get_db, None)
    await engine.dispose()


async def _register(client, name=None, password="password123"):
    name = name or f"user_{uuid.uuid4().hex[:8]}"
    resp = await client.post("/auth/register", json={
        "username": name, "email": f"{name}@nse-arena.com", "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


# ── 2. Client IP ────────────────────────────────────────────────────

def test_public_peer_xff_is_ignored():
    assert resolve_client_ip("8.8.8.8", "1.2.3.4") == "8.8.8.8"


def test_private_peer_honours_xff():
    assert resolve_client_ip("172.18.0.2", "203.0.113.9") == "203.0.113.9"
    assert resolve_client_ip("127.0.0.1", "203.0.113.9") == "203.0.113.9"


def test_only_rightmost_xff_entry_is_used():
    # Caddy writes a single client_ip value; anything left of it is forged.
    assert resolve_client_ip("172.18.0.2", "6.6.6.6, 100.64.0.5") == "100.64.0.5"
    assert resolve_client_ip("172.18.0.2", "6.6.6.6, 203.0.113.9") == "203.0.113.9"


def test_tailscale_ipv6_client_is_returned():
    assert resolve_client_ip("172.18.0.2", "fd7a:115c:a1e0::1") == "fd7a:115c:a1e0::1"


@pytest.mark.parametrize("peer", ["100.64.0.5", "100.127.255.254", "fd7a:115c:a1e0::5",
                                  "fd7a:115c:a1e0:ab12::7"])
def test_tailscale_peer_cannot_forge_xff(peer):
    # A tailnet client reaching the backend directly is the client itself.
    assert resolve_client_ip(peer, "198.51.100.77") == peer
    assert resolve_client_ip(peer, "10.0.0.1") == peer


def test_forged_xff_left_of_tailscale_client_ignored():
    assert resolve_client_ip("172.18.0.2", "198.51.100.77, 100.101.102.103") == "100.101.102.103"
    assert resolve_client_ip("172.18.0.2", "198.51.100.77, fd7a:115c:a1e0::9") == "fd7a:115c:a1e0::9"


def test_non_tailscale_ula_is_still_internal():
    assert resolve_client_ip("fd00::2", "203.0.113.9") == "203.0.113.9"


@pytest.mark.parametrize("bad", ["not-an-ip", "1.2.3.4, evil", "1.2.3.4:80", "<script>", ","])
def test_malformed_xff_falls_back_to_peer(bad):
    assert resolve_client_ip("172.18.0.2", bad) == "172.18.0.2"


def test_missing_peer_and_nonip_peer():
    assert resolve_client_ip(None, "1.2.3.4") == "unknown"
    assert resolve_client_ip("testclient", "1.2.3.4") == "testclient"


def test_client_ip_works_for_requests_and_websockets():
    conn = SimpleNamespace(client=SimpleNamespace(host="10.0.0.2"),
                           headers={"x-forwarded-for": "198.51.100.7"})
    assert client_ip(conn) == "198.51.100.7"
    assert not hasattr(ws_module, "_client_ip")  # one shared helper


@pytest.mark.asyncio
async def test_http_rate_limit_buckets_by_forwarded_ip(env):
    # httpx ASGI peer is 127.0.0.1 (loopback = the reverse proxy)
    hdr = {"X-Forwarded-For": "198.51.100.1"}
    codes = [(await env.client.post("/auth/login/json", json={"username": "n", "password": "x"},
                                    headers=hdr)).status_code for _ in range(6)]
    assert codes == [401] * 5 + [429]
    other = await env.client.post("/auth/login/json", json={"username": "n", "password": "x"},
                                  headers={"X-Forwarded-For": "198.51.100.2"})
    assert other.status_code == 401


# ── 3. /price ───────────────────────────────────────────────────────

OHLCV = [{"time": 1, "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, "volume": 10}]


@pytest.fixture
def fetcher():
    with patch("market_data.fetcher.MarketDataFetcher.get_ohlcv", return_value=OHLCV) as o, \
         patch("market_data.fetcher.MarketDataFetcher.get_price", return_value={"price": 1.5}) as p, \
         patch("main.broadcaster.get_cached_price", new_callable=AsyncMock, return_value=None):
        yield SimpleNamespace(ohlcv=o, price=p)


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/price/bad%20ticker", "/price/AB.NS", "/price/A%3BB",
                                  "/price/" + "A" * 21])
async def test_price_rejects_invalid_ticker(env, fetcher, path):
    assert (await env.client.get(path)).status_code == 400
    fetcher.ohlcv.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("path,expected", [("/price/M%26M", "M&M"), ("/price/BAJAJ-AUTO", "BAJAJ-AUTO"),
                                           ("/price/reliance", "RELIANCE")])
async def test_price_accepts_nifty_symbols(env, fetcher, path, expected):
    with patch("main.broadcaster.redis", env.redis):
        resp = await env.client.get(path)
    assert resp.status_code == 200
    assert resp.json()["ticker"] == expected


@pytest.mark.asyncio
async def test_price_ohlcv_cached_60s(env, fetcher):
    with patch("main.broadcaster.redis", env.redis):
        await env.client.get("/price/TCS")
        await env.client.get("/price/TCS")
    assert fetcher.ohlcv.call_count == 1
    assert env.redis.ttls["ohlcv:TCS:1mo"] == 60


@pytest.mark.asyncio
async def test_price_degrades_when_redis_down(env, fetcher):
    env.redis.fail = True
    with patch("main.broadcaster.redis", env.redis), \
         patch("main.broadcaster.get_cached_price", new_callable=AsyncMock,
               side_effect=ConnectionError("down")):
        resp = await env.client.get("/price/TCS")
    assert resp.status_code == 200 and resp.json()["ohlcv"] == OHLCV


@pytest.mark.asyncio
async def test_price_rate_limited_per_ip(env, fetcher):
    with patch("main.broadcaster.redis", env.redis):
        codes = [(await env.client.get("/price/TCS")).status_code for _ in range(31)]
    assert codes[:30] == [200] * 30 and codes[30] == 429


# ── 3/4. Scripts ────────────────────────────────────────────────────

SCRIPT = {"code": "plot(close)", "ticker": "TCS", "period": "3mo"}


@pytest.mark.asyncio
@pytest.mark.parametrize("override", [{"ticker": "../etc"}, {"ticker": "a b"}, {"period": "max"},
                                      {"period": "10y"}])
async def test_script_run_validates_ticker_and_period(env, override):
    token = await _register(env.client)
    resp = await env.client.post("/api/scripts/run", json={**SCRIPT, **override},
                                 headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 422


def _fake_result():
    return SimpleNamespace(indicator_title="t", plots=[], hlines=[], logs=[], errors=[])


@pytest.mark.asyncio
async def test_script_concurrency_cap_and_release(env):
    token = await _register(env.client)
    auth = {"Authorization": f"Bearer {token}"}
    started, gate = threading.Event(), threading.Event()

    def blocking(code, ohlcv, ts):
        started.set()
        gate.wait(5)
        return _fake_result()

    with patch.object(scripts_module, "run_script", blocking), \
         patch("api.routes.scripts.MarketDataFetcher.get_ohlcv", return_value=OHLCV):
        first = asyncio.create_task(env.client.post("/api/scripts/run", json=SCRIPT, headers=auth))
        while not started.is_set():
            await asyncio.sleep(0.01)
        second = await env.client.post("/api/scripts/run", json=SCRIPT, headers=auth)
        assert second.status_code == 429 and "already running" in second.json()["detail"]
        gate.set()
        assert (await first).status_code == 200
        assert (await env.client.post("/api/scripts/run", json=SCRIPT, headers=auth)).status_code == 200
    assert scripts_module._active_runs == set()


@pytest.mark.asyncio
async def test_script_slot_released_on_error_and_fetch_failure(env):
    token = await _register(env.client)
    auth = {"Authorization": f"Bearer {token}"}
    with patch("api.routes.scripts.MarketDataFetcher.get_ohlcv", return_value=OHLCV), \
         patch.object(scripts_module, "run_script", side_effect=RuntimeError("boom")):
        assert (await env.client.post("/api/scripts/run", json=SCRIPT, headers=auth)).status_code == 500
    assert scripts_module._active_runs == set()
    with patch("api.routes.scripts.MarketDataFetcher.get_ohlcv", side_effect=RuntimeError("net")):
        assert (await env.client.post("/api/scripts/run", json=SCRIPT, headers=auth)).status_code == 502
    assert scripts_module._active_runs == set()


@pytest.mark.asyncio
async def test_script_slot_tied_to_worker_not_http_timeout(env):
    token = await _register(env.client)
    auth = {"Authorization": f"Bearer {token}"}
    gate = threading.Event()

    def slow(code, ohlcv, ts):
        gate.wait(5)
        return _fake_result()

    with patch.object(scripts_module, "run_script", slow), \
         patch.object(scripts_module, "SCRIPT_TIMEOUT", 0.05), \
         patch("api.routes.scripts.MarketDataFetcher.get_ohlcv", return_value=OHLCV):
        assert (await env.client.post("/api/scripts/run", json=SCRIPT, headers=auth)).status_code == 408
        # HTTP request timed out but the worker is still running: slot still held
        assert (await env.client.post("/api/scripts/run", json=SCRIPT, headers=auth)).status_code == 429
        gate.set()
        for _ in range(200):
            if not scripts_module._active_runs:
                break
            await asyncio.sleep(0.01)
        assert scripts_module._active_runs == set()


def test_engine_budget_is_three_seconds_and_enforced():
    from scripting.engine import EXECUTION_BUDGET_SECONDS, PineEngine
    assert EXECUTION_BUDGET_SECONDS == 3.0
    eng = PineEngine([{"open": 1.0, "high": 2.0, "low": 0.5, "close": 1.0, "volume": 1}], [1])
    eng.start_time = time.perf_counter() - 3.5
    with pytest.raises(TimeoutError, match="3s limit"):
        eng.execute("plot(close)")


# ── 5. Registration / login ─────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [
    {"username": "ab"}, {"username": "a" * 31}, {"username": "bad name"}, {"username": "a.b!"},
    {"email": "nope"}, {"email": "a@b"}, {"email": "a" * 96 + "@b.co"},
    {"password": "1234567"}, {"password": "p" * 129},
])
async def test_register_rejects_invalid_input_with_422(env, payload):
    body = {"username": "good_user", "email": "good@example.com", "password": "password123", **payload}
    resp = await env.client.post("/auth/register", json=body)
    assert resp.status_code == 422
    assert isinstance(resp.json()["detail"], list)


@pytest.mark.asyncio
async def test_register_accepts_boundaries_and_keeps_duplicate_messages(env):
    await _register(env.client, name="abc", password="12345678")
    await _register(env.client, name="A-b_" + "x" * 26, password="p" * 128)
    dup_user = await env.client.post("/auth/register", json={
        "username": "ABC", "email": "other@example.com", "password": "password123"})
    assert dup_user.status_code == 400 and dup_user.json()["detail"] == "Username already registered"


@pytest.mark.asyncio
async def test_login_does_not_apply_registration_rules(env):
    async with env.maker() as db:
        db.add(User(username="a.legacy name", email="old@example.com",
                    hashed_password=auth_module.pwd_context.hash("abc")))
        db.add(User(username="ai-agent", email="ai@example.com", is_ai=True,
                    hashed_password=auth_module.pwd_context.hash("x" * 20)))
        await db.commit()
    resp = await env.client.post("/auth/login/json", json={"username": "a.legacy name", "password": "abc"})
    assert resp.status_code == 200
    resp = await env.client.post("/auth/login/json", json={"username": "ai-agent", "password": "x" * 20})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_login_unknown_user_still_runs_one_bcrypt_verify(env):
    assert auth_module.pwd_context.identify(auth_module._DUMMY_HASH) == "bcrypt"
    with patch.object(auth_module.pwd_context, "verify", return_value=False) as verify:
        resp = await env.client.post("/auth/login/json", json={"username": "ghost", "password": "pw"})
        assert resp.status_code == 401
        verify.assert_called_once_with("pw", auth_module._DUMMY_HASH)


# ── 6. JWT revocation ───────────────────────────────────────────────

def test_new_tokens_carry_unique_jti_and_iat():
    a = jwt.get_unverified_claims(create_access_token({"sub": "1"}))
    b = jwt.get_unverified_claims(create_access_token({"sub": "1"}))
    assert a["jti"] != b["jti"] and "iat" in a


@pytest.mark.asyncio
async def test_logout_revokes_token_with_remaining_ttl(env):
    token = await _register(env.client)
    claims = jwt.get_unverified_claims(token)
    auth = {"Authorization": f"Bearer {token}"}
    assert (await env.client.get("/auth/me", headers=auth)).status_code == 200
    assert (await env.client.post("/auth/logout", headers=auth)).status_code == 200
    key = f"jwt:revoked:{claims['jti']}"
    assert key in env.redis.store
    assert 0 < env.redis.ttls[key] <= config.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    assert (await env.client.get("/auth/me", headers=auth)).status_code == 401
    assert await ws_module._valid_token(token, app) is False
    # a different, newer token for the same user still works
    fresh = create_access_token({"sub": claims["sub"]})
    assert (await env.client.get("/auth/me", headers={"Authorization": f"Bearer {fresh}"})).status_code == 200


@pytest.mark.asyncio
async def test_cookie_logout_requires_csrf_header_and_revokes(env):
    await _register(env.client)
    assert (await env.client.post("/auth/logout")).status_code == 403
    assert (await env.client.get("/auth/me")).status_code == 200  # nothing happened
    assert (await env.client.post("/auth/logout", headers=XHR)).status_code == 200
    assert any(k.startswith("jwt:revoked:") for k in env.redis.store)


@pytest.mark.asyncio
async def test_logout_without_or_with_bad_token_is_ok(env):
    assert (await env.client.post("/auth/logout")).status_code == 200
    resp = await env.client.post("/auth/logout", headers={"Authorization": "Bearer garbage"})
    assert resp.status_code == 200 and not env.redis.store


@pytest.mark.asyncio
async def test_legacy_token_without_jti_still_accepted(env):
    token = await _register(env.client)
    uid = jwt.get_unverified_claims(token)["sub"]
    legacy = jwt.encode({"sub": uid, "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
                        config.SECRET_KEY, algorithm=config.ALGORITHM)
    assert (await env.client.get("/auth/me", headers={"Authorization": f"Bearer {legacy}"})).status_code == 200
    assert (await env.client.post("/auth/logout", headers={"Authorization": f"Bearer {legacy}"})).status_code == 200
    assert (await env.client.get("/auth/me", headers={"Authorization": f"Bearer {legacy}"})).status_code == 200


@pytest.mark.asyncio
async def test_revocation_fails_open_and_warns_once(env, caplog):
    token = await _register(env.client)
    auth = {"Authorization": f"Bearer {token}"}
    env.redis.fail = True
    with caplog.at_level(logging.WARNING, logger="api.token_revocation"):
        assert (await env.client.get("/auth/me", headers=auth)).status_code == 200
        assert (await env.client.get("/auth/me", headers=auth)).status_code == 200
        assert (await env.client.post("/auth/logout", headers=auth)).status_code == 200
    warnings = [r for r in caplog.records if r.name == "api.token_revocation"]
    assert len(warnings) == 1


@pytest.mark.asyncio
async def test_register_integrity_error_maps_to_same_400(env):
    """A concurrent duplicate that slips past the pre-check and trips the
    unique index returns the same 400 as the pre-check."""
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.ext.asyncio import AsyncSession
    err = IntegrityError("INSERT", {}, Exception("UNIQUE constraint failed: index 'ix_users_username_lower'"))
    with patch.object(AsyncSession, "flush", side_effect=err):
        resp = await env.client.post("/auth/register", json={
            "username": "racer", "email": "racer@example.com", "password": "password123"})
    assert resp.status_code == 400 and resp.json()["detail"] == "Username already registered"
