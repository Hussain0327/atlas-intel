"""Dashboard API endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.database import get_session
from atlas_intel.schemas.dashboard import (
    AlertSummaryResponse,
    DashboardResponse,
    MarketOverview,
    TopMoversResponse,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardResponse)
async def full_dashboard(
    session: AsyncSession = Depends(get_session),
) -> DashboardResponse:
    """Get full dashboard with market overview, top movers, and alert summary."""
    from atlas_intel.services.dashboard_service import get_full_dashboard_cached

    return await get_full_dashboard_cached(session)


@router.get("/market-overview", response_model=MarketOverview)
async def market_overview(
    session: AsyncSession = Depends(get_session),
) -> MarketOverview:
    """Get market-wide overview with sector breakdown."""
    from atlas_intel.services.dashboard_service import get_market_overview

    return await get_market_overview(session)


@router.get("/top-movers", response_model=TopMoversResponse)
async def top_movers(
    lookback_days: int = Query(default=1, ge=1, le=30),
    limit: int = Query(default=10, ge=1, le=50),
    session: AsyncSession = Depends(get_session),
) -> TopMoversResponse:
    """Get top gainers, losers, and volume leaders."""
    from atlas_intel.services.dashboard_service import get_top_movers

    return await get_top_movers(session, lookback_days=lookback_days, limit=limit)


@router.get("/alert-summary", response_model=AlertSummaryResponse)
async def alert_summary(
    session: AsyncSession = Depends(get_session),
) -> AlertSummaryResponse:
    """Get alert rules and events summary."""
    from atlas_intel.services.dashboard_service import get_alert_summary

    return await get_alert_summary(session)
