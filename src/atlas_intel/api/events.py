"""Material event API endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.api.dependencies import valid_company
from atlas_intel.database import get_session
from atlas_intel.models.company import Company
from atlas_intel.schemas.common import PaginatedResponse
from atlas_intel.schemas.event import EventSummaryResponse, MaterialEventResponse
from atlas_intel.services.event_service import get_event_summary, get_events

router = APIRouter(tags=["events"])


@router.get(
    "/companies/{identifier}/events",
    response_model=PaginatedResponse[MaterialEventResponse],
)
async def list_events(
    company: Company = Depends(valid_company),
    event_type: str | None = Query(None, description="Filter by event type"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
) -> PaginatedResponse[MaterialEventResponse]:
    """Get paginated material events for a company."""
    events, total = await get_events(
        session, company.id, event_type=event_type, offset=offset, limit=limit
    )
    return PaginatedResponse(
        items=[MaterialEventResponse.model_validate(e) for e in events],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/companies/{identifier}/events/summary",
    response_model=EventSummaryResponse,
)
async def event_summary(
    company: Company = Depends(valid_company),
    session: AsyncSession = Depends(get_session),
) -> EventSummaryResponse:
    """Get event summary for a company."""
    summary = await get_event_summary(session, company.id, company.ticker or str(company.cik))
    return EventSummaryResponse(**summary)
