# api/routes/websocket.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
import asyncio
import json
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

# Track connected clients
connected_clients: list[WebSocket] = []


@router.websocket("/ws/prices")
async def websocket_prices(websocket: WebSocket):
    """
    WebSocket endpoint for live price streaming.
    Subscribes to Redis pub/sub and forwards price updates to the client.
    On connect, sends all cached prices immediately.
    """
    await websocket.accept()
    connected_clients.append(websocket)
    logger.info("WebSocket client connected. Total clients: %d", len(connected_clients))

    # Import broadcaster lazily to avoid circular imports
    from market_data.broadcaster import PriceBroadcaster
    broadcaster = PriceBroadcaster()

    try:
        # Send all cached prices immediately on connect
        cached_prices = await broadcaster.get_all_cached_prices()
        for ticker, price_data in cached_prices.items():
            await websocket.send_json(price_data)

        # Subscribe to Redis pub/sub for live updates
        pubsub = await broadcaster.subscribe()

        # Listen for new price updates from Redis
        while True:
            message = await pubsub.get_message(
                ignore_subscribe_messages=True,
                timeout=1.0
            )

            if message and message["type"] == "message":
                price_data = json.loads(message["data"])
                await websocket.send_json(price_data)

            # Small sleep to prevent busy-waiting
            await asyncio.sleep(0.1)

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.warning("WebSocket error: %s", e)
    finally:
        if websocket in connected_clients:
            connected_clients.remove(websocket)
        await broadcaster.close()
        logger.info("WebSocket cleanup done. Remaining clients: %d", len(connected_clients))


async def broadcast_price_update(price_data: dict):
    """Broadcast a price update to all connected clients (direct, non-Redis path)"""
    disconnected = []
    for client in connected_clients:
        try:
            await client.send_json(price_data)
        except Exception:
            disconnected.append(client)

    for client in disconnected:
        if client in connected_clients:
            connected_clients.remove(client)
