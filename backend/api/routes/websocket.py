# api/routes/websocket.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt
import asyncio
import json
import logging

from api.dependencies import AUTH_COOKIE_NAME
from config import SECRET_KEY, ALGORITHM

logger = logging.getLogger(__name__)
router = APIRouter()

# Track connected clients for in-process fan-out (one shared Redis
# subscription feeds all of them — see start_price_fanout below).
connected_clients: list[WebSocket] = []

MAX_TOTAL_CONNECTIONS = 500
MAX_CONNECTIONS_PER_IP = 5
AUTH_TIMEOUT_SECONDS = 5.0

_ip_connection_counts: dict[str, int] = {}


def _client_ip(websocket: WebSocket) -> str:
    forwarded = websocket.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return websocket.client.host if websocket.client else "unknown"


def _valid_token(token: str) -> bool:
    try:
        claims = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return bool(claims.get("sub"))
    except JWTError:
        return False


async def _authenticate(websocket: WebSocket) -> bool:
    """Browser clients authenticate via the httpOnly auth cookie sent with
    the handshake. Non-browser clients may instead send a valid JWT as the
    first message frame (not a query param, since query params end up in
    access logs). Closes with 4401 on timeout, malformed payload, or an
    invalid/expired token."""
    cookie_token = websocket.cookies.get(AUTH_COOKIE_NAME)
    if cookie_token and _valid_token(cookie_token):
        return True

    try:
        raw = await asyncio.wait_for(websocket.receive_text(), timeout=AUTH_TIMEOUT_SECONDS)
        payload = json.loads(raw)
        return _valid_token(payload.get("token", ""))
    except (asyncio.TimeoutError, ValueError, json.JSONDecodeError, WebSocketDisconnect):
        return False


@router.websocket("/ws/prices")
async def websocket_prices(websocket: WebSocket):
    """
    WebSocket endpoint for live price streaming.
    Requires a valid JWT as the first message frame. Live updates are
    fanned out in-process from a single shared Redis subscription
    (start_price_fanout) rather than one subscription per socket.
    """
    await websocket.accept()

    if len(connected_clients) >= MAX_TOTAL_CONNECTIONS:
        await websocket.close(code=4429, reason="Too many connections")
        return

    client_ip = _client_ip(websocket)
    if _ip_connection_counts.get(client_ip, 0) >= MAX_CONNECTIONS_PER_IP:
        await websocket.close(code=4429, reason="Too many connections from this IP")
        return

    if not await _authenticate(websocket):
        await websocket.close(code=4401, reason="Unauthorized")
        return

    connected_clients.append(websocket)
    _ip_connection_counts[client_ip] = _ip_connection_counts.get(client_ip, 0) + 1
    logger.info("WebSocket client connected. Total clients: %d", len(connected_clients))

    broadcaster = websocket.app.state.broadcaster

    try:
        # Send all cached prices immediately on connect
        cached_prices = await broadcaster.get_all_cached_prices()
        for ticker, price_data in cached_prices.items():
            await websocket.send_json(price_data)

        # Live updates arrive via broadcast_price_update() from the shared
        # fan-out task — just keep the socket open until the client
        # disconnects.
        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.warning("WebSocket error: %s", e)
    finally:
        if websocket in connected_clients:
            connected_clients.remove(websocket)
        remaining = _ip_connection_counts.get(client_ip, 1) - 1
        if remaining <= 0:
            _ip_connection_counts.pop(client_ip, None)
        else:
            _ip_connection_counts[client_ip] = remaining
        logger.info("WebSocket cleanup done. Remaining clients: %d", len(connected_clients))


async def broadcast_price_update(price_data: dict):
    """Broadcast a price update to all connected clients (in-process fan-out)"""
    disconnected = []
    for client in connected_clients:
        try:
            await client.send_json(price_data)
        except Exception:
            disconnected.append(client)

    for client in disconnected:
        if client in connected_clients:
            connected_clients.remove(client)


async def start_price_fanout(broadcaster) -> asyncio.Task:
    """Subscribe to Redis once for the whole process and fan out to all
    connected WebSocket clients in-process, instead of each socket opening
    its own Redis pub/sub subscription."""
    async def _loop():
        pubsub = await broadcaster.subscribe()
        try:
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message["type"] == "message":
                    await broadcast_price_update(json.loads(message["data"]))
                else:
                    await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            pass
        finally:
            await pubsub.close()

    return asyncio.create_task(_loop())
