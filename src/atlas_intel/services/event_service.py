"""Material event business logic and analytics."""

from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.models.material_event import MaterialEvent


async def get_events(
    session: AsyncSession,
    company_id: int,
    event_type: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[MaterialEvent], int]:
    """Query material events paginated with optional event_type filter."""
    base_where = [MaterialEvent.company_id == company_id]
    if event_type:
        base_where.append(MaterialEvent.event_type == event_type)

    count_stmt = select(func.count(MaterialEvent.id)).where(*base_where)
    total = (await session.execute(count_stmt)).scalar() or 0

    stmt = (
        select(MaterialEvent)
        .where(*base_where)
        .order_by(MaterialEvent.event_date.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all()), total


async def get_event_summary(
    session: AsyncSession,
    company_id: int,
    ticker: str,
) -> dict[str, Any]:
    """Event summary: counts by type and time window."""
    today = date.today()
    analytics: dict[str, Any] = {"ticker": ticker}

    # Total events
    total = (
        await session.execute(
            select(func.count(MaterialEvent.id)).where(MaterialEvent.company_id == company_id)
        )
    ).scalar() or 0
    analytics["total_events"] = total

    # Events in time windows
    for label, days in [("events_90d", 90), ("events_365d", 365)]:
        cutoff = today - timedelta(days=days)
        count = (
            await session.execute(
                select(func.count(MaterialEvent.id)).where(
                    MaterialEvent.company_id == company_id,
                    MaterialEvent.event_date >= cutoff,
                )
            )
        ).scalar() or 0
        analytics[label] = count

    # By type
    type_result = await session.execute(
        select(MaterialEvent.event_type, func.count(MaterialEvent.id).label("cnt"))
        .where(MaterialEvent.company_id == company_id)
        .group_by(MaterialEvent.event_type)
        .order_by(func.count(MaterialEvent.id).desc())
    )
    analytics["by_type"] = [{"event_type": row[0], "count": row[1]} for row in type_result.all()]

    return analytics
