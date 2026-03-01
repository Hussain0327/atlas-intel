"""Unit tests for service utilities — no DB needed."""

from atlas_intel.services.company_service import resolve_identifier


class TestResolveIdentifier:
    def test_numeric_is_cik(self):
        kind, value = resolve_identifier("320193")
        assert kind == "cik"
        assert value == 320193

    def test_text_is_ticker(self):
        kind, value = resolve_identifier("AAPL")
        assert kind == "ticker"
        assert value == "AAPL"

    def test_lowercase_ticker(self):
        kind, value = resolve_identifier("aapl")
        assert kind == "ticker"
        assert value == "AAPL"

    def test_mixed_alphanumeric_is_ticker(self):
        kind, value = resolve_identifier("BRK.B")
        assert kind == "ticker"
        assert value == "BRK.B"
