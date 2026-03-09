"""Multi-criteria stock screening with efficient cross-company queries.

Filters companies by metric ranges, company attributes, and fusion signal thresholds.
All computation is read-side from existing data.
"""

from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.models.company import Company
from atlas_intel.models.market_metric import MarketMetric
from atlas_intel.schemas.screening import (
    ScreenFilter,
    ScreeningStatsResponse,
    ScreenResponse,
    ScreenResult,
    SignalFilter,
)
from atlas_intel.services.fusion_service import (
    compute_growth_signal,
    compute_risk_signal,
    compute_sentiment_signal,
    compute_smart_money_signal,
)

MAX_SCREEN_RESULTS = 200
SCREENING_CACHE_TTL = 300  # 5 minutes

# Valid metric fields for screening (column names on MarketMetric)
VALID_METRIC_FIELDS = {
    "market_cap",
    "enterprise_value",
    "pe_ratio",
    "pb_ratio",
    "price_to_sales",
    "ev_to_ebitda",
    "ev_to_sales",
    "earnings_yield",
    "fcf_yield",
    "revenue_per_share",
    "net_income_per_share",
    "book_value_per_share",
    "fcf_per_share",
    "dividend_per_share",
    "roe",
    "roic",
    "debt_to_equity",
    "debt_to_assets",
    "current_ratio",
    "interest_coverage",
    "dividend_yield",
    "payout_ratio",
}

# Valid company fields for screening
VALID_COMPANY_FIELDS = {"sector", "industry", "country", "exchange"}

# Signal type to computation function mapping
SIGNAL_FUNCTIONS = {
    "sentiment": compute_sentiment_signal,
    "growth": compute_growth_signal,
    "risk": compute_risk_signal,
    "smart_money": compute_smart_money_signal,
}


def _build_metric_conditions(
    filters: list[ScreenFilter],
    subquery_alias: str,
) -> list[Any]:
    """Build SQLAlchemy WHERE clauses for metric filters.

    Returns list of conditions. Invalid fields are silently skipped.
    """
    from sqlalchemy import column

    conditions: list[Any] = []
    for f in filters:
        if f.field not in VALID_METRIC_FIELDS:
            continue

        col: Any = column(f.field)

        if f.op == "gt" and f.value is not None:
            conditions.append(col > float(f.value))
        elif f.op == "gte" and f.value is not None:
            conditions.append(col >= float(f.value))
        elif f.op == "lt" and f.value is not None:
            conditions.append(col < float(f.value))
        elif f.op == "lte" and f.value is not None:
            conditions.append(col <= float(f.value))
        elif f.op == "eq" and f.value is not None:
            conditions.append(col == float(f.value))
        elif f.op == "between" and f.value is not None and f.value_high is not None:
            conditions.append(col >= float(f.value))
            conditions.append(col <= f.value_high)

    return conditions


def _build_company_conditions(filters: list[ScreenFilter]) -> list[Any]:
    """Build SQLAlchemy WHERE clauses for company attribute filters."""
    conditions: list[Any] = []
    for f in filters:
        if f.field not in VALID_COMPANY_FIELDS:
            continue

        col = getattr(Company, f.field, None)
        if col is None:
            continue

        if f.op == "eq" and f.value is not None:
            conditions.append(col == str(f.value))
        elif f.op == "in" and f.values:
            conditions.append(col.in_(f.values))

    return conditions


