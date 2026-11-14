# tests/test_price_endpoint.py
"""Integration tests for the /price/{ticker} endpoint — no DB, no real yfinance."""

import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient, ASGITransport


MOCK_OHLCV = [
    {"time": 1710100000, "open": 2850.0, "high": 2880.0, "low": 2830.0, "close": 2870.12, "volume": 5000000},
    {"time": 1710186400, "open": 2870.0, "high": 2900.0, "low": 2850.0, "close": 2880.46, "volume": 4500000},
]

MOCK_PRICE = {
    "ticker": "RELIANCE",
    "price": 2891.45,
    "previous_close": 2847.30,
    "open": 2855.00,
    "day_high": 2905.10,
    "day_low": 2840.20,
    "volume": 5234100,
    "change_pct": 1.55,
}


@pytest.fixture
def mock_fetcher():
    """Patch MarketDataFetcher methods used by the /price endpoint."""
    with patch("market_data.fetcher.MarketDataFetcher.get_ohlcv", return_value=MOCK_OHLCV), \
         patch("market_data.fetcher.MarketDataFetcher.get_price", return_value=MOCK_PRICE), \
         patch("main.broadcaster.get_cached_price", new_callable=AsyncMock, return_value=None):
        yield


@pytest.mark.asyncio
async def test_root_endpoint(fastapi_app):
    """GET / should return app name and version."""
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["message"] == "NSE Arena API"
    assert "version" in body


@pytest.mark.asyncio
async def test_price_endpoint_returns_200(fastapi_app, mock_fetcher):
    """GET /price/RELIANCE should return 200."""
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/price/RELIANCE")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_price_response_shape(fastapi_app, mock_fetcher):
    """Response must have ticker, current, and ohlcv keys."""
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/price/TCS")
    body = resp.json()
    assert "ticker" in body
    assert "current" in body
    assert "ohlcv" in body


@pytest.mark.asyncio
async def test_price_ohlcv_has_candles(fastapi_app, mock_fetcher):
    """ohlcv should be a non-empty list of candle dicts."""
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/price/INFY")
    body = resp.json()
    assert isinstance(body["ohlcv"], list)
    assert len(body["ohlcv"]) > 0
    candle = body["ohlcv"][0]
    assert "time" in candle
    assert "close" in candle


# ---- range parameter -------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("rng,period,interval", [
    ("1D", "1d", "5m"), ("1W", "5d", "30m"), ("1M", "1mo", "1d"), ("1Y", "1y", "1d"),
])
async def test_range_maps_to_yfinance_args(fastapi_app, rng, period, interval):
    with patch("market_data.fetcher.MarketDataFetcher.get_ohlcv", return_value=MOCK_OHLCV) as m, \
         patch("market_data.fetcher.MarketDataFetcher.get_price", return_value=MOCK_PRICE), \
         patch("main.broadcaster.get_cached_price", new_callable=AsyncMock, return_value=None):
        async with AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as c:
            resp = await c.get(f"/price/RELIANCE?range={rng}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["range"] == rng and body["interval"] == interval
    m.assert_called_once_with("RELIANCE", period=period, interval=interval)


@pytest.mark.asyncio
async def test_range_defaults_to_1m(fastapi_app, mock_fetcher):
    async with AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as c:
        body = (await c.get("/price/RELIANCE")).json()
    assert body["range"] == "1M" and body["interval"] == "1d"


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", ["5Y", "1d", "", "1M;x"])
async def test_invalid_range_is_400(fastapi_app, mock_fetcher, bad):
    async with AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as c:
        resp = await c.get("/price/RELIANCE", params={"range": bad})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_cache_key_and_ttl_per_range(fastapi_app):
    import main
    redis = AsyncMock()
    redis.get.return_value = None
    with patch("market_data.fetcher.MarketDataFetcher.get_ohlcv", return_value=MOCK_OHLCV), \
         patch("market_data.fetcher.MarketDataFetcher.get_price", return_value=MOCK_PRICE), \
         patch("main.broadcaster.get_cached_price", new_callable=AsyncMock, return_value=None), \
         patch.object(main.broadcaster, "redis", redis, create=True), \
         patch("engine.market_calendar.is_market_open", return_value=True):
        async with AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as c:
            for rng in ("1D", "1M"):
                await c.get(f"/price/RELIANCE?range={rng}")
    read_keys = [call.args[0] for call in redis.get.call_args_list]
    assert read_keys == ["ohlcv:RELIANCE:1d", "ohlcv:RELIANCE:1mo"]
    writes = {call.args[0]: call.kwargs["ex"] for call in redis.set.call_args_list}
    assert writes == {"ohlcv:RELIANCE:1d": 30, "ohlcv:RELIANCE:1mo": 60}


def test_intraday_ttl_is_60_when_market_closed():
    import main
    with patch("engine.market_calendar.is_market_open", return_value=False):
        assert main._ohlcv_ttl("1D") == 60
        assert main._ohlcv_ttl("1W") == 60
