# tests/test_trade_endpoint.py
"""Auth guard and validation tests for trade/portfolio endpoints."""

import pytest
from httpx import AsyncClient, ASGITransport


@pytest.mark.asyncio
async def test_trade_requires_auth(fastapi_app):
    """POST /trades without a Bearer token should return 401."""
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/trades", json={
            "ticker": "RELIANCE", "side": "buy", "quantity": 10,
        })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_trade_history_requires_auth(fastapi_app):
    """GET /trades without a Bearer token should return 401."""
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/trades")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_portfolio_requires_auth(fastapi_app):
    """GET /portfolio without a Bearer token should return 401."""
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/portfolio")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_trade_empty_body_still_requires_auth(fastapi_app):
    """POST /trades with empty body and no token should return 401 (auth fires first)."""
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/trades", json={})
    assert resp.status_code == 401
