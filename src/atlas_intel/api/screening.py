"""Stock screening API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.database import get_session
from atlas_intel.schemas.screening import (
    ScreenFilter,
    ScreeningStatsResponse,
    ScreenRequest,
    ScreenResponse,
)
from atlas_intel.services.screening_service import (
    get_screening_stats,
    screen_companies,
)

router = APIRouter(tags=["screening"])


@router.post(
    "/screen",
    response_model=ScreenResponse,
)
async def screen_post(
    request: ScreenRequest,
    session: AsyncSession = Depends(get_session),
) -> ScreenResponse:
    """Screen companies with complex filter criteria via request body."""
    try:
        return await screen_companies(
            session,
            metric_filters=request.metric_filters,
            company_filters=request.company_filters,
            signal_filters=request.signal_filters,
            sort_by=request.sort_by,
            sort_order=request.sort_order,
            offset=request.offset,
            limit=request.limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/screen",
    response_model=ScreenResponse,
)
async def screen_get(
    session: AsyncSession = Depends(get_session),
    pe_lt: float | None = Query(default=None),
    pe_gt: float | None = Query(default=None),
    roe_gt: float | None = Query(default=None),
    roe_lt: float | None = Query(default=None),
    debt_to_equity_lt: float | None = Query(default=None),
    dividend_yield_gt: float | None = Query(default=None),
    market_cap_gt: float | None = Query(default=None),
    market_cap_lt: float | None = Query(default=None),
    sector: str | None = Query(default=None),
    industry: str | None = Query(default=None),
    sort_by: str = Query(default="market_cap"),
    sort_order: str = Query(default="desc"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> ScreenResponse:
    """Screen companies with simple filters via query parameters."""
    metric_filters: list[ScreenFilter] = []
    company_filters: list[ScreenFilter] = []

    # Build metric filters from query params
    if pe_lt is not None:
        metric_filters.append(ScreenFilter(field="pe_ratio", op="lt", value=pe_lt))
    if pe_gt is not None:
        metric_filters.append(ScreenFilter(field="pe_ratio", op="gt", value=pe_gt))
    if roe_gt is not None:
        metric_filters.append(ScreenFilter(field="roe", op="gt", value=roe_gt))
    if roe_lt is not None:
        metric_filters.append(ScreenFilter(field="roe", op="lt", value=roe_lt))
    if debt_to_equity_lt is not None:
        metric_filters.append(
            ScreenFilter(field="debt_to_equity", op="lt", value=debt_to_equity_lt)
        )
    if dividend_yield_gt is not None:
        metric_filters.append(
            ScreenFilter(field="dividend_yield", op="gt", value=dividend_yield_gt)
        )
    if market_cap_gt is not None:
        metric_filters.append(ScreenFilter(field="market_cap", op="gt", value=market_cap_gt))
    if market_cap_lt is not None:
        metric_filters.append(ScreenFilter(field="market_cap", op="lt", value=market_cap_lt))

    # Build company filters
    if sector is not None:
        company_filters.append(ScreenFilter(field="sector", op="eq", value=sector))
    if industry is not None:
        company_filters.append(ScreenFilter(field="industry", op="eq", value=industry))

    return await screen_companies(
        session,
        metric_filters=metric_filters,
        company_filters=company_filters,
        sort_by=sort_by,
        sort_order=sort_order,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/screen/stats",
    response_model=ScreeningStatsResponse,
)
async def screening_stats(
    session: AsyncSession = Depends(get_session),
) -> ScreeningStatsResponse:
    """Get screening universe statistics."""
    return await get_screening_stats(session)
