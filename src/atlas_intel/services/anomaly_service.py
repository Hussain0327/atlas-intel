"""Statistical anomaly detection across price, fundamental, activity, and sector data.

Uses z-scores and percentile ranks. All computation is read-side from existing data.
"""

import math
import statistics
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.cache import read_cache
from atlas_intel.ingestion.utils import utcnow
from atlas_intel.models.analyst_grade import AnalystGrade
from atlas_intel.models.company import Company
from atlas_intel.models.insider_trade import InsiderTrade
from atlas_intel.models.market_metric import MarketMetric
from atlas_intel.models.material_event import MaterialEvent
from atlas_intel.models.stock_price import StockPrice
from atlas_intel.schemas.anomaly import (
    ActivityAnomalyResponse,
    AllAnomaliesResponse,
    AnomalyPoint,
    FundamentalAnomalyResponse,
    PriceAnomalyResponse,
    SectorAnomalyResponse,
)

DEFAULT_ZSCORE_THRESHOLD = 2.0
DEFAULT_LOOKBACK_DAYS = 90
ANOMALY_CACHE_TTL = 600  # 10 minutes

# Metrics to check for fundamental anomalies
FUNDAMENTAL_METRICS = [
    ("pe_ratio", "P/E Ratio"),
    ("pb_ratio", "P/B Ratio"),
    ("ev_to_ebitda", "EV/EBITDA"),
    ("debt_to_equity", "Debt/Equity"),
    ("roe", "Return on Equity"),
    ("current_ratio", "Current Ratio"),
    ("fcf_yield", "FCF Yield"),
]

# Metrics for sector comparison
SECTOR_METRICS = [
    ("pe_ratio", "P/E Ratio"),
    ("pb_ratio", "P/B Ratio"),
    ("ev_to_ebitda", "EV/EBITDA"),
    ("price_to_sales", "P/S Ratio"),
    ("roe", "ROE"),
    ("debt_to_equity", "Debt/Equity"),
    ("dividend_yield", "Dividend Yield"),
    ("fcf_yield", "FCF Yield"),
]


def _zscore(values: list[float] | list[int], current: float) -> float | None:
    """Z-score of current vs distribution. Returns None if <5 points or zero std."""
    if len(values) < 5:
        return None
    try:
        std = statistics.stdev(values)
    except statistics.StatisticsError:
        return None
    if std == 0:
        return None
    mean = statistics.mean(values)
    return (current - mean) / std


def _percentile_rank(values: list[float], current: float) -> float:
    """Percentile rank (0-100) of current within values."""
    if not values:
        return 50.0
    below = sum(1 for v in values if v < current)
    equal = sum(1 for v in values if v == current)
    return (below + 0.5 * equal) / len(values) * 100


def _detect_anomalies_in_series(
    dates: list[date] | list[date | None],
    values: list[float],
    threshold: float = DEFAULT_ZSCORE_THRESHOLD,
    description_prefix: str = "",
) -> list[AnomalyPoint]:
    """Find anomalous points in a time series by z-score."""
    if len(values) < 5:
        return []
    mean = statistics.mean(values)
    std = statistics.stdev(values)
    if std == 0:
        return []

    anomalies: list[AnomalyPoint] = []
    for i, val in enumerate(values):
        z = (val - mean) / std
        if abs(z) >= threshold:
            direction = "spike" if z > 0 else "drop"
            anomalies.append(
                AnomalyPoint(
                    anomaly_date=dates[i] if i < len(dates) else None,
                    value=round(val, 4),
                    zscore=round(z, 2),
                    description=f"{description_prefix}{direction} (z={z:.1f})",
                )
            )
    return anomalies


