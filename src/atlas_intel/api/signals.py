"""Fusion signal API endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.api.dependencies import valid_company
from atlas_intel.database import get_session
from atlas_intel.models.company import Company
from atlas_intel.schemas.fusion import AllSignalsResponse, SignalResponse
from atlas_intel.services.fusion_service import (
    compute_growth_signal,
    compute_risk_signal,
    compute_sentiment_signal,
    compute_smart_money_signal,
)

router = APIRouter(tags=["signals"])


@router.get(
    "/companies/{identifier}/signals",
    response_model=AllSignalsResponse,
)
async def all_signals(
    company: Company = Depends(valid_company),
    session: AsyncSession = Depends(get_session),
) -> AllSignalsResponse:
    """Get all 4 composite signals for a company."""
    sentiment = await compute_sentiment_signal(session, company.id)
    growth = await compute_growth_signal(session, company.id)
    risk = await compute_risk_signal(session, company.id)
    smart_money = await compute_smart_money_signal(session, company.id)

    return AllSignalsResponse(
        ticker=company.ticker or str(company.cik),
        sentiment=sentiment,
        growth=growth,
        risk=risk,
        smart_money=smart_money,
    )


@router.get(
    "/companies/{identifier}/signals/sentiment",
    response_model=SignalResponse,
)
async def sentiment_signal(
    company: Company = Depends(valid_company),
    session: AsyncSession = Depends(get_session),
) -> SignalResponse:
    """Get composite sentiment signal."""
    return await compute_sentiment_signal(session, company.id)


@router.get(
    "/companies/{identifier}/signals/growth",
    response_model=SignalResponse,
)
async def growth_signal(
    company: Company = Depends(valid_company),
    session: AsyncSession = Depends(get_session),
) -> SignalResponse:
    """Get growth signal."""
    return await compute_growth_signal(session, company.id)


@router.get(
    "/companies/{identifier}/signals/risk",
    response_model=SignalResponse,
)
async def risk_signal(
    company: Company = Depends(valid_company),
    session: AsyncSession = Depends(get_session),
) -> SignalResponse:
    """Get risk score signal."""
    return await compute_risk_signal(session, company.id)


@router.get(
    "/companies/{identifier}/signals/smart-money",
    response_model=SignalResponse,
)
async def smart_money_signal(
    company: Company = Depends(valid_company),
    session: AsyncSession = Depends(get_session),
) -> SignalResponse:
    """Get smart money signal."""
    return await compute_smart_money_signal(session, company.id)
