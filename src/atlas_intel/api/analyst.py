"""Analyst estimates, grades, and price target API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.database import get_session
from atlas_intel.schemas.analyst import (
    AnalystConsensusResponse,
    AnalystEstimateResponse,
    AnalystGradeResponse,
    PriceTargetResponse,
)
from atlas_intel.schemas.common import PaginatedResponse
from atlas_intel.services.analyst_service import (
    get_analyst_consensus,
    get_analyst_estimates,
    get_analyst_grades,
    get_price_target,
)
from atlas_intel.services.company_service import get_company_by_identifier

router = APIRouter(tags=["analyst"])


@router.get(
    "/companies/{identifier}/analyst/estimates",
    response_model=PaginatedResponse[AnalystEstimateResponse],
)
async def list_estimates(
    identifier: str,
    period: str | None = Query(None, description="Filter by period: annual or quarter"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
) -> PaginatedResponse[AnalystEstimateResponse]:
    """Get paginated analyst estimates for a company."""
    company = await get_company_by_identifier(session, identifier)
    if not company:
        raise HTTPException(status_code=404, detail=f"Company not found: {identifier}")

    estimates, total = await get_analyst_estimates(
        session, company.id, period=period, offset=offset, limit=limit
    )
    return PaginatedResponse(
        items=[AnalystEstimateResponse.model_validate(e) for e in estimates],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/companies/{identifier}/analyst/grades",
    response_model=PaginatedResponse[AnalystGradeResponse],
)
async def list_grades(
    identifier: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
) -> PaginatedResponse[AnalystGradeResponse]:
    """Get paginated analyst grades for a company."""
    company = await get_company_by_identifier(session, identifier)
    if not company:
        raise HTTPException(status_code=404, detail=f"Company not found: {identifier}")

    grades, total = await get_analyst_grades(session, company.id, offset=offset, limit=limit)
    return PaginatedResponse(
        items=[AnalystGradeResponse.model_validate(g) for g in grades],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/companies/{identifier}/analyst/price-target",
    response_model=PriceTargetResponse | None,
)
async def price_target(
    identifier: str,
    session: AsyncSession = Depends(get_session),
) -> PriceTargetResponse | None:
    """Get price target consensus for a company."""
    company = await get_company_by_identifier(session, identifier)
    if not company:
        raise HTTPException(status_code=404, detail=f"Company not found: {identifier}")

    target = await get_price_target(session, company.id)
    if not target:
        return None
    return PriceTargetResponse.model_validate(target)


@router.get(
    "/companies/{identifier}/analyst/consensus",
    response_model=AnalystConsensusResponse,
)
async def analyst_consensus(
    identifier: str,
    session: AsyncSession = Depends(get_session),
) -> AnalystConsensusResponse:
    """Get fused analyst consensus view."""
    company = await get_company_by_identifier(session, identifier)
    if not company:
        raise HTTPException(status_code=404, detail=f"Company not found: {identifier}")

    consensus = await get_analyst_consensus(session, company.id, company.ticker or identifier)
    return AnalystConsensusResponse(**consensus)
