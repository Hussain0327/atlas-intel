"""Market metrics API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.api.dependencies import valid_company
from atlas_intel.database import get_session
from atlas_intel.models.company import Company
from atlas_intel.schemas.common import CompareReportResponse, PaginatedResponse
from atlas_intel.schemas.metric import MarketMetricResponse, MetricCompareItem
from atlas_intel.services.metric_service import (
    VALID_METRIC_NAMES,
    compare_metric_report,
    get_latest_metrics_cached,
    get_metrics,
)

router = APIRouter(tags=["metrics"])


@router.get(
    "/companies/{identifier}/metrics",
    response_model=PaginatedResponse[MarketMetricResponse],
)
async def list_metrics(
    company: Company = Depends(valid_company),
    period: str | None = Query(None, description="Filter by period: TTM, annual"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
) -> PaginatedResponse[MarketMetricResponse]:
    """Get paginated market metrics for a company."""
    metrics, total = await get_metrics(
        session, company.id, period=period, offset=offset, limit=limit
    )
    return PaginatedResponse(
        items=[MarketMetricResponse.model_validate(m) for m in metrics],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/companies/{identifier}/metrics/latest",
    response_model=MarketMetricResponse,
)
async def latest_metrics(
    company: Company = Depends(valid_company),
    session: AsyncSession = Depends(get_session),
) -> MarketMetricResponse:
    """Get the most recent TTM metrics for a company."""
    metric = await get_latest_metrics_cached(session, company.id)
    if not metric:
        raise HTTPException(
            status_code=404,
            detail=f"No metrics found for {company.ticker or company.cik}",
        )

    return MarketMetricResponse(**metric)


@router.get(
    "/metrics/compare",
    response_model=list[MetricCompareItem],
)
async def compare_metrics(
    response: Response,
    metric: str = Query(..., description="Metric name to compare (e.g. pe_ratio)"),
    tickers: list[str] = Query(..., description="Tickers to compare"),
    session: AsyncSession = Depends(get_session),
) -> list[MetricCompareItem]:
    """Compare a single metric across multiple companies."""
    if metric not in VALID_METRIC_NAMES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid metric: {metric}. Valid metrics: {sorted(VALID_METRIC_NAMES)}",
        )

    results, unresolved = await compare_metric_report(session, metric, tickers)
    if unresolved:
        response.headers["X-Unresolved-Tickers"] = ",".join(unresolved)
    return [MetricCompareItem(**r) for r in results]


@router.get(
    "/metrics/compare/report",
    response_model=CompareReportResponse[MetricCompareItem],
)
async def compare_metrics_report(
    metric: str = Query(..., description="Metric name to compare (e.g. pe_ratio)"),
    tickers: list[str] = Query(..., description="Tickers to compare"),
    session: AsyncSession = Depends(get_session),
) -> CompareReportResponse[MetricCompareItem]:
    """Compare a single metric with explicit unresolved ticker reporting."""
    if metric not in VALID_METRIC_NAMES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid metric: {metric}. Valid metrics: {sorted(VALID_METRIC_NAMES)}",
        )

    results, unresolved = await compare_metric_report(session, metric, tickers)
    return CompareReportResponse(
        items=[MetricCompareItem(**r) for r in results],
        requested_tickers=[t.upper() for t in tickers],
        unresolved_tickers=unresolved,
    )
