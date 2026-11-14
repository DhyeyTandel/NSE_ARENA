# api/token_revocation.py
"""JWT revocation list backed by Redis (the broadcaster's connection).

Logout stores the token's `jti` under `jwt:revoked:<jti>` with a TTL equal
to the token's remaining lifetime, so the entry vanishes exactly when the
token would have expired anyway. No DB schema involved.

Fails open: if Redis is unreachable a revoked token keeps working (and a
single warning is logged) rather than locking every user out. Tokens
issued before `jti` existed have no id and are accepted until they expire.
"""
import logging
import time

logger = logging.getLogger(__name__)

KEY_PREFIX = "jwt:revoked:"
_warned = False


def _warn_once(action: str, err: Exception) -> None:
    global _warned
    if not _warned:
        _warned = True
        logger.warning("Token revocation %s unavailable, failing open "
                       "(logout will not invalidate tokens): %s", action, err)


def _redis(app):
    return app.state.broadcaster.redis


async def is_revoked(app, claims: dict) -> bool:
    jti = claims.get("jti")
    if not jti:
        return False
    try:
        value = await _redis(app).get(KEY_PREFIX + str(jti))
    except Exception as e:
        _warn_once("check", e)
        return False
    return value in (b"1", "1")


async def revoke(app, claims: dict) -> bool:
    """Revoke the token described by `claims`. Returns True if stored."""
    jti = claims.get("jti")
    exp = claims.get("exp")
    if not jti or exp is None:
        return False
    ttl = int(exp - time.time())
    if ttl <= 0:
        return False
    try:
        await _redis(app).set(KEY_PREFIX + str(jti), "1", ex=ttl)
        return True
    except Exception as e:
        _warn_once("revoke", e)
        return False
