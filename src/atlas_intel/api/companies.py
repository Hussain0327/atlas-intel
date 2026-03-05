"""Company API endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.api.dependencies import valid_company
from atlas_intel.database import get_session
from atlas_intel.models.company import Company
from atlas_intel.schemas.common import PaginatedResponse
from atlas_intel.schemas.company import CompanyDetail, CompanySummary
from atlas_intel.services.company_service import search_companies

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("/", response_model=PaginatedResponse[CompanySummary])
async def list_companies(
    q: str | None = Query(None, description="Search by name"),
    ticker: str | None = Query(None),
    cik: int | None = Query(None),
    sic_code: str | None = Query(None),
    exchange: str | None = Query(None),
    sector: str | None = Query(None),
    industry: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
) -> PaginatedResponse[CompanySummary]:
    """Search and list companies."""
    companies, total = await search_companies(
        session,
        q=q,
        ticker=ticker,
        cik=cik,
        sic_code=sic_code,
        exchange=exchange,
        sector=sector,
        industry=industry,
        offset=offset,
        limit=limit,
    )
    return PaginatedResponse(
        items=[CompanySummary.model_validate(c) for c in companies],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/{identifier}", response_model=CompanyDetail)
async def get_company(
    company: Company = Depends(valid_company),
) -> CompanyDetail:
    """Get company detail by ticker or CIK."""
    return CompanyDetail.model_validate(company)
