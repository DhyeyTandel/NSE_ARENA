# tests/test_websocket_auth.py
"""Item 4 (ANTIGRAVITY_NEXT.md): WebSocket auth + resource bounds.

/ws/prices previously had no auth check at all and let each client open
its own Redis pub/sub subscription. Now: the client must send a valid JWT
as its first message frame within AUTH_TIMEOUT_SECONDS (closing with 4401
otherwise), and both a total connection cap and a per-IP cap bound the
number of open sockets.
"""
import json
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from main import app
from api.routes import websocket as ws_module
from api.routes.auth import create_access_token


def _fresh_client():
    """A TestClient with a mocked broadcaster and clean connection-tracking
    state (module-level dicts persist across tests otherwise)."""
    app.state.broadcaster = AsyncMock()
    app.state.broadcaster.get_all_cached_prices = AsyncMock(return_value={})
    ws_module.connected_clients.clear()
    ws_module._ip_connection_counts.clear()
    return TestClient(app)


def test_ws_closes_unauthenticated_socket_with_missing_token():
    client = _fresh_client()
    with patch.object(ws_module, "AUTH_TIMEOUT_SECONDS", 0.05):
        with client.websocket_connect("/ws/prices") as ws:
            # Send nothing — the handshake should time out and close 4401.
            data = ws.receive()
    assert data["type"] == "websocket.close"
    assert data["code"] == 4401


def test_ws_closes_socket_with_invalid_token():
    client = _fresh_client()
    with client.websocket_connect("/ws/prices") as ws:
        ws.send_text(json.dumps({"token": "not-a-real-jwt"}))
        data = ws.receive()
    assert data["type"] == "websocket.close"
    assert data["code"] == 4401


def test_ws_accepts_valid_token():
    client = _fresh_client()
    token = create_access_token({"sub": "1"})
    with client.websocket_connect("/ws/prices") as ws:
        ws.send_text(json.dumps({"token": token}))
        # Connection should stay open (no close frame) — closing the `with`
        # block disconnects cleanly from the client side instead.
    assert ws_module.connected_clients == []  # cleaned up after disconnect


def test_ws_rejects_connection_beyond_per_ip_cap():
    client = _fresh_client()
    token = create_access_token({"sub": "1"})

    with patch.object(ws_module, "MAX_CONNECTIONS_PER_IP", 2):
        with client.websocket_connect("/ws/prices") as ws1:
            ws1.send_text(json.dumps({"token": token}))
            with client.websocket_connect("/ws/prices") as ws2:
                ws2.send_text(json.dumps({"token": token}))
                # Third connection from the same (test) client IP should be
                # rejected outright, before even reaching the auth step.
                with client.websocket_connect("/ws/prices") as ws3:
                    data = ws3.receive()
                    assert data["type"] == "websocket.close"
                    assert data["code"] == 4429
