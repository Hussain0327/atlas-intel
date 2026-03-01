"""Unit tests for data transforms — no DB, no HTTP."""

from datetime import date
from decimal import Decimal

from atlas_intel.ingestion.transforms import (
    normalize_ticker,
    parse_accession_number,
    parse_company_facts,
    parse_company_tickers,
    parse_date,
    parse_decimal,
    parse_submissions,
)


class TestParseDate:
    def test_valid_date(self):
        assert parse_date("2023-09-30") == date(2023, 9, 30)

    def test_none(self):
        assert parse_date(None) is None

    def test_empty(self):
        assert parse_date("") is None

    def test_invalid(self):
        assert parse_date("not-a-date") is None


class TestParseDecimal:
    def test_integer(self):
        assert parse_decimal(383285000000) == Decimal("383285000000")

    def test_float(self):
        assert parse_decimal(6.16) == Decimal("6.16")

    def test_string(self):
        assert parse_decimal("100.50") == Decimal("100.50")

    def test_none(self):
        assert parse_decimal(None) is None

    def test_invalid(self):
        assert parse_decimal("abc") is None


class TestParseAccessionNumber:
    def test_with_dashes(self):
        assert parse_accession_number("0000320193-23-000106") == "000032019323000106"

    def test_without_dashes(self):
        assert parse_accession_number("000032019323000106") == "000032019323000106"


class TestNormalizeTicker:
    def test_lowercase(self):
        assert normalize_ticker("aapl") == "AAPL"

    def test_whitespace(self):
        assert normalize_ticker("  MSFT  ") == "MSFT"

    def test_none(self):
        assert normalize_ticker(None) is None


class TestParseCompanyTickers:
    def test_basic(self, tickers_json):
        result = parse_company_tickers(tickers_json)
        assert len(result) == 7
        aapl = next(r for r in result if r["ticker"] == "AAPL")
        assert aapl["cik"] == 320193
        assert aapl["name"] == "Apple Inc."


class TestParseSubmissions:
    def test_basic(self, submissions_json):
        company_info, filings = parse_submissions(submissions_json)
        assert company_info["name"] == "Apple Inc."
        assert company_info["sic_code"] == "3571"
        assert company_info["fiscal_year_end"] == "0930"
        assert company_info["exchange"] == "Nasdaq"
        assert len(filings) == 5
        assert filings[0]["form_type"] == "10-K"
        assert filings[0]["filing_date"] == date(2024, 11, 1)
        assert filings[0]["accession_number"] == "000032019324000123"

    def test_empty_filings(self):
        data = {"filings": {"recent": {}}}
        _company_info, filings = parse_submissions(data)
        assert filings == []


class TestParseCompanyFacts:
    def test_basic(self, companyfacts_json):
        facts = parse_company_facts(companyfacts_json)
        assert len(facts) > 0

        # Check revenue entries
        revenue_facts = [f for f in facts if f["concept"] == "Revenues"]
        assert len(revenue_facts) == 3

        fy2023 = next(
            f for f in revenue_facts if f["fiscal_year"] == 2023 and f["fiscal_period"] == "FY"
        )
        assert fy2023["value"] == Decimal("383285000000")
        assert fy2023["unit"] == "USD"
        assert fy2023["period_end"] == date(2023, 9, 30)
        assert fy2023["period_start"] == date(2022, 10, 1)
        assert fy2023["is_instant"] is False
        assert fy2023["taxonomy"] == "us-gaap"

    def test_instant_facts(self, companyfacts_json):
        facts = parse_company_facts(companyfacts_json)
        asset_facts = [f for f in facts if f["concept"] == "Assets"]
        assert all(f["is_instant"] for f in asset_facts)

    def test_dei_taxonomy(self, companyfacts_json):
        facts = parse_company_facts(companyfacts_json)
        dei_facts = [f for f in facts if f["taxonomy"] == "dei"]
        assert len(dei_facts) > 0
        assert dei_facts[0]["concept"] == "EntityCommonStockSharesOutstanding"
