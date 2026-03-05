"""News article API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.database import get_session
from atlas_intel.schemas.common import PaginatedResponse
from atlas_intel.schemas.news import NewsActivityResponse, NewsArticleResponse
from atlas_intel.services.company_service import get_company_by_identifier
from atlas_intel.services.news_service import get_news, get_news_activity

router = APIRouter(tags=["news"])


@router.get(
    "/companies/{identifier}/news",
    response_model=PaginatedResponse[NewsArticleResponse],
)
async def list_news(
    identifier: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
) -> PaginatedResponse[NewsArticleResponse]:
    """Get paginated news articles for a company."""
    company = await get_company_by_identifier(session, identifier)
    if not company:
        raise HTTPException(status_code=404, detail=f"Company not found: {identifier}")

    articles, total = await get_news(session, company.id, offset=offset, limit=limit)
    return PaginatedResponse(
        items=[NewsArticleResponse.model_validate(a) for a in articles],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/companies/{identifier}/news/activity",
    response_model=NewsActivityResponse,
)
async def news_activity(
    identifier: str,
    session: AsyncSession = Depends(get_session),
) -> NewsActivityResponse:
    """Get news activity analytics for a company."""
    company = await get_company_by_identifier(session, identifier)
    if not company:
        raise HTTPException(status_code=404, detail=f"Company not found: {identifier}")

    analytics = await get_news_activity(session, company.id, company.ticker or identifier)
    return NewsActivityResponse(**analytics)
