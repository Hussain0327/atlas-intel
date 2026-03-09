"""Unit tests for valuation computation (pure functions, no DB)."""

from atlas_intel.services.valuation_service import (
    DCF_PROJECTION_YEARS,
    EQUITY_RISK_PREMIUM,
    _compute_dcf,
)


class TestComputeDCF:
    def test_basic_dcf(self):
        """Base case: positive FCF, reasonable inputs."""
        result = _compute_dcf(
            fcf_history=[100e6, 90e6, 80e6, 70e6, 60e6],
            shares=1e9,
            beta=1.0,
            risk_free_rate=0.04,
        )
        assert result is not None
        assert result.intrinsic_value_per_share > 0
        assert len(result.projected_fcfs) == DCF_PROJECTION_YEARS
        assert result.terminal_value > 0

    def test_single_fcf_point(self):
        """Works with single FCF data point (uses default growth)."""
        result = _compute_dcf(
            fcf_history=[100e6],
            shares=1e9,
            beta=1.0,
            risk_free_rate=0.04,
        )
        assert result is not None
        assert result.intrinsic_value_per_share > 0

    def test_empty_fcf_returns_none(self):
        result = _compute_dcf(
            fcf_history=[],
            shares=1e9,
            beta=1.0,
            risk_free_rate=0.04,
        )
        assert result is None

    def test_negative_fcf_returns_none(self):
        result = _compute_dcf(
            fcf_history=[-100e6, -90e6],
            shares=1e9,
            beta=1.0,
            risk_free_rate=0.04,
        )
        assert result is None

    def test_zero_shares_returns_none(self):
        result = _compute_dcf(
            fcf_history=[100e6],
            shares=0,
            beta=1.0,
            risk_free_rate=0.04,
        )
        assert result is None

    def test_growth_adjustment_bear(self):
        """Bear scenario: lower growth should produce lower valuation."""
        base = _compute_dcf(
            fcf_history=[100e6, 90e6, 80e6],
            shares=1e9,
            beta=1.0,
            risk_free_rate=0.04,
        )
        bear = _compute_dcf(
            fcf_history=[100e6, 90e6, 80e6],
            shares=1e9,
            beta=1.0,
            risk_free_rate=0.04,
            growth_adj=-0.02,
            discount_adj=0.02,
        )
        assert base is not None and bear is not None
        assert bear.intrinsic_value_per_share < base.intrinsic_value_per_share

    def test_growth_adjustment_bull(self):
        """Bull scenario: higher growth should produce higher valuation."""
        base = _compute_dcf(
            fcf_history=[100e6, 90e6, 80e6],
            shares=1e9,
            beta=1.0,
            risk_free_rate=0.04,
        )
        bull = _compute_dcf(
            fcf_history=[100e6, 90e6, 80e6],
            shares=1e9,
            beta=1.0,
            risk_free_rate=0.04,
            growth_adj=0.02,
            discount_adj=-0.02,
        )
        assert base is not None and bull is not None
        assert bull.intrinsic_value_per_share > base.intrinsic_value_per_share

    def test_high_beta_lowers_value(self):
        """Higher beta -> higher WACC -> lower intrinsic value."""
        low_beta = _compute_dcf(
            fcf_history=[100e6, 90e6, 80e6],
            shares=1e9,
            beta=0.8,
            risk_free_rate=0.04,
        )
        high_beta = _compute_dcf(
            fcf_history=[100e6, 90e6, 80e6],
            shares=1e9,
            beta=1.5,
            risk_free_rate=0.04,
        )
        assert low_beta is not None and high_beta is not None
        assert high_beta.intrinsic_value_per_share < low_beta.intrinsic_value_per_share

    def test_growth_rate_clamped(self):
        """Growth rate should be clamped to [-10%, 30%]."""
        # Extreme growth history (100x increase)
        result = _compute_dcf(
            fcf_history=[1e9, 1e7],  # 100x in 1 year
            shares=1e9,
            beta=1.0,
            risk_free_rate=0.04,
        )
        assert result is not None
        assert result.growth_rate <= 0.30

    def test_wacc_has_floor(self):
        """WACC should not go below 4% even with low risk-free and beta."""
        result = _compute_dcf(
            fcf_history=[100e6, 90e6],
            shares=1e9,
            beta=0.0,
            risk_free_rate=0.01,
        )
        assert result is not None
        assert result.discount_rate >= 0.04

    def test_projected_fcfs_count(self):
        result = _compute_dcf(
            fcf_history=[100e6],
            shares=1e9,
            beta=1.0,
            risk_free_rate=0.04,
        )
        assert result is not None
        assert len(result.projected_fcfs) == DCF_PROJECTION_YEARS

    def test_projected_fcfs_grow(self):
        """Each projected FCF should be greater than the last (positive growth)."""
        result = _compute_dcf(
            fcf_history=[100e6, 80e6, 60e6],
            shares=1e9,
            beta=1.0,
            risk_free_rate=0.04,
        )
        assert result is not None
        assert result.growth_rate > 0
        for i in range(1, len(result.projected_fcfs)):
            assert result.projected_fcfs[i] > result.projected_fcfs[i - 1]

    def test_terminal_value_positive(self):
        result = _compute_dcf(
            fcf_history=[100e6, 90e6, 80e6],
            shares=1e9,
            beta=1.0,
            risk_free_rate=0.04,
        )
        assert result is not None
        assert result.terminal_value > 0

    def test_label_initially_empty(self):
        """Label is set by caller, not by _compute_dcf."""
        result = _compute_dcf(
            fcf_history=[100e6],
            shares=1e9,
            beta=1.0,
            risk_free_rate=0.04,
        )
        assert result is not None
        assert result.label == ""

    def test_upside_not_set(self):
        """Upside is not computed by _compute_dcf (no current price)."""
        result = _compute_dcf(
            fcf_history=[100e6],
            shares=1e9,
            beta=1.0,
            risk_free_rate=0.04,
        )
        assert result is not None
        assert result.upside_pct is None

    def test_wacc_formula(self):
        """WACC = risk_free + beta * ERP."""
        result = _compute_dcf(
            fcf_history=[100e6],
            shares=1e9,
            beta=1.2,
            risk_free_rate=0.04,
        )
        assert result is not None
        expected_wacc = 0.04 + 1.2 * EQUITY_RISK_PREMIUM
        assert abs(result.discount_rate - expected_wacc) < 0.001

    def test_mixed_positive_negative_fcf(self):
        """FCF history with some negative years should still work."""
        result = _compute_dcf(
            fcf_history=[100e6, -50e6, 80e6, 60e6],
            shares=1e9,
            beta=1.0,
            risk_free_rate=0.04,
        )
        # Latest FCF is positive so it should compute
        assert result is not None
        assert result.intrinsic_value_per_share > 0

    def test_declining_fcf_negative_growth(self):
        """Declining FCF produces negative growth (but clamped >= -10%)."""
        result = _compute_dcf(
            fcf_history=[50e6, 80e6, 100e6],  # Most recent is smallest
            shares=1e9,
            beta=1.0,
            risk_free_rate=0.04,
        )
        assert result is not None
        assert result.growth_rate < 0
        assert result.growth_rate >= -0.10

    def test_very_high_discount_adj(self):
        """Extreme discount adjustment still produces valid result."""
        result = _compute_dcf(
            fcf_history=[100e6, 90e6],
            shares=1e9,
            beta=1.0,
            risk_free_rate=0.04,
            discount_adj=0.10,
        )
        assert result is not None
        assert result.discount_rate > 0.04

    def test_two_point_history(self):
        result = _compute_dcf(
            fcf_history=[120e6, 100e6],
            shares=1e6,
            beta=1.0,
            risk_free_rate=0.04,
        )
        assert result is not None
        assert result.intrinsic_value_per_share > 0

    def test_equal_fcf_history(self):
        """All same FCF -> 0% growth, should still work."""
        result = _compute_dcf(
            fcf_history=[100e6, 100e6, 100e6],
            shares=1e9,
            beta=1.0,
            risk_free_rate=0.04,
        )
        assert result is not None
        # With 0 growth + default adjustments, growth_rate is 0 or clamped
        assert result.growth_rate >= -0.10

    def test_very_small_shares(self):
        """Small share count -> high per-share value."""
        result = _compute_dcf(
            fcf_history=[100e6],
            shares=100,
            beta=1.0,
            risk_free_rate=0.04,
        )
        assert result is not None
        assert result.intrinsic_value_per_share > 1e6

    def test_scenarios_order(self):
        """Bear < base < bull in intrinsic value."""
        bear = _compute_dcf(
            fcf_history=[100e6, 90e6, 80e6],
            shares=1e9,
            beta=1.0,
            risk_free_rate=0.04,
            growth_adj=-0.02,
            discount_adj=0.02,
        )
        base = _compute_dcf(
            fcf_history=[100e6, 90e6, 80e6],
            shares=1e9,
            beta=1.0,
            risk_free_rate=0.04,
        )
        bull = _compute_dcf(
            fcf_history=[100e6, 90e6, 80e6],
            shares=1e9,
            beta=1.0,
            risk_free_rate=0.04,
            growth_adj=0.02,
            discount_adj=-0.02,
        )
        assert bear is not None and base is not None and bull is not None
        assert bear.intrinsic_value_per_share < base.intrinsic_value_per_share
        assert base.intrinsic_value_per_share < bull.intrinsic_value_per_share
