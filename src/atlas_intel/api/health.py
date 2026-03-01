"""Health check endpoint."""

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.database import get_session
from atlas_intel.models.company import Company
from atlas_intel.models.filing import Filing
from atlas_intel.models.financial_fact import FinancialFact

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check(session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    """Health check with database stats."""
    try:
        await session.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    stats = {}
    if db_ok:
        companies = (await session.execute(select(func.count(Company.id)))).scalar() or 0
        filings = (await session.execute(select(func.count(Filing.id)))).scalar() or 0
        facts = (await session.execute(select(func.count(FinancialFact.id)))).scalar() or 0
        stats = {"companies": companies, "filings": filings, "financial_facts": facts}

    return {
        "status": "healthy" if db_ok else "unhealthy",
        "database": "connected" if db_ok else "disconnected",
        "stats": stats,
    }
