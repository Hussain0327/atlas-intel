"""Alert rule CRUD and evaluation engine."""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.models.alert_event import AlertEvent
from atlas_intel.models.alert_rule import AlertRule
from atlas_intel.models.stock_price import StockPrice
from atlas_intel.schemas.alert import AlertRuleCreate, AlertRuleUpdate

logger = logging.getLogger(__name__)

VALID_RULE_TYPES = {
    "price_threshold",
    "volume_spike",
    "signal_drop",
    "anomaly_detected",
    "freshness_stale",
    "metric_threshold",
}

COMPARE_OPS: dict[str, Any] = {
    "gt": lambda a, b: a > b,
    "gte": lambda a, b: a >= b,
    "lt": lambda a, b: a < b,
    "lte": lambda a, b: a <= b,
    "eq": lambda a, b: a == b,
}


# ── CRUD ──────────────────────────────────────────────────────────────────────


async def create_alert_rule(session: AsyncSession, data: AlertRuleCreate) -> AlertRule:
    """Create a new alert rule."""
    rule = AlertRule(
        company_id=data.company_id,
        name=data.name,
        rule_type=data.rule_type,
        conditions=data.conditions,
        enabled=data.enabled,
        cooldown_minutes=data.cooldown_minutes,
    )
    session.add(rule)
    await session.commit()
    await session.refresh(rule)
    return rule


async def list_alert_rules(
    session: AsyncSession,
    company_id: int | None = None,
    enabled_only: bool = False,
) -> list[AlertRule]:
    """List alert rules with optional filters."""
    stmt = select(AlertRule).order_by(AlertRule.created_at.desc())
    if company_id is not None:
        stmt = stmt.where(AlertRule.company_id == company_id)
    if enabled_only:
        stmt = stmt.where(AlertRule.enabled.is_(True))
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_alert_rule(session: AsyncSession, rule_id: int) -> AlertRule | None:
    """Get a single alert rule by ID."""
    result = await session.execute(select(AlertRule).where(AlertRule.id == rule_id))
    return result.scalar_one_or_none()


async def update_alert_rule(
    session: AsyncSession, rule_id: int, data: AlertRuleUpdate
) -> AlertRule | None:
    """Update an alert rule."""
    rule = await get_alert_rule(session, rule_id)
    if not rule:
        return None

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(rule, key, value)

    await session.commit()
    await session.refresh(rule)
    return rule


async def delete_alert_rule(session: AsyncSession, rule_id: int) -> bool:
    """Delete an alert rule."""
    result = await session.execute(delete(AlertRule).where(AlertRule.id == rule_id))
    await session.commit()
    return (result.rowcount or 0) > 0  # type: ignore[attr-defined]


# ── Events ────────────────────────────────────────────────────────────────────


async def list_alert_events(
    session: AsyncSession,
    company_id: int | None = None,
    rule_id: int | None = None,
    unacknowledged_only: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[AlertEvent], int, int]:
    """List alert events. Returns (events, total_count, unacknowledged_count)."""
    stmt = select(AlertEvent).order_by(AlertEvent.triggered_at.desc())
    count_stmt = select(func.count(AlertEvent.id))
    unack_stmt = select(func.count(AlertEvent.id)).where(AlertEvent.acknowledged.is_(False))

    if company_id is not None:
        stmt = stmt.where(AlertEvent.company_id == company_id)
        count_stmt = count_stmt.where(AlertEvent.company_id == company_id)
        unack_stmt = unack_stmt.where(AlertEvent.company_id == company_id)
    if rule_id is not None:
        stmt = stmt.where(AlertEvent.rule_id == rule_id)
        count_stmt = count_stmt.where(AlertEvent.rule_id == rule_id)
        unack_stmt = unack_stmt.where(AlertEvent.rule_id == rule_id)
    if unacknowledged_only:
        stmt = stmt.where(AlertEvent.acknowledged.is_(False))

    stmt = stmt.offset(offset).limit(limit)

    result = await session.execute(stmt)
    events = list(result.scalars().all())
    total = (await session.execute(count_stmt)).scalar() or 0
    unack = (await session.execute(unack_stmt)).scalar() or 0

    return events, total, unack


