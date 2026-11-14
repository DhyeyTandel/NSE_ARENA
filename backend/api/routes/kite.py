# api/routes/kite.py
"""Zerodha Kite Connect login flow for the optional real-time feed.

Read-only market data only: nothing here can place, modify or cancel a
real order. See market_data/kite_feed.py.
"""
import hmac
import logging
import secrets
from datetime import datetime, timezone
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse

import config
from api.dependencies import require_admin
from api.rate_limit import check_rate_limit, client_ip
from market_data import kite_feed as kite_feed_mod

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/kite", tags=["kite"])

STATE_KEY_PREFIX = "kite_oauth_state:"
STATE_TTL_SECONDS = 600


def _feed(request: Request):
    return request.app.state.kite_feed


def _redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url, status_code=302)


@router.get("/status")
async def kite_status(request: Request):
    feed = _feed(request)
    connected = bool(feed.connected)
    last = feed.last_tick_at
    return {
        "configured": feed.configured,
        "connected": connected,
        "source": "kite" if connected else "yahoo",
        "last_tick_at": (
            datetime.fromtimestamp(last, tz=timezone.utc).isoformat() if last else None
        ),
    }


async def _limit_login(request: Request):
    await check_rate_limit(request, bucket="kite_login", identity=client_ip(request),
                           limit=10, window_seconds=60)


async def _limit_callback(request: Request):
    await check_rate_limit(request, bucket="kite_callback", identity=client_ip(request),
                           limit=10, window_seconds=60)


def _redis(request: Request):
    return request.app.state.broadcaster.redis


@router.get("/login", dependencies=[Depends(_limit_login)])
async def kite_login(request: Request, user=Depends(require_admin)):
    feed = _feed(request)
    if not feed.configured:
        raise HTTPException(status_code=404, detail="Kite is not configured")
    sdk = kite_feed_mod._sdk()
    if sdk is None:
        raise HTTPException(status_code=503, detail="Kite client unavailable")
    state = secrets.token_urlsafe(24)
    # Single-use, short-lived, bound to the admin who started the login.
    try:
        await _redis(request).set(STATE_KEY_PREFIX + state, str(user.id), ex=STATE_TTL_SECONDS)
    except Exception as e:
        logger.warning("Kite login state not stored: %s", type(e).__name__)
        raise HTTPException(status_code=503, detail="Kite login temporarily unavailable")
    # redirect_params is documented by Kite Connect: a URL-encoded query
    # string that Kite appends to the redirect URL. The SDK's login_url()
    # does not take it, so it is appended here.
    url = sdk[0](api_key=feed.api_key).login_url()
    url += "&redirect_params=" + quote(f"state={state}", safe="")
    return _redirect(url)


async def _consume_state(request: Request, state: str | None, user_id) -> bool:
    """Atomically take the state (GETDEL): usable once, by the admin that
    created it. Any miss, mismatch or Redis error is a rejection."""
    if not state or len(state) > 128:
        return False
    try:
        stored = await _redis(request).getdel(STATE_KEY_PREFIX + state)
    except Exception as e:
        logger.warning("Kite state check failed: %s", type(e).__name__)
        return False
    if stored is None:
        return False
    if isinstance(stored, bytes):
        stored = stored.decode()
    return hmac.compare_digest(str(stored).encode(), str(user_id).encode())


@router.get("/callback", dependencies=[Depends(_limit_callback)])
async def kite_callback(
    request: Request,
    request_token: str | None = None,
    status: str | None = None,
    state: str | None = None,
    user=Depends(require_admin),
):
    """Admin only. The browser arrives via a top-level redirect from Zerodha,
    so the SameSite=Lax auth cookie is sent; this is a GET, so the
    X-Requested-With CSRF check (mutating methods only) does not apply. The
    server-side state, consumed here, ties the callback to a login this
    admin started."""
    feed = _feed(request)
    # Consume first so the state is spent even when the rest fails.
    ok = await _consume_state(request, state, user.id)
    ok = bool(ok and feed.configured and status == "success" and request_token)
    if ok:
        try:
            ok = await feed.login(request_token)
        except Exception as e:
            # Never log or echo the exception text: it can carry tokens.
            logger.warning("Kite login failed: %s", type(e).__name__)
            ok = False
    base = config.FRONTEND_URL  # configured value only, never request input
    return _redirect(f"{base}/" if ok else f"{base}/?kite=error")


@router.post("/disconnect")
async def kite_disconnect(request: Request, user=Depends(require_admin)):
    try:
        await _feed(request).stop(clear_token=True)
    except Exception as e:
        logger.warning("Kite disconnect failed: %s", type(e).__name__)
        raise HTTPException(status_code=503, detail="Kite disconnect temporarily unavailable")
    return {"ok": True}
