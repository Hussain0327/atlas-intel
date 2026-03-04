"""Stock price API endpoints."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.database import get_session
from atlas_intel.schemas.common import PaginatedResponse
from atlas_intel.schemas.price import (
    DailyReturnResponse,
    PriceAnalyticsResponse,
    StockPriceResponse,
)
from atlas_intel.services.company_service import get_company_by_identifier
from atlas_intel.services.price_service import get_daily_returns, get_price_analytics, get_prices

router = APIRouter(tags=["prices"])


@router.get(
    "/companies/{identifier}/prices",
    response_model=PaginatedResponse[StockPriceResponse],
)
async def list_prices(
    identifier: str,
    from_date: date | None = Query(None, alias="from", description="Start date (YYYY-MM-DD)"),
    to_date: date | None = Query(None, alias="to", description="End date (YYYY-MM-DD)"),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
) -> PaginatedResponse[StockPriceResponse]:
    """Get paginated stock prices for a company with optional date range."""
    company = await get_company_by_identifier(session, identifier)
    if not company:
        raise HTTPException(status_code=404, detail=f"Company not found: {identifier}")

    prices, total = await get_prices(
        session, company.id, from_date=from_date, to_date=to_date, offset=offset, limit=limit
    )
    return PaginatedResponse(
        items=[StockPriceResponse.model_validate(p) for p in prices],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/companies/{identifier}/prices/analytics",
    response_model=PriceAnalyticsResponse,
)
async def price_analytics(
    identifier: str,
    session: AsyncSession = Depends(get_session),
) -> PriceAnalyticsResponse:
    """Get computed price analytics (returns, volatility, SMAs)."""
    company = await get_company_by_identifier(session, identifier)
    if not company:
        raise HTTPException(status_code=404, detail=f"Company not found: {identifier}")

    analytics = await get_price_analytics(session, company.id, company.ticker or identifier)
    return PriceAnalyticsResponse(**analytics)


@router.get(
    "/companies/{identifier}/prices/returns",
    response_model=list[DailyReturnResponse],
)
async def daily_returns(
    identifier: str,
    from_date: date | None = Query(None, alias="from", description="Start date"),
    to_date: date | None = Query(None, alias="to", description="End date"),
    limit: int = Query(100, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
) -> list[DailyReturnResponse]:
    """Get daily returns series for a company."""
    company = await get_company_by_identifier(session, identifier)
    if not company:
        raise HTTPException(status_code=404, detail=f"Company not found: {identifier}")

    returns = await get_daily_returns(
        session, company.id, from_date=from_date, to_date=to_date, limit=limit
    )
    return [DailyReturnResponse(**r) for r in returns]
