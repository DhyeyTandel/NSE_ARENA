# tests/test_kite_feed.py
"""Kite Connect feed: tick mapping, throttle, Yahoo fallback rule, the
status/login/callback routes and "feature off". Everything is mocked; no
network, no real kiteconnect calls.
"""
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from market_data import broadcaster as b
from market_data import kite_feed as kf


class FakeTokenException(Exception):
    pass


class FakeKite:
    rows = [
        {"tradingsymbol": "M&M", "instrument_token": 1, "instrument_type": "EQ", "segment": "NSE"},
        {"tradingsymbol": "BAJAJ-AUTO", "instrument_token": 2, "instrument_type": "EQ", "segment": "NSE"},
        {"tradingsymbol": "TCS", "instrument_token": 3, "instrument_type": "EQ", "segment": "NSE"},
        {"tradingsymbol": "TCS", "instrument_token": 99, "instrument_type": "PE", "segment": "NSE"},
        {"tradingsymbol": "NOTNIFTY", "instrument_token": 4, "instrument_type": "EQ", "segment": "NSE"},
    ]
    raise_token = False
    invalidated = []

    def __init__(self, api_key):
        self.api_key = api_key

    def set_access_token(self, t):
        self.t = t

    def instruments(self, exchange=None):
        assert exchange == "NSE"
        if FakeKite.raise_token:
            raise FakeTokenException("bad")
        return self.rows

    def login_url(self):
        return f"https://kite.example/login?api_key={self.api_key}&v=3"

    def generate_session(self, request_token, api_secret):
        return {"access_token": "ACCESS"}

    def invalidate_access_token(self, token):
        FakeKite.invalidated.append(token)


class FakeTicker:
    MODE_QUOTE = "quote"

    def __init__(self, api_key, token, reconnect=True):
        self.connect_called = False
        self.closed = False
        self.retry_stopped = False
        self.subs = None

    def connect(self, threaded=False):
        self.connect_called = True

    def close(self):
        self.closed = True

    def stop_retry(self):
        self.retry_stopped = True

    def subscribe(self, tokens):
        self.subs = tokens

    def set_mode(self, mode, tokens):
        self.mode = mode


FAKE_SDK = (FakeKite, FakeTicker, FakeTokenException)


def make_feed(configured=True):
    pb = MagicMock()
    pb.redis = AsyncMock()
    pb.cache_price = AsyncMock()
    pb.publish_price = AsyncMock()
    feed = kf.KiteFeed(pb, "key" if configured else "", "secret" if configured else "")
    return feed, pb


def quote_tick(token=1, ltp=110.0, close=100.0):
    return {"instrument_token": token, "last_price": ltp, "volume_traded": 5000,
            "ohlc": {"open": 101.0, "high": 111.0, "low": 99.0, "close": close}}


# ── tick mapping ─────────────────────────────────────────────────────

def test_map_tick_shape_change_pct_and_source():
    d = kf.map_tick(quote_tick(), "M&M", True)
    assert d == {
        "ticker": "M&M", "price": 110.0, "previous_close": 100.0, "open": 101.0,
        "day_high": 111.0, "day_low": 99.0, "volume": 5000,
        "change_pct": pytest.approx(10.0), "market_open": True, "source": "kite",
    }


def test_map_tick_zero_prev_close_and_zero_price():
    assert kf.map_tick(quote_tick(close=0), "X", False)["change_pct"] == 0
    assert kf.map_tick(quote_tick(ltp=0), "X", True) is None


def test_next_6am_ist():
    from datetime import datetime
    from engine.market_calendar import IST
    assert kf.seconds_until_next_6am_ist(datetime(2026, 11, 13, 5, 0, tzinfo=IST)) == 3600
    assert kf.seconds_until_next_6am_ist(datetime(2026, 11, 13, 7, 0, tzinfo=IST)) == 23 * 3600


# ── ticker callbacks: mapping, throttle ──────────────────────────────

def armed_feed(clock):
    feed, pb = make_feed()
    feed._clock = clock
    feed._loop = object()
    feed._token_to_symbol = {1: "M&M", 2: "BAJAJ-AUTO"}
    feed._ticker = FakeTicker("k", "t")
    return feed, pb


