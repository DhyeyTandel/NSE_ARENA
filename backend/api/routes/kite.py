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
from fastapi.responses import JSONResponse, RedirectResponse

import config
from api.dependencies import require_admin
from market_data import kite_feed as kite_feed_mod

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/kite", tags=["kite"])

STATE_COOKIE = "kite_oauth_state"
STATE_COOKIE_PATH = "/api/kite"
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


@router.get("/login")
async def kite_login(request: Request, user=Depends(require_admin)):
    feed = _feed(request)
    if not feed.configured:
        raise HTTPException(status_code=404, detail="Kite is not configured")
    sdk = kite_feed_mod._sdk()
    if sdk is None:
        raise HTTPException(status_code=503, detail="Kite client unavailable")
    state = secrets.token_urlsafe(24)
    # redirect_params is documented by Kite Connect: a URL-encoded query
    # string that Kite appends to the redirect URL. The SDK's login_url()
    # does not take it, so it is appended here.
    url = sdk[0](api_key=feed.api_key).login_url()
    url += "&redirect_params=" + quote(f"state={state}", safe="")
    response = _redirect(url)
    response.set_cookie(
        key=STATE_COOKIE,
        value=state,
        httponly=True,
        samesite="lax",  # the callback is a cross-site top-level GET
        secure=config.ENV == "production",
        max_age=STATE_TTL_SECONDS,
        path=STATE_COOKIE_PATH,
    )
    return response


@router.get("/callback")
async def kite_callback(
    request: Request,
    request_token: str | None = None,
    status: str | None = None,
    state: str | None = None,
):
    """Validated by the state cookie set in /login (no auth cookie needed:
    the user arrives here via a cross-site redirect from Zerodha)."""
    feed = _feed(request)
    expected = request.cookies.get(STATE_COOKIE)
    ok = bool(
        feed.configured
        and expected
        and state
        and hmac.compare_digest(expected.encode(), state.encode())
        and status == "success"
        and request_token
    )
    if ok:
        try:
            ok = await feed.login(request_token)
        except Exception as e:
            # Never log or echo the exception text: it can carry tokens.
            logger.warning("Kite login failed: %s", type(e).__name__)
            ok = False
    base = config.FRONTEND_URL  # configured value only, never request input
    response = _redirect(f"{base}/" if ok else f"{base}/?kite=error")
    response.delete_cookie(STATE_COOKIE, path=STATE_COOKIE_PATH)
    return response


@router.post("/disconnect")
async def kite_disconnect(request: Request, user=Depends(require_admin)):
    await _feed(request).stop(clear_token=True)
    return {"ok": True}
