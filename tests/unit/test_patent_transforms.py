"""Unit tests for patent transform functions."""

import json
from pathlib import Path

from atlas_intel.ingestion.patent_transforms import parse_patents

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


class TestParsePatents:
    def test_basic_parse(self):
        data = json.loads((FIXTURES_DIR / "uspto_patents.json").read_text())
        result = parse_patents(data)
        assert len(result) == 3

        # First patent
        p = result[0]
        assert p["patent_number"] == "US-12345678-B2"
        assert p["title"] == "Systems and Methods for Machine Learning Inference"
        assert p["grant_date"].isoformat() == "2025-06-15"
        assert p["application_date"].isoformat() == "2023-03-10"
        assert p["patent_type"] == "utility"
        assert p["cpc_class"] == "G06N3/08"
        assert p["citation_count"] == 42

    def test_design_patent_no_cpc(self):
        data = json.loads((FIXTURES_DIR / "uspto_patents.json").read_text())
        result = parse_patents(data)
        design = result[2]
        assert design["patent_type"] == "design"
        assert design["cpc_class"] is None
        assert design["abstract"] is None

    def test_missing_patent_number_skipped(self):
        data = {"patents": [{"patent_title": "No number"}]}
        result = parse_patents(data)
        assert len(result) == 0

    def test_empty_patents(self):
        assert parse_patents({"patents": []}) == []
        assert parse_patents({}) == []