def test_throttle_one_publish_per_ticker_per_second():
    now = [100.0]
    feed, _ = armed_feed(lambda: now[0])
    scheduled = []

    def fake_rcts(coro, loop):
        scheduled.append(coro.cr_frame.f_locals["symbol"])
        coro.close()

    with patch.object(kf.asyncio, "run_coroutine_threadsafe", fake_rcts):
        feed._on_ticks(feed._ticker, [quote_tick(1), quote_tick(1), quote_tick(2)])
        assert scheduled == ["M&M", "BAJAJ-AUTO"]
        now[0] += 0.5
        feed._on_ticks(feed._ticker, [quote_tick(1)])
        assert len(scheduled) == 2
        now[0] += 0.6
        feed._on_ticks(feed._ticker, [quote_tick(1), quote_tick(777)])  # unknown token ignored
        assert scheduled == ["M&M", "BAJAJ-AUTO", "M&M"]
    assert feed.has_fresh_tick()


@pytest.mark.asyncio
async def test_emit_caches_and_publishes():
    feed, pb = make_feed()
    data = kf.map_tick(quote_tick(), "M&M", True)
    await feed._emit("M&M", data)
    pb.cache_price.assert_awaited_once_with("M&M", data)
    pb.publish_price.assert_awaited_once_with("M&M", data)


# ── start / instruments / invalid token ──────────────────────────────

@pytest.mark.asyncio
async def test_start_resolves_nifty_instruments_and_subscribes():
    feed, _ = make_feed()
    FakeKite.raise_token = False
    with patch.object(kf, "_sdk", return_value=FAKE_SDK):
        assert await feed.start("tok") is True
        assert feed._token_to_symbol == {1: "M&M", 2: "BAJAJ-AUTO", 3: "TCS"}
        t = feed._ticker
        assert t.connect_called
        feed._on_connect(t, None)
        assert feed.connected and t.subs == [1, 2, 3] and t.mode == "quote"
        feed._on_close(t, 1006, "network")
        assert not feed.connected  # plain drop: SDK keeps retrying, we only flag it


@pytest.mark.asyncio
async def test_start_with_rejected_token_clears_it():
    feed, pb = make_feed()
    FakeKite.raise_token = True
    try:
        with patch.object(kf, "_sdk", return_value=FAKE_SDK):
            assert await feed.start("old") is False
    finally:
        FakeKite.raise_token = False
    pb.redis.delete.assert_awaited_once_with(kf.TOKEN_KEY)
    assert feed._ticker is None and not feed.connected


@pytest.mark.asyncio
async def test_ticker_403_stops_retry_and_clears_token():
    feed, pb = make_feed()
    with patch.object(kf, "_sdk", return_value=FAKE_SDK):
        await feed.start("tok")
        t = feed._ticker
        feed._on_connect(t, None)
        feed._on_close(t, 1006, "upgrade failed (403 - Forbidden)")
        assert t.retry_stopped and not feed.connected and feed._ticker is None
        await __import__("asyncio").sleep(0.05)  # let the scheduled clear run
    pb.redis.delete.assert_awaited_with(kf.TOKEN_KEY)


@pytest.mark.asyncio
async def test_login_stores_token_with_expiry_and_starts():
    feed, pb = make_feed()
    with patch.object(kf, "_sdk", return_value=FAKE_SDK):
        assert await feed.login("rt") is True
    args, kwargs = pb.redis.set.await_args
    assert args == (kf.TOKEN_KEY, "ACCESS") and 0 < kwargs["ex"] <= 24 * 3600


@pytest.mark.asyncio
async def test_start_from_stored_token_and_disconnect_invalidates():
    feed, pb = make_feed()
    pb.redis.get = AsyncMock(return_value=b"STORED")
    FakeKite.invalidated = []
    with patch.object(kf, "_sdk", return_value=FAKE_SDK):
        assert await feed.start_from_stored() is True
        await feed.stop(clear_token=True)
    assert FakeKite.invalidated == ["STORED"]
    pb.redis.delete.assert_awaited_with(kf.TOKEN_KEY)