async def screen_companies(
    session: AsyncSession,
    metric_filters: list[ScreenFilter] | None = None,
    company_filters: list[ScreenFilter] | None = None,
    signal_filters: list[SignalFilter] | None = None,
    sort_by: str = "market_cap",
    sort_order: str = "desc",
    offset: int = 0,
    limit: int = 50,
) -> ScreenResponse:
    """Screen companies by metric, company, and signal filters.

    Strategy: Filter by metric + company conditions via SQL first, then optionally
    post-filter by signal scores. This avoids computing signals for every company.
    """
    metric_filters = metric_filters or []
    company_filters = company_filters or []
    signal_filters = signal_filters or []

    limit = min(limit, MAX_SCREEN_RESULTS)

    # DISTINCT ON subquery for latest TTM per company
    latest_metrics = (
        select(MarketMetric)
        .where(MarketMetric.period == "TTM")
        .distinct(MarketMetric.company_id)
        .order_by(MarketMetric.company_id, MarketMetric.period_date.desc())
        .subquery()
    )

    # Build conditions
    company_conditions = _build_company_conditions(company_filters)

    # Apply metric conditions to the subquery columns
    applied_metric_conditions: list[Any] = []
    for f in metric_filters:
        if f.field not in VALID_METRIC_FIELDS:
            continue
        col = latest_metrics.c[f.field]
        if f.op == "gt" and f.value is not None:
            applied_metric_conditions.append(col > float(f.value))
        elif f.op == "gte" and f.value is not None:
            applied_metric_conditions.append(col >= float(f.value))
        elif f.op == "lt" and f.value is not None:
            applied_metric_conditions.append(col < float(f.value))
        elif f.op == "lte" and f.value is not None:
            applied_metric_conditions.append(col <= float(f.value))
        elif f.op == "eq" and f.value is not None:
            applied_metric_conditions.append(col == float(f.value))
        elif f.op == "between" and f.value is not None and f.value_high is not None:
            applied_metric_conditions.append(col >= float(f.value))
            applied_metric_conditions.append(col <= f.value_high)

    # Determine sort column
    sort_col: Any = latest_metrics.c.market_cap  # default
    if sort_by in VALID_METRIC_FIELDS and sort_by in latest_metrics.c:
        sort_col = latest_metrics.c[sort_by]
    elif sort_by == "name":
        sort_col = Company.name
    elif sort_by == "ticker":
        sort_col = Company.ticker

    order = sort_col.desc() if sort_order == "desc" else sort_col.asc()

    # Count query
    count_stmt = (
        select(func.count())
        .select_from(Company)
        .join(latest_metrics, Company.id == latest_metrics.c.company_id)
        .where(*applied_metric_conditions, *company_conditions)
    )
    total = (await session.execute(count_stmt)).scalar() or 0

    # Main query
    stmt = (
        select(Company, latest_metrics)
        .join(latest_metrics, Company.id == latest_metrics.c.company_id)
        .where(*applied_metric_conditions, *company_conditions)
        .order_by(order.nulls_last())
        .offset(offset)
        .limit(limit)
    )

    result = await session.execute(stmt)
    rows = result.all()

    # Build results
    items: list[ScreenResult] = []
    for row in rows:
        company = row[0]
        # Metric columns follow the Company columns in the row
        mapping = row._mapping

        def _metric_val(m: dict[str, Any], name: str) -> float | None:
            val = m.get(name)
            if val is None:
                return None
            if isinstance(val, Decimal):
                return float(val)
            return float(val)

        m = dict(mapping)
        items.append(
            ScreenResult(
                ticker=company.ticker or str(company.cik),
                name=company.name,
                sector=company.sector,
                industry=company.industry,
                market_cap=_metric_val(m, "market_cap"),
                pe_ratio=_metric_val(m, "pe_ratio"),
                pb_ratio=_metric_val(m, "pb_ratio"),
                ev_to_ebitda=_metric_val(m, "ev_to_ebitda"),
                roe=_metric_val(m, "roe"),
                debt_to_equity=_metric_val(m, "debt_to_equity"),
                dividend_yield=_metric_val(m, "dividend_yield"),
                fcf_yield=_metric_val(m, "fcf_yield"),
            )
        )

    # Post-filter by signal scores if requested
    if signal_filters and items:
        filtered_items: list[ScreenResult] = []
        for item in items:
            # Look up company ID
            company_result = await session.execute(
                select(Company.id).where(func.upper(Company.ticker) == item.ticker.upper())
            )
            cid = company_result.scalar_one_or_none()
            if not cid:
                continue

            passes = True
            signal_scores: dict[str, float | None] = {}

            for sf in signal_filters:
                compute_fn = SIGNAL_FUNCTIONS.get(sf.signal_type)
                if not compute_fn:
                    continue

                signal = await compute_fn(session, cid)
                signal_scores[sf.signal_type] = signal.score

                if signal.score is None:
                    passes = False
                    break

                fails_filter = (
                    (sf.op == "gt" and signal.score <= sf.value)
                    or (sf.op == "gte" and signal.score < sf.value)
                    or (sf.op == "lt" and signal.score >= sf.value)
                    or (sf.op == "lte" and signal.score > sf.value)
                )
                if fails_filter:
                    passes = False
                    break

            if passes:
                item.signal_scores = signal_scores
                filtered_items.append(item)

        items = filtered_items
        total = len(items)

    filters_applied = len(metric_filters) + len(company_filters) + len(signal_filters)

    return ScreenResponse(
        items=items,
        total=total,
        offset=offset,
        limit=limit,
        filters_applied=filters_applied,
    )


async def get_screening_stats(session: AsyncSession) -> ScreeningStatsResponse:
    """Get aggregate stats for screening: total companies, sectors, industries."""
    total_result = await session.execute(select(func.count(Company.id)))
    total_companies = total_result.scalar() or 0

    metrics_result = await session.execute(
        select(func.count(func.distinct(MarketMetric.company_id))).where(
            MarketMetric.period == "TTM"
        )
    )
    companies_with_metrics = metrics_result.scalar() or 0

    sectors_result = await session.execute(
        select(Company.sector)
        .where(Company.sector.is_not(None))
        .distinct()
        .order_by(Company.sector)
    )
    sectors = [r[0] for r in sectors_result.all()]

    industries_result = await session.execute(
        select(Company.industry)
        .where(Company.industry.is_not(None))
        .distinct()
        .order_by(Company.industry)
    )
    industries = [r[0] for r in industries_result.all()]

    return ScreeningStatsResponse(
        total_companies=total_companies,
        companies_with_metrics=companies_with_metrics,
        sectors=sectors,
        industries=industries,
    )
