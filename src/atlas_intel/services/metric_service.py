"""Market metrics business logic."""

from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.models.company import Company
from atlas_intel.models.market_metric import MarketMetric

# Allowlist of valid metric column names for comparison endpoint
VALID_METRIC_NAMES = {
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
    "days_sales_outstanding",
    "days_payables_outstanding",
    "inventory_turnover",
}


async def get_metrics(
    session: AsyncSession,
    company_id: int,
    period: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[MarketMetric], int]:
    """Query market metrics with optional period filter. Returns (metrics, total_count)."""
    stmt = select(MarketMetric).where(MarketMetric.company_id == company_id)
    count_stmt = select(func.count(MarketMetric.id)).where(MarketMetric.company_id == company_id)

    if period:
        stmt = stmt.where(MarketMetric.period == period)
        count_stmt = count_stmt.where(MarketMetric.period == period)

    total = (await session.execute(count_stmt)).scalar() or 0

    stmt = stmt.order_by(MarketMetric.period_date.desc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all()), total


async def get_latest_metrics(
    session: AsyncSession,
    company_id: int,
) -> MarketMetric | None:
    """Get the most recent TTM metrics record."""
    stmt = (
        select(MarketMetric)
        .where(MarketMetric.company_id == company_id, MarketMetric.period == "TTM")
        .order_by(MarketMetric.period_date.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def compare_metric(
    session: AsyncSession,
    metric_name: str,
    tickers: list[str],
) -> list[dict[str, Any]]:
    """Compare a single metric across multiple companies (latest TTM)."""
    upper_tickers = [t.upper() for t in tickers]
    companies_result = await session.execute(
        select(Company).where(func.upper(Company.ticker).in_(upper_tickers))
    )
    companies = {(c.ticker or "").upper(): c for c in companies_result.scalars().all()}

    results = []
    for ticker in tickers:
        company = companies.get(ticker.upper())
        if not company:
            continue

        latest = await get_latest_metrics(session, company.id)
        value: Decimal | None = None
        if latest:
            value = getattr(latest, metric_name, None)

        results.append(
            {
                "ticker": company.ticker or ticker,
                "company_name": company.name,
                "sector": company.sector,
                "value": value,
            }
        )

    return results