# ── fallback rule ────────────────────────────────────────────────────

def kite_stub(connected, last_tick_age):
    f = MagicMock()
    f.connected = connected
    f.has_fresh_tick.return_value = last_tick_age is not None and last_tick_age <= 30
    return f


@pytest.mark.asyncio
@pytest.mark.parametrize("connected,age,market_open,cache_full,expect_skip", [
    (True, 5, True, True, True),     # connected + fresh tick -> skip Yahoo
    (True, 45, True, True, False),   # stale -> Yahoo
    (True, None, True, True, False), # no tick yet -> Yahoo
    (False, 1, True, True, False),   # disconnected -> Yahoo
    (True, None, False, True, True), # closed + connected + cache warm -> skip
    (True, None, False, False, False),  # closed but cache expired -> Yahoo refills it
    (False, None, False, True, False),  # closed, disconnected -> Yahoo
])
async def test_kite_covers_rule(connected, age, market_open, cache_full, expect_skip):
    pb = b.PriceBroadcaster()
    pb.kite_feed = kite_stub(connected, age)
    pb.redis = AsyncMock()
    pb.redis.mget = AsyncMock(return_value=["x" if cache_full else None] * len(b.DEFAULT_TICKERS))
    assert await pb._kite_covers(market_open) is expect_skip


@pytest.mark.asyncio
@pytest.mark.parametrize("feed_connected,expect_polls", [(True, 0), (False, 1)])
async def test_poll_loop_skips_or_polls_yahoo(feed_connected, expect_polls):
    import asyncio
    pb = b.PriceBroadcaster()
    pb.kite_feed = kite_stub(feed_connected, 2)
    pb._poll_once = AsyncMock()

    async def stop_sleep(_):
        raise asyncio.CancelledError

    with patch.object(b, "is_market_open", return_value=True), \
         patch.object(b.asyncio, "sleep", stop_sleep):
        await pb._poll_loop()
    assert pb._poll_once.await_count == expect_polls


@pytest.mark.asyncio
async def test_no_kite_feed_always_polls_and_yahoo_ticks_tagged():
    pb = b.PriceBroadcaster()
    assert pb.kite_feed is None
    assert await pb._kite_covers(True) is False
    pb.cache_price = AsyncMock()
    pb.publish_price = AsyncMock()
    with patch("market_data.fetcher.MarketDataFetcher.get_batch_prices",
               return_value={"TCS": {"ticker": "TCS", "price": 1.0}}), \
         patch.object(b, "is_market_open", return_value=True):
        await pb._poll_once()
    assert pb.publish_price.await_args.args[1]["source"] == "yahoo"


# ── feature off ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_unconfigured_feed_is_inert():
    feed, pb = make_feed(configured=False)
    assert not feed.configured
    with patch.object(kf, "_sdk", side_effect=AssertionError("SDK must not be touched")):
        assert await feed.start("x") is False
        assert await feed.login("x") is False
        assert await feed.start_from_stored() is False
    pb.redis.get.assert_not_called()


# ── routes ───────────────────────────────────────────────────────────

@pytest.fixture
def client_and_feed():
    from main import app
    feed, _ = make_feed()
    old = app.state.kite_feed
    app.state.kite_feed = feed
    try:
        yield TestClient(app, follow_redirects=False), feed, app
    finally:
        app.state.kite_feed = old
        app.dependency_overrides.clear()


def test_status_unconfigured_needs_no_auth():
    from main import app
    feed, _ = make_feed(configured=False)
    old = app.state.kite_feed
    app.state.kite_feed = feed
    try:
        r = TestClient(app).get("/api/kite/status")
    finally:
        app.state.kite_feed = old
    assert r.status_code == 200
    assert r.json() == {"configured": False, "connected": False, "source": "yahoo", "last_tick_at": None}


def test_status_connected(client_and_feed):
    client, feed, _ = client_and_feed
    feed.connected = True
    feed.last_tick_at = time.time()
    body = client.get("/api/kite/status").json()
    assert body["configured"] and body["connected"] and body["source"] == "kite" and body["last_tick_at"]