async def detect_price_anomalies(
    session: AsyncSession,
    company_id: int,
    ticker: str,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    threshold: float = DEFAULT_ZSCORE_THRESHOLD,
) -> PriceAnomalyResponse:
    """Detect anomalies in price data: volume spikes, return spikes, volatility breakouts."""
    cutoff = date.today() - timedelta(days=lookback_days)

    stmt = (
        select(StockPrice)
        .where(StockPrice.company_id == company_id, StockPrice.price_date >= cutoff)
        .order_by(StockPrice.price_date.asc())
    )
    result = await session.execute(stmt)
    prices = list(result.scalars().all())

    volume_spikes: list[AnomalyPoint] = []
    return_spikes: list[AnomalyPoint] = []
    volatility_breakouts: list[AnomalyPoint] = []

    if len(prices) < 5:
        return PriceAnomalyResponse(
            ticker=ticker,
            lookback_days=lookback_days,
            threshold=threshold,
            computed_at=utcnow(),
        )

    # Volume anomalies: compare each day's volume to 20-day rolling average
    volumes = [int(p.volume) for p in prices if p.volume is not None]
    vol_dates = [p.price_date for p in prices if p.volume is not None]
    if len(volumes) >= 20:
        for i in range(20, len(volumes)):
            window = volumes[i - 20 : i]
            avg = statistics.mean(window)
            if avg > 0:
                ratio = volumes[i] / avg
                if ratio > 1 + threshold:
                    z = _zscore(window, volumes[i])
                    if z is not None and abs(z) >= threshold:
                        volume_spikes.append(
                            AnomalyPoint(
                                anomaly_date=vol_dates[i],
                                value=float(volumes[i]),
                                zscore=round(z, 2),
                                description=f"Volume {ratio:.1f}x 20d avg",
                            )
                        )

    # Return anomalies: daily returns vs historical std
    closes = [float(p.close) for p in prices if p.close is not None]
    close_dates = [p.price_date for p in prices if p.close is not None]
    if len(closes) >= 2:
        returns: list[float] = []
        ret_dates: list[date] = []
        for i in range(1, len(closes)):
            if closes[i - 1] > 0:
                ret = (closes[i] - closes[i - 1]) / closes[i - 1] * 100
                returns.append(ret)
                ret_dates.append(close_dates[i])

        return_spikes = _detect_anomalies_in_series(ret_dates, returns, threshold, "Return ")

    # Volatility breakouts: 5-day realized vol vs 30-day realized vol
    if len(closes) >= 35:
        for i in range(30, len(closes)):
            window_5 = closes[i - 5 : i + 1]
            window_30 = closes[i - 30 : i + 1]

            log_rets_5 = [
                math.log(window_5[j] / window_5[j - 1])
                for j in range(1, len(window_5))
                if window_5[j - 1] > 0 and window_5[j] > 0
            ]
            log_rets_30 = [
                math.log(window_30[j] / window_30[j - 1])
                for j in range(1, len(window_30))
                if window_30[j - 1] > 0 and window_30[j] > 0
            ]

            if len(log_rets_5) >= 2 and len(log_rets_30) >= 5:
                vol_5 = statistics.stdev(log_rets_5) * math.sqrt(252)
                vol_30 = statistics.stdev(log_rets_30) * math.sqrt(252)
                if vol_30 > 0:
                    ratio = vol_5 / vol_30
                    if ratio > 1 + threshold * 0.5:  # Lower threshold for vol breakouts
                        volatility_breakouts.append(
                            AnomalyPoint(
                                anomaly_date=close_dates[i] if i < len(close_dates) else None,
                                value=round(vol_5 * 100, 2),
                                zscore=round(ratio, 2),
                                description=f"5d vol {ratio:.1f}x 30d vol",
                            )
                        )

    total = len(volume_spikes) + len(return_spikes) + len(volatility_breakouts)
    return PriceAnomalyResponse(
        ticker=ticker,
        lookback_days=lookback_days,
        threshold=threshold,
        volume_spikes=volume_spikes,
        return_spikes=return_spikes,
        volatility_breakouts=volatility_breakouts,
        total_anomalies=total,
        computed_at=utcnow(),
    )


async def detect_fundamental_anomalies(
    session: AsyncSession,
    company_id: int,
    ticker: str,
    threshold: float = DEFAULT_ZSCORE_THRESHOLD,
) -> FundamentalAnomalyResponse:
    """Detect anomalies in fundamentals: latest TTM vs historical TTM values."""
    # Get last 8 TTM records for this company
    stmt = (
        select(MarketMetric)
        .where(MarketMetric.company_id == company_id, MarketMetric.period == "TTM")
        .order_by(MarketMetric.period_date.desc())
        .limit(8)
    )
    result = await session.execute(stmt)
    metrics = list(result.scalars().all())

    anomalies: list[AnomalyPoint] = []

    if len(metrics) < 3:
        return FundamentalAnomalyResponse(ticker=ticker, threshold=threshold, computed_at=utcnow())

    latest = metrics[0]
    historical = metrics[1:]

    for attr, label in FUNDAMENTAL_METRICS:
        current_val = getattr(latest, attr, None)
        if current_val is None:
            continue

        hist_vals = [
            float(getattr(m, attr)) for m in historical if getattr(m, attr, None) is not None
        ]
        if not hist_vals:
            continue

        z = _zscore([*hist_vals, float(current_val)], float(current_val))
        if z is not None and abs(z) >= threshold:
            direction = "surge" if z > 0 else "compression"
            anomalies.append(
                AnomalyPoint(
                    anomaly_date=latest.period_date,
                    value=round(float(current_val), 4),
                    zscore=round(z, 2),
                    description=f"{label} {direction}",
                )
            )

    return FundamentalAnomalyResponse(
        ticker=ticker,
        threshold=threshold,
        anomalies=anomalies,
        total_anomalies=len(anomalies),
        computed_at=utcnow(),
    )


