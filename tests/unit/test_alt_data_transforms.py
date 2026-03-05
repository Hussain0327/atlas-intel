"""Unit tests for alternative data transform functions."""

from datetime import date, datetime
from decimal import Decimal

from atlas_intel.ingestion.alt_data_transforms import (
    parse_analyst_estimates,
    parse_analyst_grades,
    parse_insider_trades,
    parse_institutional_holdings,
    parse_news_articles,
    parse_price_target_consensus,
)


class TestParseNewsArticles:
    def test_parse_valid(self):
        data = [
            {
                "title": "Test Article",
                "url": "https://example.com/1",
                "publishedDate": "2024-01-25 10:00:00",
                "text": "Snippet text",
                "site": "Bloomberg",
                "image": "https://example.com/img.jpg",
            }
        ]
        result = parse_news_articles(data)
        assert len(result) == 1
        assert result[0]["title"] == "Test Article"
        assert result[0]["url"] == "https://example.com/1"
        assert result[0]["published_at"] == datetime(2024, 1, 25, 10, 0, 0)
        assert result[0]["source_name"] == "Bloomberg"
        assert result[0]["snippet"] == "Snippet text"

    def test_skip_missing_title(self):
        data = [{"url": "https://example.com/1", "publishedDate": "2024-01-25 10:00:00"}]
        assert parse_news_articles(data) == []

    def test_skip_missing_url(self):
        data = [{"title": "Test", "publishedDate": "2024-01-25 10:00:00"}]
        assert parse_news_articles(data) == []

    def test_skip_missing_date(self):
        data = [{"title": "Test", "url": "https://example.com/1"}]
        assert parse_news_articles(data) == []

    def test_empty_input(self):
        assert parse_news_articles([]) == []

    def test_null_optional_fields(self):
        data = [
            {
                "title": "Test",
                "url": "https://example.com/1",
                "publishedDate": "2024-01-25 10:00:00",
                "text": None,
                "site": None,
                "image": None,
            }
        ]
        result = parse_news_articles(data)
        assert len(result) == 1
        assert result[0]["snippet"] is None
        assert result[0]["source_name"] is None


class TestParseInsiderTrades:
    def test_parse_valid(self):
        data = [
            {
                "filingDate": "2024-01-20",
                "transactionDate": "2024-01-18",
                "reportingName": "Tim Cook",
                "reportingCik": "0001214156",
                "transactionType": "S",
                "securitiesTransacted": 50000,
                "price": 195.50,
                "securitiesOwned": 3280000,
                "typeOfOwner": "officer",
            }
        ]
        result = parse_insider_trades(data)
        assert len(result) == 1
        assert result[0]["filing_date"] == date(2024, 1, 20)
        assert result[0]["reporting_name"] == "Tim Cook"
        assert result[0]["transaction_type"] == "S"
        assert result[0]["securities_transacted"] == Decimal("50000")
        assert result[0]["price"] == Decimal("195.50")

    def test_skip_missing_filing_date(self):
        data = [{"reportingName": "Tim Cook"}]
        assert parse_insider_trades(data) == []

    def test_skip_missing_reporting_name(self):
        data = [{"filingDate": "2024-01-20"}]
        assert parse_insider_trades(data) == []

    def test_empty_input(self):
        assert parse_insider_trades([]) == []


class TestParseAnalystEstimates:
    def test_parse_valid(self):
        data = [
            {
                "date": "2024-09-30",
                "estimatedRevenueAvg": 394500000000,
                "estimatedEpsAvg": 6.58,
                "estimatedEbitdaAvg": 130000000000,
                "numberAnalystsEstimatedRevenue": 38,
                "numberAnalystEstimatedEps": 35,
            }
        ]
        result = parse_analyst_estimates(data, "annual")
        assert len(result) == 1
        assert result[0]["period"] == "annual"
        assert result[0]["estimate_date"] == date(2024, 9, 30)
        assert result[0]["estimated_eps_avg"] == Decimal("6.58")
        assert result[0]["number_analysts_revenue"] == 38

    def test_skip_missing_date(self):
        data = [{"estimatedEpsAvg": 6.58}]
        assert parse_analyst_estimates(data, "annual") == []

    def test_empty_input(self):
        assert parse_analyst_estimates([], "quarter") == []


class TestParsePriceTargetConsensus:
    def test_parse_valid(self):
        data = [
            {
                "targetHigh": 250.00,
                "targetLow": 160.00,
                "targetConsensus": 210.00,
                "targetMedian": 215.00,
            }
        ]
        result = parse_price_target_consensus(data)
        assert result is not None
        assert result["target_consensus"] == Decimal("210.00")
        assert result["target_high"] == Decimal("250.00")

    def test_empty_returns_none(self):
        assert parse_price_target_consensus([]) is None


class TestParseAnalystGrades:
    def test_parse_valid(self):
        data = [
            {
                "date": "2024-01-26",
                "gradingCompany": "Morgan Stanley",
                "previousGrade": "Equal-Weight",
                "newGrade": "Overweight",
                "action": "upgrade",
            }
        ]
        result = parse_analyst_grades(data)
        assert len(result) == 1
        assert result[0]["grade_date"] == date(2024, 1, 26)
        assert result[0]["grading_company"] == "Morgan Stanley"
        assert result[0]["new_grade"] == "Overweight"

    def test_skip_missing_required_fields(self):
        data = [{"date": "2024-01-26", "gradingCompany": "MS"}]  # missing newGrade
        assert parse_analyst_grades(data) == []

    def test_empty_input(self):
        assert parse_analyst_grades([]) == []


class TestParseInstitutionalHoldings:
    def test_parse_valid(self):
        data = [
            {
                "holder": "Vanguard Group Inc",
                "shares": 1300000000,
                "dateReported": "2024-01-15",
                "change": 5000000,
                "changePercentage": 0.39,
                "marketValue": 253500000000,
                "portfolioPercent": 6.5432,
            }
        ]
        result = parse_institutional_holdings(data)
        assert len(result) == 1
        assert result[0]["holder"] == "Vanguard Group Inc"
        assert result[0]["shares"] == 1300000000
        assert result[0]["date_reported"] == date(2024, 1, 15)

    def test_skip_missing_holder(self):
        data = [{"dateReported": "2024-01-15", "shares": 100}]
        assert parse_institutional_holdings(data) == []

    def test_skip_missing_date(self):
        data = [{"holder": "Vanguard", "shares": 100}]
        assert parse_institutional_holdings(data) == []

    def test_empty_input(self):
        assert parse_institutional_holdings([]) == []
