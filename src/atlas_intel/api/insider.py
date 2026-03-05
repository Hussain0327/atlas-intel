"""Insider trading API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.database import get_session
from atlas_intel.schemas.common import PaginatedResponse
from atlas_intel.schemas.insider import InsiderSentimentResponse, InsiderTradeResponse
from atlas_intel.services.company_service import get_company_by_identifier
from atlas_intel.services.insider_service import get_insider_sentiment, get_insider_trades

router = APIRouter(tags=["insider-trading"])


@router.get(
    "/companies/{identifier}/insider-trades",
    response_model=PaginatedResponse[InsiderTradeResponse],
)
async def list_insider_trades(
    identifier: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
) -> PaginatedResponse[InsiderTradeResponse]:
    """Get paginated insider trades for a company."""
    company = await get_company_by_identifier(session, identifier)
    if not company:
        raise HTTPException(status_code=404, detail=f"Company not found: {identifier}")

    trades, total = await get_insider_trades(session, company.id, offset=offset, limit=limit)
    return PaginatedResponse(
        items=[InsiderTradeResponse.model_validate(t) for t in trades],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/companies/{identifier}/insider-trades/sentiment",
    response_model=InsiderSentimentResponse,
)
async def insider_sentiment(
    identifier: str,
    days: int = Query(90, ge=1, le=365),
    session: AsyncSession = Depends(get_session),
) -> InsiderSentimentResponse:
    """Get insider trading sentiment analysis."""
    company = await get_company_by_identifier(session, identifier)
    if not company:
        raise HTTPException(status_code=404, detail=f"Company not found: {identifier}")

    sentiment = await get_insider_sentiment(
        session, company.id, company.ticker or identifier, days=days
    )
    return InsiderSentimentResponse(**sentiment)
