# api/routes/auth.py
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
from pydantic import BaseModel
from typing import Optional

from database import get_db
from db.models import User, Portfolio, Season
from api.dependencies import get_current_user, AUTH_COOKIE_NAME
from api.rate_limit import check_rate_limit, client_ip
import config
from config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, STARTING_CAPITAL

router = APIRouter(prefix="/auth", tags=["auth"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def set_auth_cookie(response: Response, token: str) -> None:
    """httpOnly auth cookie for browser clients. Secure only in production
    because Safari refuses Secure cookies over plain-http localhost dev."""
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=config.ENV == "production",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )


class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Optional[dict] = None


def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


@router.post("/register", response_model=TokenResponse)
async def register(request: RegisterRequest, http_request: Request, response: Response,
                   db: AsyncSession = Depends(get_db)):
    await check_rate_limit(
        http_request, bucket="register", identity=client_ip(http_request),
        limit=3, window_seconds=3600
    )

    # Check if username exists
    result = await db.execute(select(User).where(User.username == request.username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already registered")

    # Check if email exists
    result = await db.execute(select(User).where(User.email == request.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    # Create user
    user = User(
        username=request.username,
        email=request.email,
        hashed_password=pwd_context.hash(request.password),
    )
    db.add(user)
    await db.flush()

    # Get active season
    result = await db.execute(select(Season).where(Season.is_active == True))
    season = result.scalar_one_or_none()
    if not season:
        raise HTTPException(status_code=400, detail="No active season found. Registration is currently closed.")

    # Create portfolio for this season
    portfolio = Portfolio(
        user_id=user.id,
        season_id=season.id,
        cash_balance=STARTING_CAPITAL,
    )
    db.add(portfolio)
    await db.commit()

    token = create_access_token(data={"sub": str(user.id)})
    set_auth_cookie(response, token)
    user_info = _user_to_dict(user)
    return TokenResponse(access_token=token, user=user_info)


@router.post("/login", response_model=TokenResponse)
async def login(http_request: Request,
                response: Response,
                form_data: OAuth2PasswordRequestForm = Depends(),
                db: AsyncSession = Depends(get_db)):
    await check_rate_limit(
        http_request, bucket="login", identity=client_ip(http_request),
        limit=5, window_seconds=60
    )

    result = await db.execute(select(User).where(User.username == form_data.username))
    user = result.scalar_one_or_none()

    if not user or not pwd_context.verify(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(data={"sub": str(user.id)})
    set_auth_cookie(response, token)
    return TokenResponse(access_token=token)


@router.post("/login/json", response_model=TokenResponse)
async def login_json(request: LoginRequest, http_request: Request, response: Response,
                     db: AsyncSession = Depends(get_db)):
    """JSON-body login alternative (used by the frontend)"""
    # Same "login" bucket as /auth/login — otherwise an attacker just
    # switches endpoints to dodge the limit.
    await check_rate_limit(
        http_request, bucket="login", identity=client_ip(http_request),
        limit=5, window_seconds=60
    )

    result = await db.execute(select(User).where(User.username == request.username))
    user = result.scalar_one_or_none()

    if not user or not pwd_context.verify(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    token = create_access_token(data={"sub": str(user.id)})
    set_auth_cookie(response, token)
    user_info = _user_to_dict(user)
    return TokenResponse(access_token=token, user=user_info)


@router.post("/logout")
async def logout(response: Response):
    """Clear the httpOnly auth cookie. No CSRF/auth requirement — logging
    someone out is not a damaging action and requiring auth would strand
    clients holding an expired token."""
    response.delete_cookie(key=AUTH_COOKIE_NAME, path="/")
    return {"status": "logged out"}


@router.get("/me")
async def get_current_user_info(user: User = Depends(get_current_user)):
    """Validate token and return current user info"""
    return _user_to_dict(user)


def _user_to_dict(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "initials": user.username[:2].upper(),
        "is_ai": user.is_ai,
    }
