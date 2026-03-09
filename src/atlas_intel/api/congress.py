"""Congress trading API endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.api.dependencies import valid_company
from atlas_intel.database import get_session
from atlas_intel.models.company import Company
from atlas_intel.schemas.common import PaginatedResponse
from atlas_intel.schemas.congress import CongressSummaryResponse, CongressTradeResponse
from atlas_intel.services.congress_service import get_congress_summary, get_congress_trades

router = APIRouter(tags=["congress"])


@router.get(
    "/companies/{identifier}/congress",
    response_model=PaginatedResponse[CongressTradeResponse],
)
async def list_congress_trades(
    company: Company = Depends(valid_company),
    party: str | None = Query(None, description="Filter by party (D, R, I)"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
) -> PaginatedResponse[CongressTradeResponse]:
    """Get paginated congress trades for a company."""
    trades, total = await get_congress_trades(
        session, company.id, party=party, offset=offset, limit=limit
    )
    return PaginatedResponse(
        items=[CongressTradeResponse.model_validate(t) for t in trades],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/companies/{identifier}/congress/summary",
    response_model=CongressSummaryResponse,
)
async def congress_summary(
    company: Company = Depends(valid_company),
    session: AsyncSession = Depends(get_session),
) -> CongressSummaryResponse:
    """Get congress trading summary for a company."""
    summary = await get_congress_summary(session, company.id, company.ticker or str(company.cik))
    return CongressSummaryResponse(**summary)