async def acknowledge_event(session: AsyncSession, event_id: int) -> AlertEvent | None:
    """Acknowledge a single alert event."""
    result = await session.execute(select(AlertEvent).where(AlertEvent.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        return None

    event.acknowledged = True
    event.acknowledged_at = datetime.now(UTC).replace(tzinfo=None)
    await session.commit()
    await session.refresh(event)
    return event


async def acknowledge_all_events(session: AsyncSession, company_id: int | None = None) -> int:
    """Acknowledge all unacknowledged events. Returns count acknowledged."""
    now = datetime.now(UTC).replace(tzinfo=None)
    stmt = (
        update(AlertEvent)
        .where(AlertEvent.acknowledged.is_(False))
        .values(acknowledged=True, acknowledged_at=now)
    )
    if company_id is not None:
        stmt = stmt.where(AlertEvent.company_id == company_id)

    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount or 0  # type: ignore[attr-defined]


# ── Evaluation Engine ─────────────────────────────────────────────────────────


async def evaluate_rule(session: AsyncSession, rule: AlertRule) -> AlertEvent | None:
    """Evaluate a single alert rule. Returns AlertEvent if triggered, else None."""
    if not rule.enabled:
        return None

    # Check cooldown
    if rule.last_triggered_at:
        cooldown_until = rule.last_triggered_at + timedelta(minutes=rule.cooldown_minutes)
        if datetime.now(UTC).replace(tzinfo=None) < cooldown_until:
            return None

    try:
        result = await _evaluate_by_type(session, rule)
    except Exception:
        logger.exception("Failed to evaluate rule %d (%s)", rule.id, rule.name)
        return None

    if result is None:
        return None

    title, detail, severity, data = result
    now = datetime.now(UTC).replace(tzinfo=None)

    event = AlertEvent(
        rule_id=rule.id,
        company_id=rule.company_id,
        triggered_at=now,
        rule_type=rule.rule_type,
        severity=severity,
        title=title,
        detail=detail,
        data=data,
    )
    session.add(event)

    rule.last_triggered_at = now
    rule.trigger_count = (rule.trigger_count or 0) + 1

    await session.commit()
    await session.refresh(event)
    return event


async def _evaluate_by_type(
    session: AsyncSession, rule: AlertRule
) -> tuple[str, str | None, str, dict[str, Any] | None] | None:
    """Dispatch evaluation by rule type. Returns (title, detail, severity, data) or None."""
    conditions = rule.conditions or {}

    if rule.rule_type == "price_threshold":
        return await _eval_price_threshold(session, rule, conditions)
    if rule.rule_type == "volume_spike":
        return await _eval_volume_spike(session, rule, conditions)
    if rule.rule_type == "signal_drop":
        return await _eval_signal_drop(session, rule, conditions)
    if rule.rule_type == "anomaly_detected":
        return await _eval_anomaly_detected(session, rule, conditions)
    if rule.rule_type == "freshness_stale":
        return await _eval_freshness_stale(session, rule, conditions)
    if rule.rule_type == "metric_threshold":
        return await _eval_metric_threshold(session, rule, conditions)

    return None


async def _eval_price_threshold(
    session: AsyncSession, rule: AlertRule, conditions: dict[str, Any]
) -> tuple[str, str | None, str, dict[str, Any] | None] | None:
    """Evaluate price threshold rule."""
    if not rule.company_id:
        return None

    field = conditions.get("field", "close")
    op = conditions.get("op", "lt")
    value = conditions.get("value")
    if value is None:
        return None

    stmt = (
        select(StockPrice)
        .where(StockPrice.company_id == rule.company_id)
        .order_by(StockPrice.price_date.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    price = result.scalar_one_or_none()
    if not price:
        return None

    actual = float(getattr(price, field, 0) or 0)
    compare_fn = COMPARE_OPS.get(op)
    if not compare_fn or not compare_fn(actual, float(value)):
        return None

    return (
        f"{rule.name}: {field}={actual:.2f} {op} {value}",
        f"Latest price {field} is {actual:.2f}, threshold was {op} {value}",
        "warning",
        {"field": field, "actual": actual, "threshold": value, "op": op},
    )


async def _eval_volume_spike(
    session: AsyncSession, rule: AlertRule, conditions: dict[str, Any]
) -> tuple[str, str | None, str, dict[str, Any] | None] | None:
    """Evaluate volume spike rule."""
    if not rule.company_id:
        return None

    multiplier = float(conditions.get("multiplier", 2.0))

    stmt = (
        select(StockPrice)
        .where(StockPrice.company_id == rule.company_id)
        .order_by(StockPrice.price_date.desc())
        .limit(21)
    )
    result = await session.execute(stmt)
    prices = list(result.scalars().all())
    if len(prices) < 2:
        return None

    latest = prices[0]
    avg_volume = sum(float(p.volume or 0) for p in prices[1:]) / len(prices[1:])

    if avg_volume <= 0:
        return None

    latest_volume = float(latest.volume or 0)
    ratio = latest_volume / avg_volume

    if ratio < multiplier:
        return None

    return (
        f"{rule.name}: volume spike {ratio:.1f}x average",
        f"Volume {latest_volume:,.0f} is {ratio:.1f}x the 20-day average of {avg_volume:,.0f}",
        "warning" if ratio < 3.0 else "critical",
        {"volume": latest_volume, "avg_volume": avg_volume, "ratio": ratio},
    )


async def _eval_signal_drop(
    session: AsyncSession, rule: AlertRule, conditions: dict[str, Any]
) -> tuple[str, str | None, str, dict[str, Any] | None] | None:
    """Evaluate signal drop rule."""
    if not rule.company_id:
        return None

    signal_type = conditions.get("signal_type", "sentiment")
    threshold = float(conditions.get("threshold", 0.0))

    from atlas_intel.services.fusion_service import (
        compute_growth_signal,
        compute_risk_signal,
        compute_sentiment_signal,
        compute_smart_money_signal,
    )

    compute_fn = {
        "sentiment": compute_sentiment_signal,
        "growth": compute_growth_signal,
        "risk": compute_risk_signal,
        "smart_money": compute_smart_money_signal,
    }.get(signal_type)

    if not compute_fn:
        return None

    signal = await compute_fn(session, rule.company_id)
    if signal.score is None:
        return None

    if signal.score >= threshold:
        return None

    return (
        f"{rule.name}: {signal_type} signal at {signal.score:.2f}",
        f"{signal_type} signal dropped to {signal.score:.2f} (threshold: {threshold})",
        "warning" if signal.score > -0.3 else "critical",
        {"signal_type": signal_type, "score": signal.score, "threshold": threshold},
    )


async def _eval_anomaly_detected(
    session: AsyncSession, rule: AlertRule, conditions: dict[str, Any]
) -> tuple[str, str | None, str, dict[str, Any] | None] | None:
    """Evaluate anomaly detection rule."""
    if not rule.company_id:
        return None

    from atlas_intel.models.company import Company

    result = await session.execute(select(Company).where(Company.id == rule.company_id))
    company = result.scalar_one_or_none()
    if not company:
        return None

    from atlas_intel.services.anomaly_service import detect_all_anomalies_cached

    ticker = company.ticker or str(company.cik)
    lookback = int(conditions.get("lookback_days", 90))
    threshold = float(conditions.get("threshold", 2.0))

    anomalies = await detect_all_anomalies_cached(
        session, rule.company_id, ticker, lookback_days=lookback, threshold=threshold
    )

    if anomalies.total_anomalies == 0:
        return None

    return (
        f"{rule.name}: {anomalies.total_anomalies} anomalies detected",
        f"Found {anomalies.total_anomalies} anomalies for {ticker}",
        "info" if anomalies.total_anomalies < 3 else "warning",
        {"total_anomalies": anomalies.total_anomalies, "ticker": ticker},
    )


async def _eval_freshness_stale(
    session: AsyncSession, rule: AlertRule, conditions: dict[str, Any]
) -> tuple[str, str | None, str, dict[str, Any] | None] | None:
    """Evaluate data freshness rule."""
    if not rule.company_id:
        return None

    from atlas_intel.models.company import Company

    result = await session.execute(select(Company).where(Company.id == rule.company_id))
    company = result.scalar_one_or_none()
    if not company:
        return None

    domain = conditions.get("domain", "prices")
    max_age_hours = int(conditions.get("max_age_hours", 48))

    field_map = {
        "prices": "prices_synced_at",
        "profile": "profile_synced_at",
        "metrics": "metrics_synced_at",
        "news": "news_synced_at",
        "insider": "insider_trades_synced_at",
        "transcripts": "transcripts_synced_at",
        "filings": "submissions_synced_at",
    }

    attr = field_map.get(domain)
    if not attr:
        return None

    synced_at = getattr(company, attr, None)
    if synced_at is None:
        return (
            f"{rule.name}: {domain} never synced for {company.ticker}",
            f"{domain} data has never been synced for {company.ticker}",
            "warning",
            {"domain": domain, "ticker": company.ticker},
        )

    now = datetime.now(UTC).replace(tzinfo=None)
    age_hours = (now - synced_at).total_seconds() / 3600

    if age_hours <= max_age_hours:
        return None

    return (
        f"{rule.name}: {domain} data is {age_hours:.0f}h old for {company.ticker}",
        f"{domain} data last synced {age_hours:.0f} hours ago (threshold: {max_age_hours}h)",
        "info" if age_hours < max_age_hours * 2 else "warning",
        {"domain": domain, "age_hours": age_hours, "max_age_hours": max_age_hours},
    )


async def _eval_metric_threshold(
    session: AsyncSession, rule: AlertRule, conditions: dict[str, Any]
) -> tuple[str, str | None, str, dict[str, Any] | None] | None:
    """Evaluate metric threshold rule."""
    if not rule.company_id:
        return None

    from atlas_intel.models.market_metric import MarketMetric

    field = conditions.get("field", "pe_ratio")
    op = conditions.get("op", "gt")
    value = conditions.get("value")
    if value is None:
        return None

    stmt = (
        select(MarketMetric)
        .where(MarketMetric.company_id == rule.company_id, MarketMetric.period == "TTM")
        .order_by(MarketMetric.period_date.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    metric = result.scalar_one_or_none()
    if not metric:
        return None

    actual = float(getattr(metric, field, 0) or 0)
    compare_fn = COMPARE_OPS.get(op)
    if not compare_fn or not compare_fn(actual, float(value)):
        return None

    return (
        f"{rule.name}: {field}={actual:.2f} {op} {value}",
        f"Metric {field} is {actual:.2f}, threshold was {op} {value}",
        "warning",
        {"field": field, "actual": actual, "threshold": value, "op": op},
    )


# ── Batch Evaluation ──────────────────────────────────────────────────────────


async def check_alerts_for_company(session: AsyncSession, company_id: int) -> list[AlertEvent]:
    """Evaluate all enabled rules for a company. Returns triggered events."""
    rules = await list_alert_rules(session, company_id=company_id, enabled_only=True)
    # Also include global rules (company_id is None)
    global_rules = await list_alert_rules(session, enabled_only=True)
    global_rules = [r for r in global_rules if r.company_id is None]

    events: list[AlertEvent] = []
    for rule in rules + global_rules:
        event = await evaluate_rule(session, rule)
        if event:
            events.append(event)

    return events


async def check_all_alerts(session: AsyncSession) -> list[AlertEvent]:
    """Evaluate all enabled rules. Returns triggered events."""
    rules = await list_alert_rules(session, enabled_only=True)
    events: list[AlertEvent] = []
    for rule in rules:
        event = await evaluate_rule(session, rule)
        if event:
            events.append(event)
    return events