def test_login_and_disconnect_require_auth(client_and_feed):
    client, _, _ = client_and_feed
    assert client.get("/api/kite/login").status_code == 401
    assert client.post("/api/kite/disconnect").status_code == 401


def test_login_redirects_with_api_key_and_state_cookie(client_and_feed):
    from api.dependencies import require_admin
    client, _, app = client_and_feed
    app.dependency_overrides[require_admin] = lambda: MagicMock()
    with patch.object(kf, "_sdk", return_value=FAKE_SDK):
        r = client.get("/api/kite/login")
    assert r.status_code == 302
    loc = r.headers["location"]
    assert loc.startswith("https://kite.example/login?api_key=key&v=3&redirect_params=state%3D")
    state = loc.split("state%3D")[1]
    set_cookie = r.headers["set-cookie"]
    assert f"kite_oauth_state={state}" in set_cookie and "HttpOnly" in set_cookie


def test_callback_failures_redirect_without_leaking(client_and_feed):
    client, feed, _ = client_and_feed
    feed.login = AsyncMock(side_effect=RuntimeError("SECRET-ACCESS-TOKEN"))

    # no state cookie
    r = client.get("/api/kite/callback?request_token=RT&status=success&state=abc")
    assert r.status_code == 302 and r.headers["location"] == "/?kite=error"
    feed.login.assert_not_awaited()

    client.cookies.set("kite_oauth_state", "abc", path="/api/kite")
    # wrong state
    r = client.get("/api/kite/callback?request_token=RT&status=success&state=zzz")
    assert r.headers["location"] == "/?kite=error"
    # Zerodha reported failure
    r = client.get("/api/kite/callback?request_token=RT&status=error&state=abc")
    assert r.headers["location"] == "/?kite=error"
    feed.login.assert_not_awaited()
    # exchange raises: redirect, nothing echoed
    client.cookies.set("kite_oauth_state", "abc", path="/api/kite")
    r = client.get("/api/kite/callback?request_token=RT&status=success&state=abc")
    assert r.headers["location"] == "/?kite=error"
    assert "SECRET-ACCESS-TOKEN" not in r.text and "RT" not in r.headers["location"]
    feed.login.assert_awaited_once_with("RT")


def test_callback_success_redirects_home(client_and_feed):
    client, feed, _ = client_and_feed
    feed.login = AsyncMock(return_value=True)
    client.cookies.set("kite_oauth_state", "abc", path="/api/kite")
    r = client.get("/api/kite/callback?request_token=RT&status=success&state=abc")
    assert r.status_code == 302 and r.headers["location"] == "/"


def test_disconnect_stops_feed(client_and_feed):
    from api.dependencies import require_admin
    client, feed, app = client_and_feed
    app.dependency_overrides[require_admin] = lambda: MagicMock()
    feed.stop = AsyncMock()
    r = client.post("/api/kite/disconnect")
    assert r.status_code == 200
    feed.stop.assert_awaited_once_with(clear_token=True)


def test_callback_honors_frontend_url(client_and_feed):
    import config
    client, feed, _ = client_and_feed
    feed.login = AsyncMock(return_value=True)
    with patch.object(config, "FRONTEND_URL", "http://localhost:5173"):
        client.cookies.set("kite_oauth_state", "abc", path="/api/kite")
        r = client.get("/api/kite/callback?request_token=RT&status=success&state=abc"
                       "&next=http://evil.example")
        assert r.headers["location"] == "http://localhost:5173/"
        client.cookies.set("kite_oauth_state", "abc", path="/api/kite")
        r = client.get("/api/kite/callback?request_token=RT&status=error&state=abc")
        assert r.headers["location"] == "http://localhost:5173/?kite=error"


def test_frontend_url_trailing_slash_stripped(monkeypatch):
    import importlib, config
    monkeypatch.setenv("FRONTEND_URL", "http://localhost:5173/")
    try:
        importlib.reload(config)
        assert config.FRONTEND_URL == "http://localhost:5173"
    finally:
        monkeypatch.delenv("FRONTEND_URL")
        importlib.reload(config)
