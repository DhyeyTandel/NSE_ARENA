# api/routes/seasons.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from database import get_db
from db.models import Season

router = APIRouter(prefix="/seasons", tags=["seasons"])


@router.get("/active")
async def get_active_season(db: AsyncSession = Depends(get_db)):
    """Get the current active season info"""
    result = await db.execute(select(Season).where(Season.is_active == True))
    season = result.scalar_one_or_none()

    if not season:
        return None

    now = datetime.utcnow()
    days_remaining = max(0, (season.end_date - now).days)
    total_days = max(1, (season.end_date - season.start_date).days)
    days_elapsed = total_days - days_remaining

    return {
        "id": season.id,
        "name": season.name,
        "start_date": season.start_date.isoformat(),
        "end_date": season.end_date.isoformat(),
        "starting_capital": season.starting_capital,
        "days_remaining": days_remaining,
        "days_elapsed": days_elapsed,
        "total_days": total_days,
        "is_active": season.is_active,
    }


@router.get("")
async def get_all_seasons(db: AsyncSession = Depends(get_db)):
    """Get all seasons (for history display)"""
    result = await db.execute(
        select(Season).order_by(Season.start_date.desc())
    )
    seasons = result.scalars().all()

    return [
        {
            "id": s.id,
            "name": s.name,
            "start_date": s.start_date.isoformat(),
            "end_date": s.end_date.isoformat(),
            "starting_capital": s.starting_capital,
            "is_active": s.is_active,
        }
        for s in seasons
    ]
