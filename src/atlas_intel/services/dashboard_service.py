"""Dashboard aggregation service."""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.cache import read_cache
from atlas_intel.models.alert_event import AlertEvent
from atlas_intel.models.alert_rule import AlertRule
from atlas_intel.models.company import Company
from atlas_intel.models.market_metric import MarketMetric
from atlas_intel.models.stock_price import StockPrice
from atlas_intel.schemas.dashboard import (
    AlertSummaryResponse,
    DashboardResponse,
    MarketOverview,
    SectorSummary,
    TopMover,
    TopMoversResponse,
)

logger = logging.getLogger(__name__)

DASHBOARD_CACHE_TTL = 300  # 5 minutes


async def get_market_overview(session: AsyncSession) -> MarketOverview:
    """Get market-wide overview: total companies, sector breakdown."""
    total = (await session.execute(select(func.count(Company.id)))).scalar() or 0

    # Fully synced (prices AND metrics)
    with_prices = (
        await session.execute(
            select(func.count(Company.id)).where(
                Company.prices_synced_at.is_not(None),
                Company.metrics_synced_at.is_not(None),
            )
        )
    ).scalar() or 0

    # Companies with SEC data
    with_sec = (
        await session.execute(
            select(func.count(Company.id)).where(Company.facts_synced_at.is_not(None))
        )
    ).scalar() or 0

    # Sector breakdown with avg metrics
    # Subquery for latest TTM metric per company
    latest_metric = (
        select(
            MarketMetric.company_id,
            MarketMetric.pe_ratio,
            MarketMetric.roe,
            MarketMetric.market_cap,
        )
        .where(MarketMetric.period == "TTM")
        .distinct(MarketMetric.company_id)
        .order_by(MarketMetric.company_id, MarketMetric.period_date.desc())
        .subquery()
    )

    sector_stmt = (
        select(
            Company.sector,
            func.count(Company.id).label("cnt"),
            func.avg(latest_metric.c.pe_ratio).label("avg_pe"),
            func.avg(latest_metric.c.roe).label("avg_roe"),
            func.sum(latest_metric.c.market_cap).label("total_mc"),
        )
        .outerjoin(latest_metric, Company.id == latest_metric.c.company_id)
        .where(Company.sector.is_not(None))
        .group_by(Company.sector)
        .order_by(func.count(Company.id).desc())
    )

    result = await session.execute(sector_stmt)
    sectors = [
        SectorSummary(
            sector=row.sector,
            company_count=row.cnt,
            avg_pe=float(row.avg_pe) if row.avg_pe else None,
            avg_roe=float(row.avg_roe) if row.avg_roe else None,
            total_market_cap=float(row.total_mc) if row.total_mc else None,
        )
        for row in result.all()
    ]

    return MarketOverview(
        total_companies=total,
        companies_with_prices=with_prices,
        companies_with_sec_data=with_sec,
        sectors=sectors,
        computed_at=datetime.now(UTC).replace(tzinfo=None),
    )


