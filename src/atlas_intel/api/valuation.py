"""Valuation API endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.api.dependencies import valid_company
from atlas_intel.database import get_session
from atlas_intel.models.company import Company
from atlas_intel.schemas.valuation import (
    AnalystValuationResponse,
    DCFResponse,
    FullValuationResponse,
    RelativeValuationResponse,
)
from atlas_intel.services.valuation_service import (
    compute_analyst_valuation,
    compute_dcf_valuation,
    compute_full_valuation_cached,
    compute_relative_valuation,
)

router = APIRouter(tags=["valuation"])


@router.get(
    "/companies/{identifier}/valuation",
    response_model=FullValuationResponse,
)
async def full_valuation(
    company: Company = Depends(valid_company),
    session: AsyncSession = Depends(get_session),
) -> FullValuationResponse:
    """Get full valuation analysis combining DCF, relative, and analyst models."""
    ticker = company.ticker or str(company.cik)
    return await compute_full_valuation_cached(session, company.id, ticker)


@router.get(
    "/companies/{identifier}/valuation/dcf",
    response_model=DCFResponse,
)
async def dcf_valuation(
    company: Company = Depends(valid_company),
    session: AsyncSession = Depends(get_session),
) -> DCFResponse:
    """Get DCF valuation with bear/base/bull scenarios."""
    ticker = company.ticker or str(company.cik)
    return await compute_dcf_valuation(session, company.id, ticker)


@router.get(
    "/companies/{identifier}/valuation/relative",
    response_model=RelativeValuationResponse,
)
async def relative_valuation(
    company: Company = Depends(valid_company),
    session: AsyncSession = Depends(get_session),
) -> RelativeValuationResponse:
    """Get relative valuation vs sector peers."""
    ticker = company.ticker or str(company.cik)
    return await compute_relative_valuation(session, company.id, ticker)


@router.get(
    "/companies/{identifier}/valuation/analyst",
    response_model=AnalystValuationResponse,
)
async def analyst_valuation(
    company: Company = Depends(valid_company),
    session: AsyncSession = Depends(get_session),
) -> AnalystValuationResponse:
    """Get analyst price target valuation."""
    ticker = company.ticker or str(company.cik)
    return await compute_analyst_valuation(session, company.id, ticker)
