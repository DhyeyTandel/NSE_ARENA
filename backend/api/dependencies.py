# api/dependencies.py
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from config import SECRET_KEY, ALGORITHM

AUTH_COOKIE_NAME = "access_token"
MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def _extract_token(request: Request, bearer_token: str | None) -> str | None:
    """Prefer the Bearer header (API clients, tests); fall back to the
    httpOnly auth cookie (browser clients).

    CSRF: a cross-site page can make the browser send our cookie on a
    top-level form POST, but it cannot set a custom header. So when auth
    comes from the cookie on a mutating request, require the
    X-Requested-With header the frontend always sends. Bearer-header auth
    is immune (an attacker can't forge that header cross-site), so it
    skips the check.
    """
    if bearer_token:
        return bearer_token

    cookie_token = request.cookies.get(AUTH_COOKIE_NAME)
    if not cookie_token:
        return None

    if request.method in MUTATING_METHODS:
        if request.headers.get("x-requested-with") != "XMLHttpRequest":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Missing X-Requested-With header",
            )
    return cookie_token


async def get_current_user(
    request: Request,
    bearer_token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    token = _extract_token(request, bearer_token)
    if not token:
        raise credentials_exception
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    from sqlalchemy import select
    from db.models import User
    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    return user


async def get_current_user_optional(
    request: Request,
    bearer_token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    """Returns user if authenticated, None otherwise (no 401)."""
    try:
        token = _extract_token(request, bearer_token)
    except HTTPException:
        return None
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            return None
    except JWTError:
        return None

    from sqlalchemy import select
    from db.models import User
    result = await db.execute(select(User).where(User.id == int(user_id)))
    return result.scalar_one_or_none()
