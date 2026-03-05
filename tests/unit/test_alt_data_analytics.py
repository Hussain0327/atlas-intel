"""Unit tests for alternative data analytics computations."""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from atlas_intel.services.insider_service import get_insider_sentiment


def _make_trade(
    tx_type: str,
    name: str = "Test Person",
    securities: float | None = 1000,
    price: float | None = 100.0,
    filing_date: date | None = None,
) -> MagicMock:
    trade = MagicMock()
    trade.transaction_type = tx_type
    trade.reporting_name = name
    trade.securities_transacted = Decimal(str(securities)) if securities else None
    trade.price = Decimal(str(price)) if price else None
    trade.filing_date = filing_date or date.today()
    return trade


class TestInsiderSentiment:
    @pytest.fixture
    def mock_session(self):
        session = AsyncMock()
        return session

    async def test_bullish_sentiment(self, mock_session):
        """More buys than sells = bullish."""
        trades = [
            _make_trade("P", "Buyer 1", 1000, 100),
            _make_trade("P", "Buyer 2", 2000, 50),
            _make_trade("P", "Buyer 3", 500, 200),
            _make_trade("S", "Seller 1", 100, 150),
        ]
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = trades
        mock_session.execute = AsyncMock(return_value=result_mock)

        result = await get_insider_sentiment(mock_session, 1, "AAPL", days=90)
        assert result["buy_count"] == 3
        assert result["sell_count"] == 1
        assert result["sentiment"] == "bullish"
        assert result["net_ratio"] == 0.75

    async def test_bearish_sentiment(self, mock_session):
        """More sells than buys = bearish."""
        trades = [
            _make_trade("S", "Seller 1", 5000, 200),
            _make_trade("S", "Seller 2", 3000, 150),
            _make_trade("S", "Seller 3", 2000, 180),
            _make_trade("P", "Buyer 1", 100, 100),
        ]
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = trades
        mock_session.execute = AsyncMock(return_value=result_mock)

        result = await get_insider_sentiment(mock_session, 1, "AAPL", days=90)
        assert result["sentiment"] == "bearish"
        assert result["net_ratio"] == 0.25

    async def test_neutral_sentiment(self, mock_session):
        """Equal buys and sells = neutral."""
        trades = [
            _make_trade("P", "Buyer 1", 1000, 100),
            _make_trade("S", "Seller 1", 1000, 100),
        ]
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = trades
        mock_session.execute = AsyncMock(return_value=result_mock)

        result = await get_insider_sentiment(mock_session, 1, "AAPL", days=90)
        assert result["sentiment"] == "neutral"
        assert result["net_ratio"] == 0.5

    async def test_empty_trades(self, mock_session):
        """No trades = neutral."""
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=result_mock)

        result = await get_insider_sentiment(mock_session, 1, "AAPL", days=90)
        assert result["sentiment"] == "neutral"
        assert result["buy_count"] == 0
        assert result["sell_count"] == 0
        assert result["net_ratio"] is None

    async def test_top_buyers_sellers(self, mock_session):
        """Top buyers/sellers computed correctly."""
        trades = [
            _make_trade("P", "Big Buyer", 10000, 200),
            _make_trade("P", "Small Buyer", 100, 50),
            _make_trade("S", "Big Seller", 5000, 300),
        ]
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = trades
        mock_session.execute = AsyncMock(return_value=result_mock)

        result = await get_insider_sentiment(mock_session, 1, "AAPL", days=90)
        assert len(result["top_buyers"]) == 2
        assert result["top_buyers"][0]["name"] == "Big Buyer"
        assert result["top_buyers"][0]["value"] == 2000000.0
        assert len(result["top_sellers"]) == 1

    async def test_buy_sell_values(self, mock_session):
        """Total buy/sell values computed."""
        trades = [
            _make_trade("P", "Buyer", 1000, 100),  # $100,000
            _make_trade("S", "Seller", 500, 200),  # $100,000
        ]
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = trades
        mock_session.execute = AsyncMock(return_value=result_mock)

        result = await get_insider_sentiment(mock_session, 1, "AAPL", days=90)
        assert result["total_buy_value"] == 100000.0
        assert result["total_sell_value"] == 100000.0

    async def test_trades_with_null_values(self, mock_session):
        """Trades with null price/shares don't crash."""
        trades = [
            _make_trade("P", "Buyer", None, None),
            _make_trade("S", "Seller", 1000, None),
        ]
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = trades
        mock_session.execute = AsyncMock(return_value=result_mock)

        result = await get_insider_sentiment(mock_session, 1, "AAPL", days=90)
        assert result["buy_count"] == 1
        assert result["sell_count"] == 1
        assert result["total_buy_value"] is None
        assert result["total_sell_value"] is None

    async def test_custom_days_parameter(self, mock_session):
        """Days parameter is passed through."""
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=result_mock)

        result = await get_insider_sentiment(mock_session, 1, "AAPL", days=30)
        assert result["days"] == 30