async def detect_activity_anomalies(
    session: AsyncSession,
    company_id: int,
    ticker: str,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    threshold: float = DEFAULT_ZSCORE_THRESHOLD,
) -> ActivityAnomalyResponse:
    """Detect anomalies in insider trades, 8-K filings, analyst grade clustering."""
    today = date.today()
    cutoff = today - timedelta(days=lookback_days)

    insider_anomalies: list[AnomalyPoint] = []
    event_anomalies: list[AnomalyPoint] = []
    grade_anomalies: list[AnomalyPoint] = []

    # Insider trade surge: 30-day windows over lookback
    for offset_days in range(0, lookback_days - 29, 30):
        window_start = today - timedelta(days=offset_days + 30)
        window_end = today - timedelta(days=offset_days)
        count_result = await session.execute(
            select(func.count(InsiderTrade.id)).where(
                InsiderTrade.company_id == company_id,
                InsiderTrade.filing_date >= window_start,
                InsiderTrade.filing_date < window_end,
            )
        )
        count = count_result.scalar() or 0

        # Get baseline: 90-day avg monthly rate prior to this window
        baseline_start = window_start - timedelta(days=90)
        baseline_result = await session.execute(
            select(func.count(InsiderTrade.id)).where(
                InsiderTrade.company_id == company_id,
                InsiderTrade.filing_date >= baseline_start,
                InsiderTrade.filing_date < window_start,
            )
        )
        baseline_total = baseline_result.scalar() or 0
        baseline_monthly = baseline_total / 3  # 3 months

        if baseline_monthly > 0 and count > baseline_monthly * (1 + threshold * 0.5):
            z = count / baseline_monthly if baseline_monthly > 0 else 0
            insider_anomalies.append(
                AnomalyPoint(
                    anomaly_date=window_end,
                    value=float(count),
                    zscore=round(z, 2),
                    description=(
                        f"Insider trade surge: {count} trades"
                        f" in 30d (avg {baseline_monthly:.1f}/mo)"
                    ),
                )
            )

    # 8-K filing frequency
    event_count_result = await session.execute(
        select(func.count(MaterialEvent.id)).where(
            MaterialEvent.company_id == company_id,
            MaterialEvent.event_date >= cutoff,
        )
    )
    recent_events = event_count_result.scalar() or 0

    baseline_event_result = await session.execute(
        select(func.count(MaterialEvent.id)).where(
            MaterialEvent.company_id == company_id,
            MaterialEvent.event_date >= cutoff - timedelta(days=lookback_days),
            MaterialEvent.event_date < cutoff,
        )
    )
    baseline_events = baseline_event_result.scalar() or 0

    if baseline_events > 0 and recent_events > baseline_events * (1 + threshold * 0.5):
        ratio = recent_events / baseline_events
        event_anomalies.append(
            AnomalyPoint(
                anomaly_date=today,
                value=float(recent_events),
                zscore=round(ratio, 2),
                description=(
                    f"8-K filing surge: {recent_events} events vs {baseline_events} prior period"
                ),
            )
        )

    # Analyst grade clustering
    grade_count_result = await session.execute(
        select(func.count(AnalystGrade.id)).where(
            AnalystGrade.company_id == company_id,
            AnalystGrade.grade_date >= today - timedelta(days=7),
        )
    )
    recent_grades = grade_count_result.scalar() or 0

    baseline_grade_result = await session.execute(
        select(func.count(AnalystGrade.id)).where(
            AnalystGrade.company_id == company_id,
            AnalystGrade.grade_date >= cutoff,
            AnalystGrade.grade_date < today - timedelta(days=7),
        )
    )
    baseline_grades = baseline_grade_result.scalar() or 0
    weeks_in_baseline = max((lookback_days - 7) / 7, 1)
    baseline_weekly = baseline_grades / weeks_in_baseline

    if baseline_weekly > 0 and recent_grades > baseline_weekly * (1 + threshold * 0.5):
        ratio = recent_grades / baseline_weekly
        grade_anomalies.append(
            AnomalyPoint(
                anomaly_date=today,
                value=float(recent_grades),
                zscore=round(ratio, 2),
                description=(
                    f"Analyst grade clustering: {recent_grades}"
                    f" grades in 7d (avg {baseline_weekly:.1f}/wk)"
                ),
            )
        )

    total = len(insider_anomalies) + len(event_anomalies) + len(grade_anomalies)
    return ActivityAnomalyResponse(
        ticker=ticker,
        lookback_days=lookback_days,
        threshold=threshold,
        insider_anomalies=insider_anomalies,
        event_anomalies=event_anomalies,
        grade_anomalies=grade_anomalies,
        total_anomalies=total,
        computed_at=utcnow(),
    )


