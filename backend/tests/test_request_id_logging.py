# tests/test_request_id_logging.py
"""Priority E item 5: structured (JSON) logging with a per-request
correlation ID, so log lines from every module touched during one
request can be grepped/joined by request_id in a log aggregator.
"""
import json
import logging

import pytest
from httpx import AsyncClient, ASGITransport

from main import app
from logging_setup import JSONFormatter, RequestIdFilter, request_id_var


@pytest.mark.asyncio
async def test_response_includes_a_generated_request_id():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/")
        assert "X-Request-ID" in resp.headers
        assert len(resp.headers["X-Request-ID"]) > 0


@pytest.mark.asyncio
async def test_incoming_request_id_is_echoed_back_unchanged():
    """A reverse proxy or caller that already generated a correlation ID
    should have it preserved end-to-end, not overwritten."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/", headers={"X-Request-ID": "caller-supplied-id-123"})
        assert resp.headers["X-Request-ID"] == "caller-supplied-id-123"


@pytest.mark.asyncio
async def test_two_requests_without_a_header_get_different_ids():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r1 = await client.get("/")
        r2 = await client.get("/")
        assert r1.headers["X-Request-ID"] != r2.headers["X-Request-ID"]


def test_json_formatter_embeds_the_current_request_id():
    token = request_id_var.set("abc-123")
    try:
        record = logging.LogRecord(
            name="test.logger", level=logging.INFO, pathname=__file__,
            lineno=1, msg="something happened", args=None, exc_info=None,
        )
        RequestIdFilter().filter(record)
        payload = json.loads(JSONFormatter().format(record))
    finally:
        request_id_var.reset(token)

    assert payload["request_id"] == "abc-123"
    assert payload["message"] == "something happened"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "test.logger"


def test_json_formatter_defaults_to_a_placeholder_outside_a_request():
    record = logging.LogRecord(
        name="test.logger", level=logging.INFO, pathname=__file__,
        lineno=1, msg="background task log", args=None, exc_info=None,
    )
    RequestIdFilter().filter(record)
    payload = json.loads(JSONFormatter().format(record))
    assert payload["request_id"] == "-"
