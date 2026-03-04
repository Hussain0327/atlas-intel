"""Financial data API endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.database import get_session
from atlas_intel.schemas.common import PaginatedResponse
from atlas_intel.schemas.financial import CompareItem, FinancialFactResponse, FinancialSummaryItem
from atlas_intel.services.company_service import get_company_by_identifier
from atlas_intel.services.financial_service import (
    compare_metric,
    get_financial_facts,
    get_financial_summary,
)

router = APIRouter(tags=["financials"])


@router.get(
    "/companies/{identifier}/financials",
    response_model=PaginatedResponse[FinancialFactResponse],
)
async def query_financials(
    identifier: str,
    concept: str | None = Query(None, description="XBRL concept name (e.g. Revenues, Assets)"),
    form_type: str | None = Query(None, description="Filing form type (e.g. 10-K, 10-Q)"),
    fiscal_year: int | None = Query(None),
    fiscal_period: str | None = Query(None, description="e.g. FY, Q1, Q2, Q3, Q4"),
    taxonomy: str | None = Query(None, description="e.g. us-gaap, dei"),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
) -> PaginatedResponse[FinancialFactResponse]:
    """Query financial facts for a company."""
    company = await get_company_by_identifier(session, identifier)
    if not company:
        raise HTTPException(status_code=404, detail=f"Company not found: {identifier}")

    facts, total = await get_financial_facts(
        session,
        company.id,
        concept=concept,
        form_type=form_type,
        fiscal_year=fiscal_year,
        fiscal_period=fiscal_period,
        taxonomy=taxonomy,
        offset=offset,
        limit=limit,
    )
    return PaginatedResponse(
        items=[FinancialFactResponse.model_validate(f) for f in facts],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/companies/{identifier}/financials/summary",
    response_model=list[FinancialSummaryItem],
)
async def financials_summary(
    identifier: str,
    years: int = Query(5, ge=1, le=20),
    session: AsyncSession = Depends(get_session),
) -> Any:
    """Get key financial metrics summary for the last N fiscal years."""
    company = await get_company_by_identifier(session, identifier)
    if not company:
        raise HTTPException(status_code=404, detail=f"Company not found: {identifier}")

    return await get_financial_summary(session, company.id, years=years)


@router.get("/financials/compare", response_model=list[CompareItem])
async def compare_financials(
    concept: str = Query(..., description="XBRL concept to compare"),
    tickers: list[str] = Query(..., description="Tickers to compare"),
    form_type: str = Query("10-K"),
    fiscal_period: str = Query("FY"),
    years: int = Query(5, ge=1, le=20),
    session: AsyncSession = Depends(get_session),
) -> Any:
    """Compare a financial metric across multiple companies."""
    return await compare_metric(
        session,
        concept=concept,
        tickers=tickers,
        form_type=form_type,
        fiscal_period=fiscal_period,
        years=years,
    )
