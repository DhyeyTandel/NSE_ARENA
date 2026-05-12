# api/routes/scripts.py
"""
API endpoints for the PineScript-lite scripting engine.
"""
import asyncio
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from database import async_session
from api.dependencies import get_current_user_optional, get_current_user
from market_data.fetcher import MarketDataFetcher
from scripting.engine import run_script

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/scripts", tags=["scripts"])

SCRIPT_TIMEOUT = 10  # seconds max execution


# ── Request / Response models ───────────────────────────────────────────────

class RunScriptRequest(BaseModel):
    code: str
    ticker: str = "RELIANCE"
    period: str = "3mo"   # yfinance period: 1mo, 3mo, 6mo, 1y, 2y
    interval: str = "1d"  # yfinance interval: 1m, 5m, 15m, 1h, 1d


class SaveScriptRequest(BaseModel):
    name: str
    code: str


# ── Built-in templates ──────────────────────────────────────────────────────

TEMPLATES = [
    {
        "name": "RSI Oscillator",
        "description": "Classic RSI with overbought/oversold levels",
        "code": """//@version=5
indicator("RSI", overlay=false)

// RSI calculation
rsiLength = 14
rsiValue = ta.rsi(close, rsiLength)

// Plot RSI line
plot(rsiValue, title="RSI", color=color.purple)

// Overbought / Oversold levels
hline(70, title="Overbought", color=color.red)
hline(30, title="Oversold", color=color.green)
hline(50, title="Midline", color=color.gray)
""",
    },
    {
        "name": "MACD Crossover",
        "description": "MACD line, signal, and histogram",
        "code": """//@version=5
indicator("MACD", overlay=false)

// MACD calculation
[macdLine, signalLine, hist] = ta.macd(close, 12, 26, 9)

// Plot
plot(macdLine, title="MACD", color=color.blue)
plot(signalLine, title="Signal", color=color.orange)
plot(hist, title="Histogram", color=color.gray, style=plot.style_histogram)

// Zero line
hline(0, title="Zero", color=color.gray)
""",
    },
    {
        "name": "Bollinger Bands",
        "description": "Price bands with upper, middle, and lower levels",
        "code": """//@version=5
indicator("Bollinger Bands", overlay=true)

// Bollinger Bands calculation
length = 20
mult = 2.0
[upper, middle, lower] = ta.bbands(close, length, mult)

// Plot bands
plot(upper, title="Upper Band", color=color.red)
plot(middle, title="Middle Band", color=color.gray)
plot(lower, title="Lower Band", color=color.green)
""",
    },
    {
        "name": "SMA Crossover",
        "description": "20 SMA vs 50 SMA — classic trend-following strategy",
        "code": """//@version=5
indicator("SMA Crossover", overlay=true)

// Moving averages
fast = ta.sma(close, 20)
slow = ta.sma(close, 50)

// Plot both lines
plot(fast, title="SMA 20", color=color.green)
plot(slow, title="SMA 50", color=color.red)
""",
    },
    {
        "name": "VWAP",
        "description": "Volume Weighted Average Price",
        "code": """//@version=5
indicator("VWAP", overlay=true)

// VWAP calculation
vwapValue = ta.vwap(close, volume)

// Plot
plot(vwapValue, title="VWAP", color=color.blue, linewidth=2)
""",
    },
    {
        "name": "EMA Ribbon",
        "description": "Multiple EMAs creating a visual ribbon",
        "code": """//@version=5
indicator("EMA Ribbon", overlay=true)

// EMA ribbon
ema8 = ta.ema(close, 8)
ema13 = ta.ema(close, 13)
ema21 = ta.ema(close, 21)
ema34 = ta.ema(close, 34)
ema55 = ta.ema(close, 55)

// Plot ribbon
plot(ema8, title="EMA 8", color=color.green)
plot(ema13, title="EMA 13", color=color.lime)
plot(ema21, title="EMA 21", color=color.yellow)
plot(ema34, title="EMA 34", color=color.orange)
plot(ema55, title="EMA 55", color=color.red)
""",
    },
    {
        "name": "Stochastic RSI",
        "description": "Stochastic oscillator applied to RSI values",
        "code": """//@version=5
indicator("Stochastic RSI", overlay=false)

// Calculate RSI first
rsiValue = ta.rsi(close, 14)

// Then apply Stochastic to RSI
stochRsi = ta.stoch(rsiValue, rsiValue, rsiValue, 14)
smoothK = ta.sma(stochRsi, 3)

// Plot
plot(smoothK, title="%K", color=color.blue)
hline(80, title="Overbought", color=color.red)
hline(20, title="Oversold", color=color.green)
hline(50, title="Midline", color=color.gray)
""",
    },
    {
        "name": "ATR Volatility",
        "description": "Average True Range — measures market volatility",
        "code": """//@version=5
indicator("ATR", overlay=false)

// ATR calculation
atrLength = 14
atrValue = ta.atr(high, low, close, atrLength)

// Plot
plot(atrValue, title="ATR", color=color.orange, linewidth=2)
""",
    },
]


