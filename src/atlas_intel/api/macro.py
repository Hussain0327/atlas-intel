"""Macro indicator API endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.database import get_session
from atlas_intel.schemas.common import PaginatedResponse
from atlas_intel.schemas.macro import MacroIndicatorResponse, MacroSummaryResponse
from atlas_intel.services.macro_service import get_indicators, get_macro_summary

router = APIRouter(tags=["macro"])


@router.get(
    "/macro/indicators",
    response_model=PaginatedResponse[MacroIndicatorResponse],
)
async def list_indicators(
    series_id: str | None = Query(None, description="Filter by series ID (e.g. GDP, UNRATE)"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
) -> PaginatedResponse[MacroIndicatorResponse]:
    """Get paginated macro indicator observations."""
    indicators, total = await get_indicators(
        session, series_id=series_id, offset=offset, limit=limit
    )
    return PaginatedResponse(
        items=[MacroIndicatorResponse.model_validate(i) for i in indicators],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/macro/summary",
    response_model=MacroSummaryResponse,
)
async def macro_summary(
    session: AsyncSession = Depends(get_session),
) -> MacroSummaryResponse:
    """Get macro summary: latest value per series with observation counts."""
    summary = await get_macro_summary(session)
    return MacroSummaryResponse(**summary)
