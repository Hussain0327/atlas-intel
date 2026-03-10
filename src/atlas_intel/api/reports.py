"""Report generation API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.api.dependencies import valid_company
from atlas_intel.database import get_session
from atlas_intel.llm.client import LLMUnavailableError
from atlas_intel.models.company import Company
from atlas_intel.schemas.report import ComparisonRequest, ReportResponse

router = APIRouter(tags=["reports"])


@router.get("/companies/{identifier}/report", response_model=ReportResponse)
async def company_report(
    company: Company = Depends(valid_company),
    session: AsyncSession = Depends(get_session),
    report_type: str = Query(default="comprehensive", pattern=r"^(comprehensive|quick)$"),
) -> ReportResponse:
    """Generate an LLM-powered company analysis report."""
    from atlas_intel.services.report_service import generate_company_report

    try:
        return await generate_company_report(
            session, company.id, company.ticker or str(company.cik), company.name, report_type
        )
    except LLMUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/companies/{identifier}/report/stream")
async def company_report_stream(
    company: Company = Depends(valid_company),
    session: AsyncSession = Depends(get_session),
    report_type: str = Query(default="comprehensive", pattern=r"^(comprehensive|quick)$"),
) -> StreamingResponse:
    """Stream an LLM-powered company analysis report via SSE."""
    from atlas_intel.services.report_service import stream_company_report

    try:
        return StreamingResponse(
            stream_company_report(
                session,
                company.id,
                company.ticker or str(company.cik),
                company.name,
                report_type,
            ),
            media_type="text/event-stream",
        )
    except LLMUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/reports/comparison", response_model=ReportResponse)
async def comparison_report(
    request: ComparisonRequest,
    session: AsyncSession = Depends(get_session),
) -> ReportResponse:
    """Generate a comparison report for multiple companies."""
    from atlas_intel.services.company_service import get_company_by_identifier
    from atlas_intel.services.report_service import generate_comparison_report

    company_infos: list[tuple[int, str, str]] = []
    for ticker in request.tickers:
        company = await get_company_by_identifier(session, ticker)
        if not company:
            raise HTTPException(status_code=404, detail=f"Company not found: {ticker}")
        company_infos.append((company.id, company.ticker or ticker, company.name))

    try:
        return await generate_comparison_report(session, company_infos)
    except LLMUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/reports/sector/{sector}", response_model=ReportResponse)
async def sector_report(
    sector: str,
    session: AsyncSession = Depends(get_session),
) -> ReportResponse:
    """Generate a sector analysis report."""
    from atlas_intel.services.report_service import generate_sector_report

    try:
        return await generate_sector_report(session, sector)
    except LLMUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
