"""Analyst estimates, grades, and price target API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.api.dependencies import valid_company
from atlas_intel.database import get_session
from atlas_intel.models.company import Company
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

router = APIRouter(tags=["analyst"])


@router.get(
    "/companies/{identifier}/analyst/estimates",
    response_model=PaginatedResponse[AnalystEstimateResponse],
)
async def list_estimates(
    company: Company = Depends(valid_company),
    period: str | None = Query(None, description="Filter by period: annual or quarter"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
) -> PaginatedResponse[AnalystEstimateResponse]:
    """Get paginated analyst estimates for a company."""
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
    company: Company = Depends(valid_company),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
) -> PaginatedResponse[AnalystGradeResponse]:
    """Get paginated analyst grades for a company."""
    grades, total = await get_analyst_grades(session, company.id, offset=offset, limit=limit)
    return PaginatedResponse(
        items=[AnalystGradeResponse.model_validate(g) for g in grades],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/companies/{identifier}/analyst/price-target",
    response_model=PriceTargetResponse,
)
async def price_target(
    company: Company = Depends(valid_company),
    session: AsyncSession = Depends(get_session),
) -> PriceTargetResponse:
    """Get price target consensus for a company."""
    target = await get_price_target(session, company.id)
    if not target:
        raise HTTPException(
            status_code=404,
            detail=f"No price target found for {company.ticker or company.cik}",
        )
    return PriceTargetResponse.model_validate(target)


@router.get(
    "/companies/{identifier}/analyst/consensus",
    response_model=AnalystConsensusResponse,
)
async def analyst_consensus(
    company: Company = Depends(valid_company),
    session: AsyncSession = Depends(get_session),
) -> AnalystConsensusResponse:
    """Get fused analyst consensus view."""
    consensus = await get_analyst_consensus(session, company.id, company.ticker or str(company.cik))
    return AnalystConsensusResponse(**consensus)
