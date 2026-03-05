"""Institutional holdings business logic."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.models.institutional_holding import InstitutionalHolding


async def get_institutional_holdings(
    session: AsyncSession,
    company_id: int,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[InstitutionalHolding], int]:
    """Query institutional holdings paginated. Returns (holdings, total_count)."""
    count_stmt = select(func.count(InstitutionalHolding.id)).where(
        InstitutionalHolding.company_id == company_id
    )
    total = (await session.execute(count_stmt)).scalar() or 0

    stmt = (
        select(InstitutionalHolding)
        .where(InstitutionalHolding.company_id == company_id)
        .order_by(InstitutionalHolding.date_reported.desc(), InstitutionalHolding.shares.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all()), total


async def get_top_holders(
    session: AsyncSession,
    company_id: int,
    limit: int = 10,
) -> list[InstitutionalHolding]:
    """Get top N holders by shares from the latest report date."""
    # Find the latest report date
    latest_date_result = await session.execute(
        select(func.max(InstitutionalHolding.date_reported)).where(
            InstitutionalHolding.company_id == company_id
        )
    )
    latest_date = latest_date_result.scalar()

    if latest_date is None:
        return []

    stmt = (
        select(InstitutionalHolding)
        .where(
            InstitutionalHolding.company_id == company_id,
            InstitutionalHolding.date_reported == latest_date,
        )
        .order_by(InstitutionalHolding.shares.desc().nulls_last())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())