async def detect_sector_anomalies(
    session: AsyncSession,
    company_id: int,
    ticker: str,
    threshold: float = DEFAULT_ZSCORE_THRESHOLD,
) -> SectorAnomalyResponse:
    """Detect company metrics that are anomalous vs sector distribution."""
    company = await session.get(Company, company_id)
    sector = company.sector if company else None

    if not sector:
        return SectorAnomalyResponse(ticker=ticker, threshold=threshold, computed_at=utcnow())

    # Get company's latest TTM
    company_metric_stmt = (
        select(MarketMetric)
        .where(MarketMetric.company_id == company_id, MarketMetric.period == "TTM")
        .order_by(MarketMetric.period_date.desc())
        .limit(1)
    )
    result = await session.execute(company_metric_stmt)
    company_metrics = result.scalar_one_or_none()

    if not company_metrics:
        return SectorAnomalyResponse(
            ticker=ticker, sector=sector, threshold=threshold, computed_at=utcnow()
        )

    # Get sector peers' latest TTM (DISTINCT ON subquery)
    latest_sub = (
        select(MarketMetric)
        .where(MarketMetric.period == "TTM")
        .distinct(MarketMetric.company_id)
        .order_by(MarketMetric.company_id, MarketMetric.period_date.desc())
        .subquery()
    )
    stmt = (
        select(latest_sub)
        .join(Company, Company.id == latest_sub.c.company_id)
        .where(Company.sector == sector, Company.id != company_id)
    )
    peer_result = await session.execute(stmt)
    peer_rows = peer_result.all()
    peer_count = len(peer_rows)

    anomalies: list[AnomalyPoint] = []

    for attr, label in SECTOR_METRICS:
        company_val = getattr(company_metrics, attr, None)
        if company_val is None:
            continue

        peer_vals = [
            float(row._mapping[attr]) for row in peer_rows if row._mapping.get(attr) is not None
        ]

        if not peer_vals:
            continue

        z = _zscore(peer_vals, float(company_val))
        if z is not None and abs(z) >= threshold:
            pctile = _percentile_rank(peer_vals, float(company_val))
            direction = "high" if z > 0 else "low"
            anomalies.append(
                AnomalyPoint(
                    anomaly_date=company_metrics.period_date,
                    value=round(float(company_val), 4),
                    zscore=round(z, 2),
                    description=f"{label} anomalously {direction} vs sector (p{pctile:.0f})",
                )
            )

    return SectorAnomalyResponse(
        ticker=ticker,
        sector=sector,
        threshold=threshold,
        peer_count=peer_count,
        anomalies=anomalies,
        total_anomalies=len(anomalies),
        computed_at=utcnow(),
    )


async def detect_all_anomalies(
    session: AsyncSession,
    company_id: int,
    ticker: str,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    threshold: float = DEFAULT_ZSCORE_THRESHOLD,
) -> AllAnomaliesResponse:
    """Detect all anomaly types for a company."""
    price = await detect_price_anomalies(session, company_id, ticker, lookback_days, threshold)
    fundamental = await detect_fundamental_anomalies(session, company_id, ticker, threshold)
    activity = await detect_activity_anomalies(
        session, company_id, ticker, lookback_days, threshold
    )
    sector = await detect_sector_anomalies(session, company_id, ticker, threshold)

    total = (
        price.total_anomalies
        + fundamental.total_anomalies
        + activity.total_anomalies
        + sector.total_anomalies
    )

    return AllAnomaliesResponse(
        ticker=ticker,
        price=price,
        fundamental=fundamental,
        activity=activity,
        sector=sector,
        total_anomalies=total,
        computed_at=utcnow(),
    )


async def detect_all_anomalies_cached(
    session: AsyncSession,
    company_id: int,
    ticker: str,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    threshold: float = DEFAULT_ZSCORE_THRESHOLD,
) -> AllAnomaliesResponse:
    """Cached all-anomalies detection."""
    result = await read_cache.get_or_set(
        f"anomalies:{company_id}:{lookback_days}:{threshold}",
        ANOMALY_CACHE_TTL,
        lambda: detect_all_anomalies(session, company_id, ticker, lookback_days, threshold),
    )
    if isinstance(result, dict):
        return AllAnomaliesResponse(**result)
    return result
