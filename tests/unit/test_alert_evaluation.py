"""Unit tests for alert rule evaluation logic."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from atlas_intel.services.alert_service import COMPARE_OPS, evaluate_rule


class TestCompareOps:
    def test_gt(self):
        assert COMPARE_OPS["gt"](5, 3) is True
        assert COMPARE_OPS["gt"](3, 5) is False

    def test_gte(self):
        assert COMPARE_OPS["gte"](5, 5) is True
        assert COMPARE_OPS["gte"](4, 5) is False

    def test_lt(self):
        assert COMPARE_OPS["lt"](3, 5) is True
        assert COMPARE_OPS["lt"](5, 3) is False

    def test_lte(self):
        assert COMPARE_OPS["lte"](5, 5) is True
        assert COMPARE_OPS["lte"](6, 5) is False

    def test_eq(self):
        assert COMPARE_OPS["eq"](5, 5) is True
        assert COMPARE_OPS["eq"](5, 6) is False


class TestEvaluateRule:
    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.fixture
    def make_rule(self):
        def _make(
            rule_type="price_threshold",
            conditions=None,
            company_id=1,
            enabled=True,
            cooldown_minutes=60,
            last_triggered_at=None,
        ):
            rule = MagicMock()
            rule.id = 1
            rule.rule_type = rule_type
            rule.conditions = conditions or {}
            rule.company_id = company_id
            rule.enabled = enabled
            rule.cooldown_minutes = cooldown_minutes
            rule.last_triggered_at = last_triggered_at
            rule.trigger_count = 0
            rule.name = "Test Rule"
            return rule

        return _make

    async def test_disabled_rule_not_evaluated(self, mock_session, make_rule):
        rule = make_rule(enabled=False)
        result = await evaluate_rule(mock_session, rule)
        assert result is None

    async def test_cooldown_prevents_trigger(self, mock_session, make_rule):
        rule = make_rule(
            last_triggered_at=datetime.now(UTC).replace(tzinfo=None),
            cooldown_minutes=60,
        )
        result = await evaluate_rule(mock_session, rule)
        assert result is None

    async def test_cooldown_expired_allows_trigger(self, mock_session, make_rule):
        rule = make_rule(
            rule_type="price_threshold",
            conditions={"field": "close", "op": "lt", "value": 200.0},
            last_triggered_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=2),
        )

        mock_price = MagicMock()
        mock_price.close = 150.0

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_price
        mock_session.execute.return_value = mock_result

        mock_event = MagicMock()
        mock_session.refresh = AsyncMock()

        with patch("atlas_intel.services.alert_service.AlertEvent") as MockEvent:
            MockEvent.return_value = mock_event
            result = await evaluate_rule(mock_session, rule)

        assert result is not None

    async def test_price_threshold_no_company(self, mock_session, make_rule):
        rule = make_rule(company_id=None)
        result = await evaluate_rule(mock_session, rule)
        assert result is None

    async def test_price_threshold_no_price_data(self, mock_session, make_rule):
        rule = make_rule(
            conditions={"field": "close", "op": "lt", "value": 100},
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await evaluate_rule(mock_session, rule)
        assert result is None

    async def test_price_threshold_condition_not_met(self, mock_session, make_rule):
        rule = make_rule(
            conditions={"field": "close", "op": "lt", "value": 100},
        )
        mock_price = MagicMock()
        mock_price.close = 150.0  # above threshold

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_price
        mock_session.execute.return_value = mock_result

        result = await evaluate_rule(mock_session, rule)
        assert result is None

    async def test_evaluation_exception_returns_none(self, mock_session, make_rule):
        rule = make_rule(conditions={"field": "close", "op": "lt", "value": 100})
        mock_session.execute.side_effect = Exception("DB error")

        result = await evaluate_rule(mock_session, rule)
        assert result is None
