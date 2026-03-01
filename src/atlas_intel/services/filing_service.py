"""Filing business logic."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.models.filing import Filing


async def get_filings(
    session: AsyncSession,
    company_id: int,
    form_type: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[Filing], int]:
    """Get filings for a company with optional form_type filter."""
    stmt = select(Filing).where(Filing.company_id == company_id)
    count_stmt = select(func.count(Filing.id)).where(Filing.company_id == company_id)

    if form_type:
        stmt = stmt.where(Filing.form_type == form_type)
        count_stmt = count_stmt.where(Filing.form_type == form_type)

    total = (await session.execute(count_stmt)).scalar() or 0

    stmt = stmt.order_by(Filing.filing_date.desc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all()), total


async def get_filing_by_accession(
    session: AsyncSession,
    company_id: int,
    accession_number: str,
) -> Filing | None:
    """Get a specific filing by accession number."""
    accession_clean = accession_number.replace("-", "")
    stmt = select(Filing).where(
        Filing.company_id == company_id,
        Filing.accession_number == accession_clean,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()
