"""Unit tests for market data transform functions."""

from datetime import date
from decimal import Decimal

import pytest

from atlas_intel.ingestion.market_transforms import (
    parse_company_profile,
    parse_historical_prices,
    parse_key_metrics,
)


class TestParseHistoricalPrices:
    def test_parses_valid_prices(self):
        data = [
            {
                "date": "2024-01-26",
                "open": 194.27,
                "high": 196.17,
                "low": 193.82,
                "close": 192.42,
                "adjClose": 192.42,
                "volume": 44587041,
                "vwap": 194.14,
                "changePercent": -0.9524,
            },
            {
                "date": "2024-01-25",
                "open": 195.22,
                "high": 196.38,
                "low": 193.81,
                "close": 194.17,
                "adjClose": 194.17,
                "volume": 54148506,
            },
        ]
        result = parse_historical_prices(data)
        assert len(result) == 2
        assert result[0]["price_date"] == date(2024, 1, 26)
        assert result[0]["close"] == Decimal("192.42")
        assert result[0]["volume"] == 44587041
        assert result[0]["vwap"] == Decimal("194.14")

    def test_skips_entries_without_close(self):
        data = [
            {"date": "2024-01-26", "open": 194.27, "high": 196.17},
            {"date": "2024-01-25", "close": 194.17},
        ]
        result = parse_historical_prices(data)
        assert len(result) == 1
        assert result[0]["close"] == Decimal("194.17")

    def test_skips_entries_without_date(self):
        data = [{"close": 192.42}]
        result = parse_historical_prices(data)
        assert len(result) == 0

    def test_empty_input(self):
        assert parse_historical_prices([]) == []

    def test_handles_null_close(self):
        data = [{"date": "2024-01-26", "close": None}]
        result = parse_historical_prices(data)
        assert len(result) == 0


class TestParseCompanyProfile:
    def test_parses_full_profile(self):
        data = [
            {
                "sector": "Technology",
                "industry": "Consumer Electronics",
                "country": "US",
                "currency": "USD",
                "ceo": "Mr. Timothy D. Cook",
                "fullTimeEmployees": "161000",
                "description": "Apple Inc. designs...",
                "ipoDate": "1980-12-12",
                "isEtf": False,
                "isActivelyTrading": True,
                "beta": 1.2863,
                "exchangeShortName": "NASDAQ",
                "website": "https://www.apple.com",
            }
        ]
        result = parse_company_profile(data)
        assert result["sector"] == "Technology"
        assert result["industry"] == "Consumer Electronics"
        assert result["ceo"] == "Mr. Timothy D. Cook"
        assert result["full_time_employees"] == 161000
        assert result["ipo_date"] == date(1980, 12, 12)
        assert result["is_etf"] is False
        assert result["is_actively_trading"] is True
        assert result["beta"] == Decimal("1.2863")

    def test_empty_data_returns_empty_dict(self):
        assert parse_company_profile([]) == {}

    def test_handles_missing_fields(self):
        data = [{"sector": "Technology"}]
        result = parse_company_profile(data)
        assert result["sector"] == "Technology"
        assert result["industry"] is None
        assert result["ceo"] is None

    def test_coerces_employees_to_int(self):
        data = [{"fullTimeEmployees": "not_a_number"}]
        result = parse_company_profile(data)
        assert result["full_time_employees"] is None

    def test_handles_empty_string_fields(self):
        data = [{"sector": "", "industry": "", "ceo": ""}]
        result = parse_company_profile(data)
        assert result["sector"] is None
        assert result["industry"] is None
        assert result["ceo"] is None


class TestParseKeyMetrics:
    def test_parses_annual_metrics(self):
        data = [
            {
                "date": "2023-09-30",
                "peRatio": 30.82,
                "pbRatio": 47.89,
                "marketCap": 2987123456789,
                "roe": 1.51,
                "debtToEquity": 1.79,
                "currentRatio": 0.99,
            }
        ]
        result = parse_key_metrics(data, period_type="annual")
        assert len(result) == 1
        assert result[0]["period"] == "annual"
        assert result[0]["period_date"] == date(2023, 9, 30)
        assert result[0]["pe_ratio"] == Decimal("30.82")
        assert result[0]["market_cap"] == Decimal("2987123456789")

    def test_ttm_defaults_date_to_today(self):
        data = [{"peRatioTTM": 30.82, "marketCapTTM": 2987123456789}]
        result = parse_key_metrics(data, period_type="TTM")
        assert len(result) == 1
        assert result[0]["period"] == "TTM"
        assert result[0]["period_date"] == date.today()
        assert result[0]["pe_ratio"] == Decimal("30.82")

    def test_skips_annual_without_date(self):
        data = [{"peRatio": 30.82}]
        result = parse_key_metrics(data, period_type="annual")
        assert len(result) == 0

    def test_empty_input(self):
        assert parse_key_metrics([], period_type="annual") == []

    @pytest.mark.parametrize("bad_value", [None, "N/A", ""])
    def test_handles_bad_metric_values(self, bad_value):
        data = [{"date": "2023-09-30", "peRatio": bad_value}]
        result = parse_key_metrics(data, period_type="annual")
        assert len(result) == 1
        # Bad value should not appear in the result dict
        assert "pe_ratio" not in result[0]
