# api/rate_limit.py
"""Redis-backed fixed-window rate limiting.

Reuses the Redis connection already held by the shared PriceBroadcaster
(app.state.broadcaster.redis) instead of opening a second connection.

Fails open (allows the request through) if Redis is unreachable or the
check itself errors — matches the app's existing "degrade gracefully
without Redis" posture for price streaming, and means a Redis outage
doesn't also take down login/registration/scripts.
"""
import logging
import time

from fastapi import HTTPException, Request, status

logger = logging.getLogger(__name__)


def client_ip(request: Request) -> str:
    """Forwarded client IP if behind a proxy, else the direct peer IP."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def check_rate_limit(request: Request, bucket: str, identity: str,
                            limit: int, window_seconds: int) -> None:
    """Raise 429 if `identity` has made more than `limit` requests to
    `bucket` within the current fixed window."""
    key = f"ratelimit:{bucket}:{identity}:{int(time.time() // window_seconds)}"
    try:
        redis_client = request.app.state.broadcaster.redis
        current = await redis_client.incr(key)
        if current == 1:
            await redis_client.expire(key, window_seconds)
        exceeded = current > limit
    except Exception as e:
        logger.warning("Rate limiter error for key=%s, failing open: %s", key, e)
        return

    if exceeded:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please try again later.",
        )
