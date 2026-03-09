"""Unit tests for screening logic (pure functions, no DB)."""

from atlas_intel.schemas.screening import ScreenFilter
from atlas_intel.services.screening_service import (
    VALID_COMPANY_FIELDS,
    VALID_METRIC_FIELDS,
    _build_company_conditions,
    _build_metric_conditions,
)


class TestBuildMetricConditions:
    def test_valid_field_gt(self):
        filters = [ScreenFilter(field="pe_ratio", op="gt", value=20.0)]
        conditions = _build_metric_conditions(filters, "m")
        assert len(conditions) == 1

    def test_valid_field_lt(self):
        filters = [ScreenFilter(field="roe", op="lt", value=0.5)]
        conditions = _build_metric_conditions(filters, "m")
        assert len(conditions) == 1

    def test_valid_field_between(self):
        filters = [ScreenFilter(field="pe_ratio", op="between", value=10.0, value_high=25.0)]
        conditions = _build_metric_conditions(filters, "m")
        assert len(conditions) == 2  # >= and <=

    def test_invalid_field_skipped(self):
        filters = [ScreenFilter(field="nonexistent", op="gt", value=10.0)]
        conditions = _build_metric_conditions(filters, "m")
        assert len(conditions) == 0

    def test_multiple_filters(self):
        filters = [
            ScreenFilter(field="pe_ratio", op="lt", value=20.0),
            ScreenFilter(field="roe", op="gt", value=0.15),
            ScreenFilter(field="debt_to_equity", op="lt", value=1.0),
        ]
        conditions = _build_metric_conditions(filters, "m")
        assert len(conditions) == 3

    def test_empty_filters(self):
        conditions = _build_metric_conditions([], "m")
        assert len(conditions) == 0

    def test_eq_operator(self):
        filters = [ScreenFilter(field="pe_ratio", op="eq", value=15.0)]
        conditions = _build_metric_conditions(filters, "m")
        assert len(conditions) == 1

    def test_gte_lte_operators(self):
        filters = [
            ScreenFilter(field="pe_ratio", op="gte", value=10.0),
            ScreenFilter(field="pe_ratio", op="lte", value=20.0),
        ]
        conditions = _build_metric_conditions(filters, "m")
        assert len(conditions) == 2


class TestBuildCompanyConditions:
    def test_sector_eq(self):
        filters = [ScreenFilter(field="sector", op="eq", value="Technology")]
        conditions = _build_company_conditions(filters)
        assert len(conditions) == 1

    def test_sector_in(self):
        filters = [
            ScreenFilter(
                field="sector",
                op="in",
                values=["Technology", "Healthcare"],
            )
        ]
        conditions = _build_company_conditions(filters)
        assert len(conditions) == 1

    def test_invalid_field_skipped(self):
        filters = [ScreenFilter(field="nonexistent", op="eq", value="foo")]
        conditions = _build_company_conditions(filters)
        assert len(conditions) == 0

    def test_empty_filters(self):
        conditions = _build_company_conditions([])
        assert len(conditions) == 0


class TestValidFields:
    def test_metric_fields_contain_common_metrics(self):
        assert "pe_ratio" in VALID_METRIC_FIELDS
        assert "roe" in VALID_METRIC_FIELDS
        assert "market_cap" in VALID_METRIC_FIELDS
        assert "dividend_yield" in VALID_METRIC_FIELDS

    def test_company_fields_contain_common_attrs(self):
        assert "sector" in VALID_COMPANY_FIELDS
        assert "industry" in VALID_COMPANY_FIELDS
        assert "country" in VALID_COMPANY_FIELDS
