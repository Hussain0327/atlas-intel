"""Analyst estimates, grades, and price target business logic."""

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.cache import read_cache
from atlas_intel.models.analyst_estimate import AnalystEstimate
from atlas_intel.models.analyst_grade import AnalystGrade
from atlas_intel.models.price_target import PriceTarget
from atlas_intel.models.stock_price import StockPrice

ANALYST_CONSENSUS_TTL_SECONDS = 900


async def invalidate_analyst_consensus_cache(company_id: int) -> None:
    """Invalidate cached analyst consensus for a company."""
    await read_cache.invalidate(f"analyst_consensus:{company_id}")


async def get_analyst_estimates(
    session: AsyncSession,
    company_id: int,
    period: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[AnalystEstimate], int]:
    """Query analyst estimates paginated with optional period filter."""
    base_where = [AnalystEstimate.company_id == company_id]
    if period:
        base_where.append(AnalystEstimate.period == period)

    count_stmt = select(func.count(AnalystEstimate.id)).where(*base_where)
    total = (await session.execute(count_stmt)).scalar() or 0

    stmt = (
        select(AnalystEstimate)
        .where(*base_where)
        .order_by(AnalystEstimate.estimate_date.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all()), total


async def get_analyst_grades(
    session: AsyncSession,
    company_id: int,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[AnalystGrade], int]:
    """Query analyst grades paginated."""
    count_stmt = select(func.count(AnalystGrade.id)).where(AnalystGrade.company_id == company_id)
    total = (await session.execute(count_stmt)).scalar() or 0

    stmt = (
        select(AnalystGrade)
        .where(AnalystGrade.company_id == company_id)
        .order_by(AnalystGrade.grade_date.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all()), total


async def get_price_target(
    session: AsyncSession,
    company_id: int,
) -> PriceTarget | None:
    """Get price target consensus for a company."""
    result = await session.execute(select(PriceTarget).where(PriceTarget.company_id == company_id))
    return result.scalar_one_or_none()


async def get_analyst_consensus(
    session: AsyncSession,
    company_id: int,
    ticker: str,
) -> dict[str, Any]:
    """Fused analyst consensus: price target + latest estimate + grade distribution + upside."""
    consensus: dict[str, Any] = {"ticker": ticker}

    # Price target
    target = await get_price_target(session, company_id)
    if target:
        consensus["target_consensus"] = target.target_consensus
        consensus["target_high"] = target.target_high
        consensus["target_low"] = target.target_low

    # Current price (latest close)
    price_result = await session.execute(
        select(StockPrice.close)
        .where(StockPrice.company_id == company_id)
        .order_by(StockPrice.price_date.desc())
        .limit(1)
    )
    current_price: Decimal | None = price_result.scalar_one_or_none()
    consensus["current_price"] = current_price

    # Upside %
    if current_price and target and target.target_consensus and current_price > 0:
        upside = float((target.target_consensus - current_price) / current_price * 100)
        consensus["upside_pct"] = round(upside, 2)
    else:
        consensus["upside_pct"] = None

    # Latest estimate
    latest_est_result = await session.execute(
        select(AnalystEstimate)
        .where(AnalystEstimate.company_id == company_id)
        .order_by(AnalystEstimate.estimate_date.desc())
        .limit(1)
    )
    latest_est = latest_est_result.scalar_one_or_none()
    if latest_est:
        consensus["latest_eps_estimate"] = latest_est.estimated_eps_avg
        consensus["latest_revenue_estimate"] = latest_est.estimated_revenue_avg
    else:
        consensus["latest_eps_estimate"] = None
        consensus["latest_revenue_estimate"] = None

    # Grade distribution (last 90 days)
    cutoff = date.today() - timedelta(days=90)
    grades_result = await session.execute(
        select(AnalystGrade.action, func.count(AnalystGrade.id))
        .where(
            AnalystGrade.company_id == company_id,
            AnalystGrade.grade_date >= cutoff,
        )
        .group_by(AnalystGrade.action)
    )
    grade_dist: dict[str, int] = {}
    for action, cnt in grades_result.all():
        if action:
            grade_dist[action] = cnt
    consensus["grade_distribution"] = grade_dist

    # Sentiment from upside
    if consensus["upside_pct"] is not None:
        if consensus["upside_pct"] >= 10:
            consensus["sentiment"] = "bullish"
        elif consensus["upside_pct"] <= -10:
            consensus["sentiment"] = "bearish"
        else:
            consensus["sentiment"] = "neutral"
    else:
        consensus["sentiment"] = "neutral"

    return consensus


async def get_analyst_consensus_cached(
    session: AsyncSession,
    company_id: int,
    ticker: str,
) -> dict[str, Any]:
    """Get cached analyst consensus view."""
    return await read_cache.get_or_set(
        f"analyst_consensus:{company_id}",
        ANALYST_CONSENSUS_TTL_SECONDS,
        lambda: get_analyst_consensus(session, company_id, ticker),
    )
