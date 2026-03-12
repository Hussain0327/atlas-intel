"""Health check endpoints for liveness and readiness probes."""

from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.config import settings
from atlas_intel.database import get_session
from atlas_intel.models.company import Company
from atlas_intel.models.filing import Filing
from atlas_intel.models.financial_fact import FinancialFact

router = APIRouter(tags=["health"])


@router.get("/health/live")
async def liveness() -> dict[str, str]:
    """Liveness probe — always 200 if the process is running."""
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness(
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    """Readiness probe — checks database connectivity."""
    try:
        await session.execute(text("SELECT 1"))
        return JSONResponse(
            status_code=200,
            content={"status": "ready", "database": "connected", "git_sha": settings.git_sha},
        )
    except Exception:
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "database": "disconnected",
                "git_sha": settings.git_sha,
            },
        )


@router.get("/health")
async def health_check(session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    """Health check with database stats (backward compatible)."""
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
        "git_sha": settings.git_sha,
        "stats": stats,
    }
