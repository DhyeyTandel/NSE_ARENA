# tests/test_kite_callback.py
"""Kite login hardening: admin-only callback, server-side single-use state
bound to the admin, per-IP rate limits, clean 503 when Redis is down."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlparse

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

import config
from api.dependencies import get_current_user
from main import app


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

    async def set(self, key, value, ex=None):
        self._check()
        self.store[key] = value
        self.ttls[key] = ex

    async def getdel(self, key):
        self._check()
        v = self.store.pop(key, None)
        return v.encode() if isinstance(v, str) else v


class FakeKite:
    def __init__(self, api_key=None):
        pass

    def login_url(self):
        return "https://kite.zerodha.com/connect/login?v=3&api_key=k"


class FakeFeed:
    configured = True
    api_key = "k"
    connected = False
    last_tick_at = None

    def __init__(self):
        self.login = AsyncMock(return_value=True)
        self.stop = AsyncMock()


def _user(uid=1, name="boss"):
    return SimpleNamespace(id=uid, username=name, email="x@y.z", is_ai=False)


@pytest_asyncio.fixture
async def env():
    redis = FakeRedis()
    feed = FakeFeed()
    app.state.broadcaster = AsyncMock()
    app.state.broadcaster.redis = redis
    app.state.kite_feed = feed
    app.dependency_overrides[get_current_user] = lambda: _user()
    with patch.object(config, "ADMIN_USERNAMES", {"boss"}), \
         patch("market_data.kite_feed._sdk", return_value=(FakeKite, object)):
        async with AsyncClient(transport=ASGITransport(app=app),
                               base_url="http://test", follow_redirects=False) as client:
            yield SimpleNamespace(client=client, redis=redis, feed=feed)
    app.dependency_overrides.pop(get_current_user, None)


async def _start_login(env):
    resp = await env.client.get("/api/kite/login")
    assert resp.status_code == 302
    return parse_qs(urlparse(resp.headers["location"]).query)["redirect_params"][0].split("=", 1)[1]


@pytest.mark.asyncio
async def test_login_stores_single_use_state_server_side(env):
    state = await _start_login(env)
    key = "kite_oauth_state:" + state
    assert env.redis.store[key] == "1"
    assert 0 < env.redis.ttls[key] <= 600
    assert "kite_oauth_state" not in (await env.client.get("/api/kite/login")).headers.get("set-cookie", "")


@pytest.mark.asyncio
async def test_callback_happy_path_and_state_is_single_use(env):
    state = await _start_login(env)
    params = {"status": "success", "request_token": "rt", "state": state}
    resp = await env.client.get("/api/kite/callback", params=params)
    assert resp.status_code == 302 and "kite=error" not in resp.headers["location"]
    env.feed.login.assert_awaited_once_with("rt")
    again = await env.client.get("/api/kite/callback", params=params)
    assert again.headers["location"].endswith("/?kite=error")
    env.feed.login.assert_awaited_once()  # replay did not log in again


@pytest.mark.asyncio
@pytest.mark.parametrize("state", [None, "", "never-issued"])
async def test_callback_rejects_missing_or_unknown_state(env, state):
    params = {"status": "success", "request_token": "rt"}
    if state is not None:
        params["state"] = state
    resp = await env.client.get("/api/kite/callback", params=params)
    assert resp.status_code == 302 and resp.headers["location"].endswith("/?kite=error")
    env.feed.login.assert_not_awaited()


@pytest.mark.asyncio
async def test_callback_state_bound_to_the_admin_who_started_it(env):
    state = await _start_login(env)  # started by user id 1
    with patch.object(config, "ADMIN_USERNAMES", {"boss", "other"}):
        app.dependency_overrides[get_current_user] = lambda: _user(uid=2, name="other")
        resp = await env.client.get("/api/kite/callback", params={
            "status": "success", "request_token": "rt", "state": state})
    assert resp.headers["location"].endswith("/?kite=error")
    env.feed.login.assert_not_awaited()


@pytest.mark.asyncio
async def test_callback_requires_admin(env):
    app.dependency_overrides[get_current_user] = lambda: _user(name="nobody")
    resp = await env.client.get("/api/kite/callback", params={
        "status": "success", "request_token": "rt", "state": "x"})
    assert resp.status_code == 403
    app.dependency_overrides.pop(get_current_user)
    resp = await env.client.get("/api/kite/callback", params={"state": "x"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_callback_get_needs_no_csrf_header(env):
    # A top-level redirect from Zerodha carries the cookie but never sets
    # X-Requested-With; the CSRF check applies to mutating methods only.
    from api.dependencies import _extract_token
    req = SimpleNamespace(method="GET", cookies={"access_token": "t"}, headers={})
    assert _extract_token(req, None) == "t"


@pytest.mark.asyncio
async def test_callback_redis_down_is_error_redirect(env):
    env.redis.fail = True  # rate limiter fails open, state check rejects
    resp = await env.client.get("/api/kite/callback", params={
        "status": "success", "request_token": "rt", "state": "x"})
    assert resp.status_code == 302 and resp.headers["location"].endswith("/?kite=error")


@pytest.mark.asyncio
async def test_login_redis_down_is_503(env):
    env.redis.fail = True
    assert (await env.client.get("/api/kite/login")).status_code == 503


@pytest.mark.asyncio
async def test_callback_and_login_rate_limited_per_ip(env):
    codes = [(await env.client.get("/api/kite/callback", params={"state": "x"})).status_code
             for _ in range(11)]
    assert codes[:10] == [302] * 10 and codes[10] == 429
    codes = [(await env.client.get("/api/kite/login")).status_code for _ in range(11)]
    assert codes[:10] == [302] * 10 and codes[10] == 429


@pytest.mark.asyncio
async def test_disconnect_ok_and_503_when_redis_unavailable(env):
    resp = await env.client.post("/api/kite/disconnect", headers={"X-Requested-With": "XMLHttpRequest"})
    assert resp.status_code == 200
    env.feed.stop.side_effect = ConnectionError("redis down")
    resp = await env.client.post("/api/kite/disconnect", headers={"X-Requested-With": "XMLHttpRequest"})
    assert resp.status_code == 503
