# api/routes/ai.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db
from db.models import AIDecision

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/decisions")
async def get_ai_decisions(
    limit: int = 20,
    db: AsyncSession = Depends(get_db)
):
    """Get recent AI agent decisions for the feed"""
    result = await db.execute(
        select(AIDecision)
        .order_by(AIDecision.created_at.desc())
        .limit(limit)
    )
    decisions = result.scalars().all()

    return [
        {
            "id": d.id,
            "action": d.action,
            "ticker": d.ticker,
            "quantity": d.quantity,
            "reasoning": d.reasoning,
            "confidence": d.confidence,
            "guardrail_status": d.guardrail_status,
            "guardrail_reason": d.guardrail_reason,
            "stop_loss_price": d.stop_loss_price,
            "position_size_pct": d.position_size_pct,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in decisions
    ]
