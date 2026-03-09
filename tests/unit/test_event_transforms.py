"""Unit tests for 8-K event transform functions."""

from atlas_intel.ingestion.event_transforms import classify_event_type, parse_8k_events


class TestClassifyEventType:
    def test_known_items(self):
        assert classify_event_type("1.01") == "acquisition"
        assert classify_event_type("5.02") == "officer_change"
        assert classify_event_type("2.02") == "operating_results"
        assert classify_event_type("2.06") == "impairment"

    def test_unknown_item(self):
        assert classify_event_type("9.99") == "other_event"

    def test_none_item(self):
        assert classify_event_type(None) == "other_event"

    def test_multiple_items_uses_first(self):
        assert classify_event_type("5.02, 8.01") == "officer_change"


class TestParse8kEvents:
    def test_basic_parse(self):
        filings = [
            {
                "filingDate": "2025-11-15",
                "accessionNumber": "0000320193-25-000099",
                "items": "5.02",
                "description": "8-K: Officer Change",
            }
        ]
        result = parse_8k_events(filings)
        assert len(result) == 1
        assert result[0]["event_type"] == "officer_change"
        assert result[0]["item_number"] == "5.02"
        assert result[0]["accession_number"] == "0000320193-25-000099"
        assert result[0]["source"] == "sec_8k"

    def test_multiple_items_per_filing(self):
        filings = [
            {
                "filingDate": "2025-10-01",
                "accessionNumber": "0000320193-25-000088",
                "items": "5.02, 8.01",
                "description": "8-K",
            }
        ]
        result = parse_8k_events(filings)
        assert len(result) == 2
        assert result[0]["event_type"] == "officer_change"
        assert result[1]["event_type"] == "other_event"

    def test_missing_date_skipped(self):
        filings = [
            {
                "filingDate": None,
                "accessionNumber": "test",
                "items": "8.01",
            }
        ]
        result = parse_8k_events(filings)
        assert len(result) == 0

    def test_empty_response(self):
        assert parse_8k_events([]) == []
