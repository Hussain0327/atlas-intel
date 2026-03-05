"""Filing API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.api.dependencies import valid_company
from atlas_intel.database import get_session
from atlas_intel.models.company import Company
from atlas_intel.schemas.common import PaginatedResponse
from atlas_intel.schemas.filing import FilingResponse
from atlas_intel.services.filing_service import get_filing_by_accession, get_filings

router = APIRouter(prefix="/companies/{identifier}/filings", tags=["filings"])


@router.get("/", response_model=PaginatedResponse[FilingResponse])
async def list_filings(
    company: Company = Depends(valid_company),
    form_type: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
) -> PaginatedResponse[FilingResponse]:
    """List filings for a company."""
    filings, total = await get_filings(
        session,
        company.id,
        form_type=form_type,
        offset=offset,
        limit=limit,
    )
    return PaginatedResponse(
        items=[FilingResponse.model_validate(f) for f in filings],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/{accession}", response_model=FilingResponse)
async def get_filing(
    accession: str,
    company: Company = Depends(valid_company),
    session: AsyncSession = Depends(get_session),
) -> FilingResponse:
    """Get a specific filing by accession number."""
    filing = await get_filing_by_accession(session, company.id, accession)
    if not filing:
        raise HTTPException(status_code=404, detail=f"Filing not found: {accession}")
    return FilingResponse.model_validate(filing)
