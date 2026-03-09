"""Patent API endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.api.dependencies import valid_company
from atlas_intel.database import get_session
from atlas_intel.models.company import Company
from atlas_intel.schemas.common import PaginatedResponse
from atlas_intel.schemas.patent import InnovationSummaryResponse, PatentResponse
from atlas_intel.services.patent_service import get_innovation_summary, get_patents

router = APIRouter(tags=["patents"])


@router.get(
    "/companies/{identifier}/patents",
    response_model=PaginatedResponse[PatentResponse],
)
async def list_patents(
    company: Company = Depends(valid_company),
    patent_type: str | None = Query(None, description="Filter by patent type"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
) -> PaginatedResponse[PatentResponse]:
    """Get paginated patents for a company."""
    patents, total = await get_patents(
        session, company.id, patent_type=patent_type, offset=offset, limit=limit
    )
    return PaginatedResponse(
        items=[PatentResponse.model_validate(p) for p in patents],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/companies/{identifier}/patents/innovation",
    response_model=InnovationSummaryResponse,
)
async def innovation_summary(
    company: Company = Depends(valid_company),
    session: AsyncSession = Depends(get_session),
) -> InnovationSummaryResponse:
    """Get innovation summary for a company."""
    summary = await get_innovation_summary(session, company.id, company.ticker or str(company.cik))
    return InnovationSummaryResponse(**summary)
