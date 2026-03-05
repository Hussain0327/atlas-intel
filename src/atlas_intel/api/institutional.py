"""Institutional holdings API endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.api.dependencies import valid_company
from atlas_intel.database import get_session
from atlas_intel.models.company import Company
from atlas_intel.schemas.common import PaginatedResponse
from atlas_intel.schemas.institutional import InstitutionalHoldingResponse
from atlas_intel.services.institutional_service import get_institutional_holdings, get_top_holders

router = APIRouter(tags=["institutional-holdings"])


@router.get(
    "/companies/{identifier}/institutional-holdings",
    response_model=PaginatedResponse[InstitutionalHoldingResponse],
)
async def list_holdings(
    company: Company = Depends(valid_company),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
) -> PaginatedResponse[InstitutionalHoldingResponse]:
    """Get paginated institutional holdings for a company."""
    holdings, total = await get_institutional_holdings(
        session, company.id, offset=offset, limit=limit
    )
    return PaginatedResponse(
        items=[InstitutionalHoldingResponse.model_validate(h) for h in holdings],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/companies/{identifier}/institutional-holdings/top",
    response_model=list[InstitutionalHoldingResponse],
)
async def top_holders(
    company: Company = Depends(valid_company),
    limit: int = Query(10, ge=1, le=50),
    session: AsyncSession = Depends(get_session),
) -> list[InstitutionalHoldingResponse]:
    """Get top institutional holders by shares."""
    holders = await get_top_holders(session, company.id, limit=limit)
    return [InstitutionalHoldingResponse.model_validate(h) for h in holders]
