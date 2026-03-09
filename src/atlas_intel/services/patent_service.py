"""Patent business logic and analytics."""

from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.models.patent import Patent


async def get_patents(
    session: AsyncSession,
    company_id: int,
    patent_type: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[Patent], int]:
    """Query patents paginated with optional patent_type filter."""
    base_where = [Patent.company_id == company_id]
    if patent_type:
        base_where.append(Patent.patent_type == patent_type)

    count_stmt = select(func.count(Patent.id)).where(*base_where)
    total = (await session.execute(count_stmt)).scalar() or 0

    stmt = (
        select(Patent)
        .where(*base_where)
        .order_by(Patent.grant_date.desc().nulls_last())
        .offset(offset)
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all()), total


async def get_innovation_summary(
    session: AsyncSession,
    company_id: int,
    ticker: str,
) -> dict[str, Any]:
    """Innovation summary: patent velocity, top CPC classes."""
    today = date.today()
    analytics: dict[str, Any] = {"ticker": ticker}

    # Total patents
    total = (
        await session.execute(select(func.count(Patent.id)).where(Patent.company_id == company_id))
    ).scalar() or 0
    analytics["total_patents"] = total

    # Patents in last 12 months vs prior 12 months
    cutoff_12m = today - timedelta(days=365)
    cutoff_24m = today - timedelta(days=730)

    patents_12m = (
        await session.execute(
            select(func.count(Patent.id)).where(
                Patent.company_id == company_id,
                Patent.grant_date >= cutoff_12m,
            )
        )
    ).scalar() or 0
    analytics["patents_12m"] = patents_12m

    patents_prior_12m = (
        await session.execute(
            select(func.count(Patent.id)).where(
                Patent.company_id == company_id,
                Patent.grant_date >= cutoff_24m,
                Patent.grant_date < cutoff_12m,
            )
        )
    ).scalar() or 0
    analytics["patents_prior_12m"] = patents_prior_12m

    # Velocity change %
    if patents_prior_12m > 0:
        change = (patents_12m - patents_prior_12m) / patents_prior_12m * 100
        analytics["velocity_change_pct"] = round(change, 2)
    else:
        analytics["velocity_change_pct"] = None

    # Top 5 CPC classes
    cpc_result = await session.execute(
        select(Patent.cpc_class, func.count(Patent.id).label("cnt"))
        .where(Patent.company_id == company_id, Patent.cpc_class.isnot(None))
        .group_by(Patent.cpc_class)
        .order_by(func.count(Patent.id).desc())
        .limit(5)
    )
    analytics["top_cpc_classes"] = [
        {"cpc_class": row[0], "count": row[1]} for row in cpc_result.all()
    ]

    return analytics
