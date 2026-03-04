"""Unit tests for price analytics helper functions."""

from decimal import Decimal

from atlas_intel.services.price_service import _annualized_volatility, _pct_return


class TestPctReturn:
    def test_positive_return(self):
        result = _pct_return(Decimal("100"), Decimal("110"))
        assert result is not None
        assert abs(result - 10.0) < 0.001

    def test_negative_return(self):
        result = _pct_return(Decimal("100"), Decimal("90"))
        assert result is not None
        assert abs(result - (-10.0)) < 0.001

    def test_zero_return(self):
        result = _pct_return(Decimal("100"), Decimal("100"))
        assert result == 0.0

    def test_zero_old_price(self):
        assert _pct_return(Decimal("0"), Decimal("100")) is None


class TestAnnualizedVolatility:
    def test_constant_prices(self):
        closes = [Decimal("100")] * 30
        result = _annualized_volatility(closes)
        assert result is not None
        assert result == 0.0

    def test_increasing_prices(self):
        # Create steadily increasing prices
        closes = [Decimal(str(100 + i * 0.5)) for i in range(30)]
        result = _annualized_volatility(closes)
        assert result is not None
        assert result > 0

    def test_insufficient_data(self):
        assert _annualized_volatility([]) is None
        assert _annualized_volatility([Decimal("100")]) is None

    def test_two_prices(self):
        result = _annualized_volatility([Decimal("100"), Decimal("102")])
        # With only 1 return, variance is 0 (n-1 denominator = 0 for single sample)
        # Actually with 2 prices we get 1 return, and variance of single value...
        # std dev with ddof=1 for single value => 0/0 actually let's check:
        # variance = sum((r - mean)^2) / (1 - 1) = 0/0 which is nan
        # Actually we get n=1 return, variance = sum of 0 squared differences / 0
        # The function checks len(log_returns) < 2 => None
        assert result is None

    def test_three_prices_works(self):
        closes = [Decimal("100"), Decimal("102"), Decimal("101")]
        result = _annualized_volatility(closes)
        assert result is not None
        assert result > 0
