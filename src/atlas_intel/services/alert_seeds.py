"""Default alert rule seeding for demo/initial setup."""

import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.models.alert_rule import AlertRule
from atlas_intel.models.company import Company
from atlas_intel.schemas.alert import AlertRuleCreate
from atlas_intel.services.alert_service import create_alert_rule

logger = logging.getLogger(__name__)


async def seed_default_alert_rules(session: AsyncSession) -> int:
    """Seed default alert rules if none exist. Returns count of rules created."""
    existing = (await session.execute(select(func.count(AlertRule.id)))).scalar() or 0
    if existing > 0:
        logger.info("Alert rules already exist (%d), skipping seed", existing)
        return 0

    created = 0

    # Global rules (no company_id)
    global_rules = [
        AlertRuleCreate(
            name="Stale Price Data Alert",
            rule_type="freshness_stale",
            conditions={"domain": "prices", "max_age_hours": 72},
            cooldown_minutes=360,
        ),
        AlertRuleCreate(
            name="Unusual Volume Alert",
            rule_type="volume_spike",
            conditions={"multiplier": 2.5},
            cooldown_minutes=60,
        ),
    ]
    for rule_data in global_rules:
        await create_alert_rule(session, rule_data)
        created += 1

    # Per-company anomaly monitors (up to 10 synced companies)
    result = await session.execute(
        select(Company.id, Company.ticker)
        .where(Company.prices_synced_at.is_not(None))
        .order_by(Company.ticker)
        .limit(10)
    )
    companies = result.all()

    for company_id, ticker in companies:
        rule_data = AlertRuleCreate(
            company_id=company_id,
            name=f"Anomaly Monitor — {ticker}",
            rule_type="anomaly_detected",
            conditions={"lookback_days": 90},
            cooldown_minutes=120,
        )
        await create_alert_rule(session, rule_data)
        created += 1

    logger.info("Seeded %d default alert rules", created)
    return created
