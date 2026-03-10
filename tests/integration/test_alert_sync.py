"""Integration tests for post-sync alert hooks."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from atlas_intel.models.alert_rule import AlertRule
from atlas_intel.models.company import Company
from atlas_intel.models.stock_price import StockPrice
from atlas_intel.services.alert_service import (
    check_alerts_for_company,
    create_alert_rule,
    evaluate_rule,
)
from atlas_intel.schemas.alert import AlertRuleCreate


class TestAlertSync:
    async def test_price_threshold_triggers(self, session):
        """Create rule, add price data, verify alert fires."""
        company = Company(cik=320193, ticker="AAPL", name="Apple Inc.")
        session.add(company)
        await session.commit()
        await session.refresh(company)

        # Create alert rule: price < 150
        data = AlertRuleCreate(
            company_id=company.id,
            name="AAPL price below 150",
            rule_type="price_threshold",
            conditions={"field": "close", "op": "lt", "value": 150.0},
        )
        rule = await create_alert_rule(session, data)

        # Add price data below threshold
        price = StockPrice(
            company_id=company.id,
            price_date=datetime.now(UTC).replace(tzinfo=None).date(),
            open=Decimal("148.00"),
            high=Decimal("149.50"),
            low=Decimal("147.00"),
            close=Decimal("148.50"),
            volume=50000000,
        )
        session.add(price)
        await session.commit()

        # Evaluate
        await session.refresh(rule)
        event = await evaluate_rule(session, rule)

        assert event is not None
        assert "148.50" in event.title
        assert event.severity == "warning"
        assert event.rule_type == "price_threshold"

    async def test_price_threshold_not_triggered(self, session):
        """Rule should not fire when condition not met."""
        company = Company(cik=320193, ticker="AAPL", name="Apple Inc.")
        session.add(company)
        await session.commit()
        await session.refresh(company)

        data = AlertRuleCreate(
            company_id=company.id,
            name="AAPL price below 100",
            rule_type="price_threshold",
            conditions={"field": "close", "op": "lt", "value": 100.0},
        )
        rule = await create_alert_rule(session, data)

        price = StockPrice(
            company_id=company.id,
            price_date=datetime.now(UTC).replace(tzinfo=None).date(),
            open=Decimal("148.00"),
            high=Decimal("149.50"),
            low=Decimal("147.00"),
            close=Decimal("148.50"),
            volume=50000000,
        )
        session.add(price)
        await session.commit()

        await session.refresh(rule)
        event = await evaluate_rule(session, rule)
        assert event is None

    async def test_check_alerts_for_company(self, session):
        """Test batch alert checking for a company."""
        company = Company(cik=320193, ticker="AAPL", name="Apple Inc.")
        session.add(company)
        await session.commit()
        await session.refresh(company)

        # Create two rules
        for name, value in [("Rule 1", 200.0), ("Rule 2", 100.0)]:
            data = AlertRuleCreate(
                company_id=company.id,
                name=name,
                rule_type="price_threshold",
                conditions={"field": "close", "op": "lt", "value": value},
            )
            await create_alert_rule(session, data)

        # Add price at 150 — only Rule 1 (< 200) should fire
        price = StockPrice(
            company_id=company.id,
            price_date=datetime.now(UTC).replace(tzinfo=None).date(),
            open=Decimal("150.00"),
            high=Decimal("150.00"),
            low=Decimal("150.00"),
            close=Decimal("150.00"),
            volume=50000000,
        )
        session.add(price)
        await session.commit()

        events = await check_alerts_for_company(session, company.id)
        assert len(events) == 1
        assert "Rule 1" in events[0].title

    async def test_freshness_stale_triggers(self, session):
        """Test freshness_stale rule type."""
        company = Company(cik=320193, ticker="AAPL", name="Apple Inc.")
        session.add(company)
        await session.commit()
        await session.refresh(company)

        data = AlertRuleCreate(
            company_id=company.id,
            name="Stale prices",
            rule_type="freshness_stale",
            conditions={"domain": "prices", "max_age_hours": 1},
        )
        rule = await create_alert_rule(session, data)

        # No prices_synced_at set → should trigger "never synced"
        await session.refresh(rule)
        event = await evaluate_rule(session, rule)
        assert event is not None
        assert "never synced" in event.title
