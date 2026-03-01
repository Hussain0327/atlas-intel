"""Company business logic."""

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.models.company import Company


def resolve_identifier(identifier: str) -> tuple[str, int | str]:
    """Resolve an identifier to either CIK (int) or ticker (str).

    Returns ("cik", int_value) or ("ticker", str_value).
    """
    if identifier.isdigit():
        return ("cik", int(identifier))
    return ("ticker", identifier.upper())


async def get_company_by_identifier(session: AsyncSession, identifier: str) -> Company | None:
    """Look up a company by ticker or CIK."""
    kind, value = resolve_identifier(identifier)
    if kind == "cik":
        stmt = select(Company).where(Company.cik == value)
    else:
        stmt = select(Company).where(func.upper(Company.ticker) == value)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def search_companies(
    session: AsyncSession,
    q: str | None = None,
    ticker: str | None = None,
    cik: int | None = None,
    sic_code: str | None = None,
    exchange: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[Company], int]:
    """Search companies with filters. Returns (companies, total_count)."""
    stmt = select(Company)
    count_stmt = select(func.count(Company.id))

    conditions: list[ColumnElement[bool]] = []
    if q:
        conditions.append(Company.name.ilike(f"%{q}%"))
    if ticker:
        conditions.append(func.upper(Company.ticker) == ticker.upper())
    if cik:
        conditions.append(Company.cik == cik)
    if sic_code:
        conditions.append(Company.sic_code == sic_code)
    if exchange:
        conditions.append(func.upper(Company.exchange) == exchange.upper())

    if conditions:
        stmt = stmt.where(*conditions)
        count_stmt = count_stmt.where(*conditions)

    total = (await session.execute(count_stmt)).scalar() or 0

    stmt = stmt.order_by(Company.ticker).offset(offset).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all()), total
