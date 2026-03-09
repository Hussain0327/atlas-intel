"""Anomaly detection API endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.api.dependencies import valid_company
from atlas_intel.database import get_session
from atlas_intel.models.company import Company
from atlas_intel.schemas.anomaly import (
    ActivityAnomalyResponse,
    AllAnomaliesResponse,
    FundamentalAnomalyResponse,
    PriceAnomalyResponse,
    SectorAnomalyResponse,
)
from atlas_intel.services.anomaly_service import (
    detect_activity_anomalies,
    detect_all_anomalies_cached,
    detect_fundamental_anomalies,
    detect_price_anomalies,
    detect_sector_anomalies,
)

router = APIRouter(tags=["anomalies"])


@router.get(
    "/companies/{identifier}/anomalies",
    response_model=AllAnomaliesResponse,
)
async def all_anomalies(
    company: Company = Depends(valid_company),
    session: AsyncSession = Depends(get_session),
    lookback_days: int = Query(default=90, ge=7, le=365),
    threshold: float = Query(default=2.0, ge=1.0, le=5.0),
) -> AllAnomaliesResponse:
    """Get all anomalies for a company."""
    ticker = company.ticker or str(company.cik)
    return await detect_all_anomalies_cached(session, company.id, ticker, lookback_days, threshold)


@router.get(
    "/companies/{identifier}/anomalies/price",
    response_model=PriceAnomalyResponse,
)
async def price_anomalies(
    company: Company = Depends(valid_company),
    session: AsyncSession = Depends(get_session),
    lookback_days: int = Query(default=90, ge=7, le=365),
    threshold: float = Query(default=2.0, ge=1.0, le=5.0),
) -> PriceAnomalyResponse:
    """Detect price anomalies: volume spikes, return spikes, volatility breakouts."""
    ticker = company.ticker or str(company.cik)
    return await detect_price_anomalies(session, company.id, ticker, lookback_days, threshold)


@router.get(
    "/companies/{identifier}/anomalies/fundamental",
    response_model=FundamentalAnomalyResponse,
)
async def fundamental_anomalies(
    company: Company = Depends(valid_company),
    session: AsyncSession = Depends(get_session),
    threshold: float = Query(default=2.0, ge=1.0, le=5.0),
) -> FundamentalAnomalyResponse:
    """Detect fundamental anomalies vs historical values."""
    ticker = company.ticker or str(company.cik)
    return await detect_fundamental_anomalies(session, company.id, ticker, threshold)


@router.get(
    "/companies/{identifier}/anomalies/activity",
    response_model=ActivityAnomalyResponse,
)
async def activity_anomalies(
    company: Company = Depends(valid_company),
    session: AsyncSession = Depends(get_session),
    lookback_days: int = Query(default=90, ge=7, le=365),
    threshold: float = Query(default=2.0, ge=1.0, le=5.0),
) -> ActivityAnomalyResponse:
    """Detect activity anomalies: insider surges, 8-K frequency, analyst clustering."""
    ticker = company.ticker or str(company.cik)
    return await detect_activity_anomalies(session, company.id, ticker, lookback_days, threshold)


@router.get(
    "/companies/{identifier}/anomalies/sector",
    response_model=SectorAnomalyResponse,
)
async def sector_anomalies(
    company: Company = Depends(valid_company),
    session: AsyncSession = Depends(get_session),
    threshold: float = Query(default=2.0, ge=1.0, le=5.0),
) -> SectorAnomalyResponse:
    """Detect company metrics that are anomalous vs sector distribution."""
    ticker = company.ticker or str(company.cik)
    return await detect_sector_anomalies(session, company.id, ticker, threshold)
