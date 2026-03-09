"""Unit tests for anomaly detection (pure functions, no DB)."""

from datetime import date

from atlas_intel.services.anomaly_service import (
    _detect_anomalies_in_series,
    _percentile_rank,
    _zscore,
)


class TestZscore:
    def test_basic_zscore(self):
        values = [10, 10, 10, 10, 10]
        # All same values -> std=0 -> None
        assert _zscore(values, 10) is None

    def test_zscore_with_variance(self):
        values = [10, 12, 11, 9, 10, 11, 10]
        z = _zscore(values, 20)
        assert z is not None
        assert z > 2  # 20 is far above mean ~10.4

    def test_zscore_negative(self):
        values = [10, 12, 11, 9, 10, 11, 10]
        z = _zscore(values, 0)
        assert z is not None
        assert z < -2  # 0 is far below mean

    def test_zscore_near_mean(self):
        values = [10, 12, 11, 9, 10, 11, 10]
        z = _zscore(values, 10.5)
        assert z is not None
        assert abs(z) < 1  # Close to mean

    def test_zscore_too_few_points(self):
        assert _zscore([1, 2, 3, 4], 5) is None  # Need >= 5

    def test_zscore_exactly_five_points(self):
        values = [10, 20, 30, 40, 50]
        z = _zscore(values, 100)
        assert z is not None
        assert z > 0

    def test_zscore_empty(self):
        assert _zscore([], 5) is None

    def test_zscore_all_zeros(self):
        assert _zscore([0, 0, 0, 0, 0], 0) is None  # std = 0


class TestPercentileRank:
    def test_basic_percentile(self):
        values = [1, 2, 3, 4, 5]
        # 5 is highest -> percentile near 90-100
        rank = _percentile_rank(values, 5)
        assert rank > 80

    def test_lowest_value(self):
        values = [1, 2, 3, 4, 5]
        rank = _percentile_rank(values, 1)
        assert rank < 20

    def test_median_value(self):
        values = [1, 2, 3, 4, 5]
        rank = _percentile_rank(values, 3)
        assert 40 <= rank <= 60

    def test_empty_values(self):
        assert _percentile_rank([], 5) == 50.0

    def test_all_same_values(self):
        values = [5, 5, 5, 5, 5]
        rank = _percentile_rank(values, 5)
        assert rank == 50.0  # 0.5 * 5 / 5 * 100

    def test_value_above_all(self):
        values = [1, 2, 3, 4, 5]
        rank = _percentile_rank(values, 100)
        assert rank == 100.0

    def test_value_below_all(self):
        values = [1, 2, 3, 4, 5]
        rank = _percentile_rank(values, -100)
        assert rank == 0.0


class TestDetectAnomaliesInSeries:
    def test_finds_spike(self):
        dt = [date(2024, 1, i) for i in range(1, 11)]
        values = [10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 50.0]
        anomalies = _detect_anomalies_in_series(dt, values, threshold=2.0)
        assert len(anomalies) > 0
        assert anomalies[-1].value == 50.0
        assert "spike" in anomalies[-1].description

    def test_finds_drop(self):
        dt = [date(2024, 1, i) for i in range(1, 11)]
        values = [10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, -30.0]
        anomalies = _detect_anomalies_in_series(dt, values, threshold=2.0)
        assert len(anomalies) > 0
        assert any("drop" in a.description for a in anomalies)

    def test_no_anomalies_uniform(self):
        dt = [date(2024, 1, i) for i in range(1, 11)]
        values = [10.0] * 10
        anomalies = _detect_anomalies_in_series(dt, values, threshold=2.0)
        assert len(anomalies) == 0  # Zero std -> no z-scores

    def test_too_few_points(self):
        dt = [date(2024, 1, i) for i in range(1, 5)]
        values = [10.0, 20.0, 10.0, 100.0]
        anomalies = _detect_anomalies_in_series(dt, values, threshold=2.0)
        assert len(anomalies) == 0  # Need >= 5 points

    def test_threshold_higher_means_fewer(self):
        dt = [date(2024, 1, i) for i in range(1, 11)]
        values = [10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 15.0, 10.0, 30.0]
        low_threshold = _detect_anomalies_in_series(dt, values, threshold=1.5)
        high_threshold = _detect_anomalies_in_series(dt, values, threshold=3.0)
        assert len(low_threshold) >= len(high_threshold)

    def test_description_prefix(self):
        dt = [date(2024, 1, i) for i in range(1, 11)]
        values = [10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 50.0]
        anomalies = _detect_anomalies_in_series(
            dt, values, threshold=2.0, description_prefix="Volume "
        )
        assert len(anomalies) > 0
        assert anomalies[-1].description.startswith("Volume ")

    def test_zscore_in_result(self):
        dt = [date(2024, 1, i) for i in range(1, 11)]
        values = [10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 50.0]
        anomalies = _detect_anomalies_in_series(dt, values, threshold=2.0)
        assert len(anomalies) > 0
        assert anomalies[-1].zscore >= 2.0
