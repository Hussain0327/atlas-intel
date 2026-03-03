"""Unit tests for NLP aggregate functions (pure logic, no model loading)."""

from decimal import Decimal

from atlas_intel.nlp.sentiment import aggregate_sentiment


class TestAggregateSentiment:
    def test_single_sentiment(self):
        sentiments = [
            {
                "positive": Decimal("0.8"),
                "negative": Decimal("0.1"),
                "neutral": Decimal("0.1"),
                "label": "positive",
                "confidence": Decimal("0.8"),
            }
        ]
        result = aggregate_sentiment(sentiments)
        assert result["label"] == "positive"
        assert result["positive"] == Decimal("0.8")
        assert result["negative"] == Decimal("0.1")

    def test_multiple_sentiments_weighted(self):
        sentiments = [
            {
                "positive": Decimal("0.9"),
                "negative": Decimal("0.05"),
                "neutral": Decimal("0.05"),
                "label": "positive",
                "confidence": Decimal("0.9"),
            },
            {
                "positive": Decimal("0.1"),
                "negative": Decimal("0.8"),
                "neutral": Decimal("0.1"),
                "label": "negative",
                "confidence": Decimal("0.8"),
            },
        ]
        result = aggregate_sentiment(sentiments)
        # Weighted average should be computed
        assert isinstance(result["positive"], Decimal)
        assert isinstance(result["negative"], Decimal)
        assert isinstance(result["neutral"], Decimal)
        assert result["label"] in ("positive", "negative", "neutral")

    def test_empty_sentiments(self):
        result = aggregate_sentiment([])
        assert result["label"] == "neutral"
        assert result["positive"] == Decimal("0")
        assert result["negative"] == Decimal("0")
        assert result["neutral"] == Decimal("0")

    def test_all_neutral(self):
        sentiments = [
            {
                "positive": Decimal("0.1"),
                "negative": Decimal("0.1"),
                "neutral": Decimal("0.8"),
                "label": "neutral",
                "confidence": Decimal("0.8"),
            },
            {
                "positive": Decimal("0.15"),
                "negative": Decimal("0.05"),
                "neutral": Decimal("0.8"),
                "label": "neutral",
                "confidence": Decimal("0.8"),
            },
        ]
        result = aggregate_sentiment(sentiments)
        assert result["label"] == "neutral"
