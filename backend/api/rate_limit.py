# api/rate_limit.py
"""Redis-backed fixed-window rate limiting.

Reuses the Redis connection already held by the shared PriceBroadcaster
(app.state.broadcaster.redis) instead of opening a second connection.

Fails open (allows the request through) if Redis is unreachable or the
check itself errors — matches the app's existing "degrade gracefully
without Redis" posture for price streaming, and means a Redis outage
doesn't also take down login/registration/scripts.
"""
import ipaddress
import logging
import time

from fastapi import HTTPException, Request, status
from starlette.requests import HTTPConnection

logger = logging.getLogger(__name__)


def _parse_ip(value: str):
    try:
        ip = ipaddress.ip_address(value.strip())
    except ValueError:
        return None
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        return ip.ipv4_mapped
    return ip


def _is_internal(ip) -> bool:
    return ip.is_private or ip.is_loopback or ip.is_link_local


def resolve_client_ip(peer_host: str | None, forwarded_for: str | None) -> str:
    """The single place that decides which IP a request "comes from".

    X-Forwarded-For is only honoured when the direct socket peer is itself
    a private/loopback address, i.e. our reverse proxy (Caddy container).
    A peer on a public address is the client, and any header it sent is
    ignored. Behind the proxy the header is read right to left, skipping
    internal hops, so entries a client prepended cannot win. If the header
    is malformed (any entry not an IP) the socket peer is used.

    Deployment assumption: Caddy runs with `trusted_proxies static
    private_ranges` (see Caddyfile) so it overwrites a forwarded IP sent
    by a public peer.
    """
    if not peer_host:
        return "unknown"
    peer = _parse_ip(peer_host)
    if peer is None or not _is_internal(peer) or not forwarded_for:
        return str(peer) if peer is not None else peer_host

    hops = [_parse_ip(part) for part in forwarded_for.split(",")]
    if not hops or any(h is None for h in hops):
        return str(peer)
    for hop in reversed(hops):
        if not _is_internal(hop):
            return str(hop)
    return str(hops[0])  # every hop internal (e.g. a LAN/tailnet ULA client)


def client_ip(conn: HTTPConnection) -> str:
    """Client IP for an HTTP Request or a WebSocket (both HTTPConnection)."""
    peer = conn.client.host if conn.client else None
    return resolve_client_ip(peer, conn.headers.get("x-forwarded-for"))


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
