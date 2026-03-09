"""Macro indicator business logic and analytics."""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.models.macro_indicator import MacroIndicator


async def get_indicators(
    session: AsyncSession,
    series_id: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[MacroIndicator], int]:
    """Query macro indicators paginated with optional series filter."""
    base_where = []
    if series_id:
        base_where.append(MacroIndicator.series_id == series_id.upper())

    count_stmt = (
        select(func.count(MacroIndicator.id)).where(*base_where)
        if base_where
        else select(func.count(MacroIndicator.id))
    )
    total = (await session.execute(count_stmt)).scalar() or 0

    stmt = select(MacroIndicator)
    if base_where:
        stmt = stmt.where(*base_where)
    stmt = (
        stmt.order_by(MacroIndicator.series_id, MacroIndicator.observation_date.desc())
        .offset(offset)
        .limit(limit)
    )

    result = await session.execute(stmt)
    return list(result.scalars().all()), total


async def get_macro_summary(session: AsyncSession) -> dict[str, Any]:
    """Get latest value per series with observation counts."""
    from sqlalchemy import literal_column

    # Subquery: latest date per series
    latest_sub = (
        select(
            MacroIndicator.series_id,
            func.max(MacroIndicator.observation_date).label("max_date"),
            func.count(MacroIndicator.id).label("obs_count"),
        )
        .group_by(MacroIndicator.series_id)
        .subquery()
    )

    stmt: Any = (
        select(
            MacroIndicator.series_id,
            MacroIndicator.value,
            MacroIndicator.observation_date,
            literal_column("obs_count"),
        )
        .join(
            latest_sub,
            (MacroIndicator.series_id == latest_sub.c.series_id)
            & (MacroIndicator.observation_date == latest_sub.c.max_date),
        )
        .order_by(MacroIndicator.series_id)
    )

    result = await session.execute(stmt)
    series_list = []
    for row in result.all():
        series_list.append(
            {
                "series_id": row[0],
                "latest_value": row[1],
                "latest_date": row[2],
                "observation_count": row[3],
            }
        )

    return {"series": series_list}
