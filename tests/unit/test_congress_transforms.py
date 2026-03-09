"""Unit tests for congress trading transform functions."""

from atlas_intel.ingestion.congress_transforms import parse_congress_trades


class TestParseCongressTrades:
    def test_senate_parse(self):
        senate = [
            {
                "firstName": "John",
                "lastName": "Doe",
                "party": "D",
                "transactionDate": "2025-09-15",
                "disclosureDate": "2025-10-20",
                "type": "Purchase",
                "amount": "$1,001 - $15,000",
                "assetDescription": "Apple Inc. Common Stock",
            }
        ]
        result = parse_congress_trades(senate, [])
        assert len(result) == 1
        assert result[0]["representative"] == "John Doe"
        assert result[0]["party"] == "D"
        assert result[0]["chamber"] == "Senate"
        assert result[0]["transaction_type"] == "purchase"
        assert result[0]["amount_range"] == "$1,001 - $15,000"

    def test_house_parse(self):
        house = [
            {
                "representative": "Bob Johnson",
                "party": "R",
                "transactDate": "2025-07-22",
                "transactionType": "purchase",
                "amount": "$1,001 - $15,000",
            }
        ]
        result = parse_congress_trades([], house)
        assert len(result) == 1
        assert result[0]["representative"] == "Bob Johnson"
        assert result[0]["chamber"] == "House"

    def test_sale_type_normalization(self):
        senate = [
            {
                "firstName": "Jane",
                "lastName": "Smith",
                "party": "R",
                "transactionDate": "2025-08-10",
                "type": "Sale (Full)",
            }
        ]
        result = parse_congress_trades(senate, [])
        assert result[0]["transaction_type"] == "sale"

    def test_missing_representative_skipped(self):
        senate = [{"transactionDate": "2025-08-10", "type": "Purchase"}]
        result = parse_congress_trades(senate, [])
        assert len(result) == 0

    def test_missing_date_skipped(self):
        senate = [{"firstName": "John", "lastName": "Doe", "type": "Purchase"}]
        result = parse_congress_trades(senate, [])
        assert len(result) == 0

    def test_combined_chambers(self):
        senate = [
            {
                "firstName": "Sen",
                "lastName": "A",
                "transactionDate": "2025-09-01",
                "type": "Purchase",
            }
        ]
        house = [
            {
                "representative": "Rep B",
                "transactDate": "2025-09-02",
                "transactionType": "sale",
            }
        ]
        result = parse_congress_trades(senate, house)
        assert len(result) == 2
        assert result[0]["chamber"] == "Senate"
        assert result[1]["chamber"] == "House"

    def test_empty_input(self):
        assert parse_congress_trades([], []) == []
