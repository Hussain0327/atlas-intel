"""Unit tests for alert rule seeding."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

SEEDS = "atlas_intel.services.alert_seeds"


@pytest.fixture
def mock_session():
    return AsyncMock()


class TestSeedDefaultAlertRules:
    async def test_skips_when_rules_exist(self, mock_session):
        mock_result = MagicMock()
        mock_result.scalar.return_value = 5
        mock_session.execute.return_value = mock_result

        from atlas_intel.services.alert_seeds import seed_default_alert_rules

        count = await seed_default_alert_rules(mock_session)
        assert count == 0

    async def test_creates_rules_when_empty(self, mock_session):
        count_result = MagicMock()
        count_result.scalar.return_value = 0

        company_result = MagicMock()
        company_result.all.return_value = [(1, "AAPL"), (2, "MSFT")]

        mock_session.execute.side_effect = [count_result, company_result]

        mock_rule = MagicMock()
        mock_rule.id = 1

        with patch(
            f"{SEEDS}.create_alert_rule",
            new_callable=AsyncMock,
            return_value=mock_rule,
        ) as mock_create:
            from atlas_intel.services.alert_seeds import seed_default_alert_rules

            count = await seed_default_alert_rules(mock_session)

        # 2 global + 2 per-company = 4
        assert count == 4
        assert mock_create.call_count == 4

    async def test_creates_only_global_when_no_synced_companies(self, mock_session):
        count_result = MagicMock()
        count_result.scalar.return_value = 0

        company_result = MagicMock()
        company_result.all.return_value = []

        mock_session.execute.side_effect = [count_result, company_result]

        mock_rule = MagicMock()
        mock_rule.id = 1

        with patch(
            f"{SEEDS}.create_alert_rule",
            new_callable=AsyncMock,
            return_value=mock_rule,
        ) as mock_create:
            from atlas_intel.services.alert_seeds import seed_default_alert_rules

            count = await seed_default_alert_rules(mock_session)

        # Only 2 global rules
        assert count == 2
        assert mock_create.call_count == 2
