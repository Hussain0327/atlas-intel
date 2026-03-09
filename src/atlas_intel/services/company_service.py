"""Company business logic."""

from collections.abc import Sequence

from sqlalchemy import ColumnElement, case, func, or_, select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.cache import read_cache
from atlas_intel.models.company import Company
from atlas_intel.schemas.company import CompanyDetail

COMPANY_DETAIL_TTL_SECONDS = 3600


async def invalidate_company_detail_cache(company: Company) -> None:
    """Invalidate cached company-detail reads for ticker and CIK identifiers."""
    if company.ticker:
        await read_cache.invalidate(f"company_detail:{company.ticker.upper()}")
    await read_cache.invalidate(f"company_detail:{company.cik}")


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


async def get_company_detail(session: AsyncSession, identifier: str) -> dict[str, object] | None:
    """Get cached company detail payload for a ticker or CIK."""
    _, value = resolve_identifier(identifier)
    cache_key = f"company_detail:{value}"

    async def _load() -> dict[str, object] | None:
        company = await get_company_by_identifier(session, identifier)
        if not company:
            return None
        return CompanyDetail.model_validate(company).model_dump(mode="json")

    return await read_cache.get_or_set(cache_key, COMPANY_DETAIL_TTL_SECONDS, _load)


def _apply_fallback_name_search(
    q: str,
    conditions: list[ColumnElement[bool]],
) -> tuple[list[ColumnElement[bool]], Sequence[ColumnElement[object]]]:
    conditions.append(Company.name.ilike(f"%{q}%"))
    return conditions, (Company.ticker.asc(),)


async def search_companies(
    session: AsyncSession,
    q: str | None = None,
    ticker: str | None = None,
    cik: int | None = None,
    sic_code: str | None = None,
    exchange: str | None = None,
    sector: str | None = None,
    industry: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[Company], int]:
    """Search companies with filters. Returns (companies, total_count)."""
    stmt = select(Company)
    count_stmt = select(func.count(Company.id))

    conditions: list[ColumnElement[bool]] = []
    order_by: Sequence[ColumnElement[object]] = (Company.ticker.asc(),)
    if q:
        normalized_q = q.strip()
        upper_q = normalized_q.upper()
        similarity_expr = func.coalesce(func.similarity(Company.name, normalized_q), 0.0)
        conditions.append(
            or_(
                func.upper(Company.ticker) == upper_q,
                Company.ticker.ilike(f"{upper_q}%"),
                Company.name.ilike(f"%{normalized_q}%"),
                similarity_expr >= 0.2,
            )
        )
        order_by = (
            case((func.upper(Company.ticker) == upper_q, 0), else_=1).asc(),
            case((Company.ticker.ilike(f"{upper_q}%"), 0), else_=1).asc(),
            similarity_expr.desc(),
            Company.name.asc(),
        )
    if ticker:
        conditions.append(func.upper(Company.ticker) == ticker.upper())
    if cik:
        conditions.append(Company.cik == cik)
    if sic_code:
        conditions.append(Company.sic_code == sic_code)
    if exchange:
        conditions.append(func.upper(Company.exchange) == exchange.upper())
    if sector:
        conditions.append(func.upper(Company.sector) == sector.upper())
    if industry:
        conditions.append(func.upper(Company.industry) == industry.upper())

    if conditions:
        stmt = stmt.where(*conditions)
        count_stmt = count_stmt.where(*conditions)

    try:
        total = (await session.execute(count_stmt)).scalar() or 0
        stmt = stmt.order_by(*order_by).offset(offset).limit(limit)
        result = await session.execute(stmt)
        return list(result.scalars().all()), total
    except DBAPIError:
        if not q:
            raise

    fallback_conditions, fallback_order_by = _apply_fallback_name_search(q, [])
    if ticker:
        fallback_conditions.append(func.upper(Company.ticker) == ticker.upper())
    if cik:
        fallback_conditions.append(Company.cik == cik)
    if sic_code:
        fallback_conditions.append(Company.sic_code == sic_code)
    if exchange:
        fallback_conditions.append(func.upper(Company.exchange) == exchange.upper())
    if sector:
        fallback_conditions.append(func.upper(Company.sector) == sector.upper())
    if industry:
        fallback_conditions.append(func.upper(Company.industry) == industry.upper())

    fallback_stmt = select(Company).where(*fallback_conditions)
    fallback_count_stmt = select(func.count(Company.id)).where(*fallback_conditions)
    total = (await session.execute(fallback_count_stmt)).scalar() or 0
    fallback_stmt = fallback_stmt.order_by(*fallback_order_by).offset(offset).limit(limit)
    result = await session.execute(fallback_stmt)
    return list(result.scalars().all()), total