# ── Endpoints ───────────────────────────────────────────────────────────────

@router.post("/run")
async def run_user_script(req: RunScriptRequest):
    """Execute a PineScript-lite program against market data."""
    if not req.code.strip():
        raise HTTPException(400, "Script code is empty")
    if len(req.code) > 10_000:
        raise HTTPException(400, "Script too long (max 10,000 characters)")

    # Fetch OHLCV data
    try:
        ohlcv = await asyncio.to_thread(
            MarketDataFetcher.get_ohlcv, req.ticker, req.period
        )
    except Exception as e:
        logger.warning("Failed to fetch data for %s: %s", req.ticker, e)
        raise HTTPException(502, f"Could not fetch market data for {req.ticker}")

    if not ohlcv:
        raise HTTPException(404, f"No data available for {req.ticker}")

    timestamps = [bar["time"] for bar in ohlcv]

    # Execute script with timeout
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(run_script, req.code, ohlcv, timestamps),
            timeout=SCRIPT_TIMEOUT,
        )
    except asyncio.TimeoutError:
        raise HTTPException(408, "Script execution timed out (10s limit)")
    except Exception as e:
        raise HTTPException(500, f"Script execution error: {str(e)}")

    return {
        "indicator_title": result.indicator_title,
        "plots": [
            {
                "title": p.title,
                "data": p.data,
                "color": p.color,
                "style": p.style,
                "linewidth": p.linewidth,
                "pane": p.pane,
            }
            for p in result.plots
        ],
        "hlines": [
            {"price": h.price, "title": h.title, "color": h.color,
             "linestyle": h.linestyle}
            for h in result.hlines
        ],
        "ohlcv": ohlcv,
        "logs": result.logs,
        "errors": result.errors,
        "bars": len(ohlcv),
    }


@router.get("/templates")
async def get_templates():
    """Return built-in script templates."""
    return [
        {"name": t["name"], "description": t["description"], "code": t["code"]}
        for t in TEMPLATES
    ]


@router.post("/save")
async def save_script(req: SaveScriptRequest,
                      user=Depends(get_current_user)):
    """Save a user's script."""
    from db.models import UserScript

    async with async_session() as db:
        script = UserScript(
            user_id=user.id,
            name=req.name,
            code=req.code,
        )
        db.add(script)
        await db.commit()
        await db.refresh(script)
        return {
            "id": script.id,
            "name": script.name,
            "created_at": str(script.created_at),
        }


@router.get("/mine")
async def get_my_scripts(user=Depends(get_current_user)):
    """Get all scripts saved by the current user."""
    from db.models import UserScript

    async with async_session() as db:
        result = await db.execute(
            select(UserScript)
            .where(UserScript.user_id == user.id)
            .order_by(UserScript.updated_at.desc())
        )
        scripts = result.scalars().all()
        return [
            {
                "id": s.id,
                "name": s.name,
                "code": s.code,
                "created_at": str(s.created_at),
                "updated_at": str(s.updated_at),
            }
            for s in scripts
        ]
