"""Unit tests for FRED transform functions."""

from decimal import Decimal

from atlas_intel.ingestion.fred_transforms import parse_fred_observations


class TestParseFredObservations:
    def test_basic_parse(self):
        data = {
            "observations": [
                {"date": "2024-01-01", "value": "27956.998"},
                {"date": "2024-04-01", "value": "28628.121"},
            ]
        }
        result = parse_fred_observations(data, "GDP")
        assert len(result) == 2
        assert result[0]["series_id"] == "GDP"
        assert result[0]["observation_date"].isoformat() == "2024-01-01"
        assert result[0]["value"] == Decimal("27956.998")

    def test_missing_value_dot(self):
        """FRED uses '.' for missing/unavailable values."""
        data = {
            "observations": [
                {"date": "2025-01-01", "value": "."},
            ]
        }
        result = parse_fred_observations(data, "GDP")
        assert len(result) == 1
        assert result[0]["value"] is None

    def test_missing_date_skipped(self):
        data = {
            "observations": [
                {"date": None, "value": "100"},
            ]
        }
        result = parse_fred_observations(data, "UNRATE")
        assert len(result) == 0

    def test_empty_observations(self):
        data = {"observations": []}
        result = parse_fred_observations(data, "GDP")
        assert result == []

    def test_missing_observations_key(self):
        data = {}
        result = parse_fred_observations(data, "GDP")
        assert result == []

    def test_negative_value(self):
        data = {
            "observations": [
                {"date": "2020-04-01", "value": "-5.3"},
            ]
        }
        result = parse_fred_observations(data, "GDP")
        assert result[0]["value"] == Decimal("-5.3")