async def get_top_movers(
    session: AsyncSession, lookback_days: int = 1, limit: int = 10
) -> TopMoversResponse:
    """Get top gainers, losers, and volume leaders."""
    cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=lookback_days + 5)

    # Get latest 2 prices per company to compute change
    # Subquery: latest price per company
    latest_price = (
        select(
            StockPrice.company_id,
            StockPrice.close,
            StockPrice.volume,
            StockPrice.price_date,
            func.row_number()
            .over(partition_by=StockPrice.company_id, order_by=StockPrice.price_date.desc())
            .label("rn"),
        )
        .where(StockPrice.price_date >= cutoff.date())
        .subquery()
    )

    current = (
        select(
            latest_price.c.company_id,
            latest_price.c.close.label("current_close"),
            latest_price.c.volume.label("current_volume"),
        )
        .where(latest_price.c.rn == 1)
        .subquery()
    )

    previous = (
        select(
            latest_price.c.company_id,
            latest_price.c.close.label("prev_close"),
        )
        .where(latest_price.c.rn == 2)
        .subquery()
    )

    # Join with company for ticker/name
    change_stmt = (
        select(
            Company.ticker,
            Company.name,
            current.c.current_close,
            current.c.current_volume,
            previous.c.prev_close,
            case(
                (
                    previous.c.prev_close > 0,
                    (current.c.current_close - previous.c.prev_close) / previous.c.prev_close * 100,
                ),
                else_=None,
            ).label("change_pct"),
        )
        .join(current, Company.id == current.c.company_id)
        .outerjoin(previous, Company.id == previous.c.company_id)
        .where(Company.ticker.is_not(None))
    )

    result = await session.execute(change_stmt)
    rows = result.all()

    gainers: list[TopMover] = []
    losers: list[TopMover] = []
    volume_leaders: list[TopMover] = []

    rows_with_change = [r for r in rows if r.change_pct is not None]
    rows_with_change.sort(key=lambda r: float(r.change_pct), reverse=True)

    for r in rows_with_change[:limit]:
        if float(r.change_pct) > 0:
            gainers.append(
                TopMover(
                    ticker=r.ticker,
                    name=r.name,
                    value=float(r.current_close),
                    change_pct=float(r.change_pct),
                )
            )
    for r in rows_with_change[-limit:]:
        if float(r.change_pct) < 0:
            losers.append(
                TopMover(
                    ticker=r.ticker,
                    name=r.name,
                    value=float(r.current_close),
                    change_pct=float(r.change_pct),
                )
            )
    losers.sort(key=lambda m: m.change_pct or 0)

    rows_with_volume = [r for r in rows if r.current_volume and float(r.current_volume) > 0]
    rows_with_volume.sort(key=lambda r: float(r.current_volume), reverse=True)
    for r in rows_with_volume[:limit]:
        volume_leaders.append(
            TopMover(
                ticker=r.ticker,
                name=r.name,
                value=float(r.current_volume),
                change_pct=float(r.change_pct) if r.change_pct else None,
            )
        )

    return TopMoversResponse(
        gainers=gainers,
        losers=losers,
        volume_leaders=volume_leaders,
        lookback_days=lookback_days,
        computed_at=datetime.now(UTC).replace(tzinfo=None),
    )


async def get_alert_summary(session: AsyncSession) -> AlertSummaryResponse:
    """Get alert summary: rule counts, recent events."""
    total_rules = (await session.execute(select(func.count(AlertRule.id)))).scalar() or 0
    active_rules = (
        await session.execute(select(func.count(AlertRule.id)).where(AlertRule.enabled.is_(True)))
    ).scalar() or 0

    now = datetime.now(UTC).replace(tzinfo=None)
    day_ago = now - timedelta(days=1)
    week_ago = now - timedelta(days=7)

    events_24h = (
        await session.execute(
            select(func.count(AlertEvent.id)).where(AlertEvent.triggered_at >= day_ago)
        )
    ).scalar() or 0

    events_7d = (
        await session.execute(
            select(func.count(AlertEvent.id)).where(AlertEvent.triggered_at >= week_ago)
        )
    ).scalar() or 0

    critical_24h = (
        await session.execute(
            select(func.count(AlertEvent.id)).where(
                AlertEvent.triggered_at >= day_ago,
                AlertEvent.severity == "critical",
            )
        )
    ).scalar() or 0

    # Recent events
    recent_result = await session.execute(
        select(AlertEvent).order_by(AlertEvent.triggered_at.desc()).limit(5)
    )
    recent = [
        {
            "id": e.id,
            "title": e.title,
            "severity": e.severity,
            "triggered_at": str(e.triggered_at),
            "acknowledged": e.acknowledged,
        }
        for e in recent_result.scalars().all()
    ]

    return AlertSummaryResponse(
        total_rules=total_rules,
        active_rules=active_rules,
        total_events_24h=events_24h,
        total_events_7d=events_7d,
        critical_events_24h=critical_24h,
        recent_events=recent,
        computed_at=now,
    )


async def get_full_dashboard_cached(session: AsyncSession) -> DashboardResponse:
    """Get full dashboard, cached for 5 minutes."""

    async def _load() -> DashboardResponse:
        overview = await get_market_overview(session)
        movers = await get_top_movers(session)
        alerts = await get_alert_summary(session)
        return DashboardResponse(
            market_overview=overview,
            top_movers=movers,
            alert_summary=alerts,
            computed_at=datetime.now(UTC).replace(tzinfo=None),
        )

    return await read_cache.get_or_set("dashboard:full", DASHBOARD_CACHE_TTL, _load)
