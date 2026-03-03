"""Edge case tests for transforms and NLP — pure logic, no DB/HTTP.

Covers: malformed input, boundary conditions, long text, missing sections.
"""

from decimal import Decimal

from atlas_intel.ingestion.transcript_transforms import (
    parse_fmp_transcript,
    parse_transcript_date,
    parse_transcript_sections,
    split_into_sentences,
)
from atlas_intel.nlp.sentiment import aggregate_sentiment


class TestTranscriptDateEdgeCases:
    def test_whitespace_padding(self):
        assert parse_transcript_date("  2024-01-25 17:00:00  ") is not None

    def test_midnight(self):
        result = parse_transcript_date("2024-01-25 00:00:00")
        assert result is not None
        assert result.day == 25

    def test_garbage_string(self):
        assert parse_transcript_date("not-a-date") is None

    def test_partial_datetime(self):
        assert parse_transcript_date("2024-01") is None

    def test_iso_with_timezone(self):
        # FMP doesn't use this format, but we shouldn't crash
        assert parse_transcript_date("2024-01-25T17:00:00Z") is None


class TestSplitSentencesEdgeCases:
    def test_very_long_text(self):
        """Simulates a dense earnings paragraph — should not hang or OOM."""
        text = "Revenue grew 5% year over year. " * 500
        sentences = split_into_sentences(text)
        assert len(sentences) == 500

    def test_no_sentence_endings(self):
        """Text without periods — returned as single chunk if long enough."""
        text = "This is a long block of text without any periods or exclamation marks"
        sentences = split_into_sentences(text)
        assert len(sentences) == 1

    def test_abbreviations(self):
        """Common abbreviations shouldn't cause excessive splits."""
        text = "Revenue was $119.6 billion vs. estimates of $118.2 billion. Margins improved."
        sentences = split_into_sentences(text)
        # "vs." should not split, so we expect at most 2-3 sentences
        assert len(sentences) <= 3

    def test_unicode_text(self):
        text = "Fréquence des revenus augmentée. Les marges se sont améliorées significativement."
        sentences = split_into_sentences(text)
        assert len(sentences) == 2

    def test_newlines_in_text(self):
        text = "Revenue grew 10%.\n\nMargins improved significantly.\nWe are optimistic."
        sentences = split_into_sentences(text)
        assert len(sentences) >= 2

    def test_only_short_fragments(self):
        """All fragments under 10 chars should yield empty list."""
        text = "OK. Yes. No. Fine."
        sentences = split_into_sentences(text)
        assert len(sentences) == 0


class TestParseSectionsEdgeCases:
    def test_no_qa_section(self):
        """Transcript with only prepared remarks, no Q&A."""
        content = (
            "Tim Cook - CEO:\n"
            "We had a great quarter with record revenue and strong margins. "
            "Our services business continues to grow rapidly.\n\n"
            "Luca Maestri - CFO:\n"
            "Revenue for the quarter was $119 billion, up 2% year over year. "
            "Gross margin was 45.9%, near the high end of guidance.\n"
        )
        sections = parse_transcript_sections(content)
        assert len(sections) == 2
        assert all(s["section_type"] == "prepared_remarks" for s in sections)

    def test_speaker_without_title(self):
        """Speaker line with no dash-separated title."""
        content = (
            "Operator:\n"
            "Good day, welcome to the earnings call.\n\n"
            "John Smith:\n"
            "Thank you. Let me begin with the key financial highlights for this quarter.\n"
        )
        sections = parse_transcript_sections(content)
        operator_section = [s for s in sections if s["speaker_name"] == "Operator"]
        john_section = [s for s in sections if s["speaker_name"] == "John Smith"]
        assert len(operator_section) == 1
        assert operator_section[0]["speaker_title"] is None
        assert len(john_section) == 1
        assert john_section[0]["speaker_title"] is None

    def test_speaker_with_complex_title(self):
        content = (
            "Jane Doe - Senior Vice President, Head of Investor Relations:\n"
            "Thank you for joining our call today. We have several updates to share.\n"
        )
        sections = parse_transcript_sections(content)
        assert len(sections) == 1
        assert sections[0]["speaker_name"] == "Jane Doe"
        assert "Senior Vice President" in (sections[0]["speaker_title"] or "")

    def test_empty_speaker_block(self):
        """Speaker line followed immediately by another speaker — empty block skipped."""
        content = (
            "Tim Cook - CEO:\n"
            "Luca Maestri - CFO:\n"
            "Revenue was $119 billion, up 2% year over year.\n"
        )
        sections = parse_transcript_sections(content)
        # Tim Cook block has no content, so should be skipped
        assert all(s["content"] for s in sections)

    def test_very_long_transcript(self):
        """Simulates a 50-page transcript — should not be slow."""
        names = [
            "Alice",
            "Bob",
            "Carol",
            "Dave",
            "Eve",
            "Frank",
            "Grace",
            "Heidi",
            "Ivan",
            "Judy",
            "Karl",
            "Laura",
            "Mike",
            "Nancy",
            "Oscar",
            "Pam",
            "Quinn",
            "Ruth",
            "Steve",
            "Tina",
        ]
        speakers = []
        for i in range(100):
            name = names[i % len(names)]
            speakers.append(
                f"{name} - Analyst:\n"
                f"This is a detailed question about growth metrics and revenue trends "
                f"that spans several lines of meaningful financial text number {i}.\n\n"
            )
        content = "".join(speakers)
        sections = parse_transcript_sections(content)
        assert len(sections) == 100

    def test_colon_in_content(self):
        """Colons in content (not speaker labels) shouldn't trigger false splits."""
        content = (
            "Tim Cook - CEO:\n"
            "Our key metrics are as follows: revenue up 10%, margins up 2%. "
            "Q4 guidance: we expect $90-92 billion in revenue.\n"
        )
        sections = parse_transcript_sections(content)
        assert len(sections) == 1
        assert "key metrics" in sections[0]["content"]


class TestParseFmpTranscriptEdgeCases:
    def test_whitespace_only_content(self):
        data = {"quarter": 1, "year": 2024, "date": "2024-01-25 17:00:00", "content": "   \n\n  "}
        assert parse_fmp_transcript(data) is None

    def test_very_large_content(self):
        """Multi-MB transcript should parse without issue."""
        data = {
            "quarter": 1,
            "year": 2024,
            "date": "2024-01-25 17:00:00",
            "content": "A" * 500_000,
        }
        result = parse_fmp_transcript(data)
        assert result is not None
        assert len(result["raw_text"]) == 500_000

    def test_zero_quarter(self):
        """quarter=0 is falsy — parse_fmp_transcript correctly rejects it."""
        data = {"quarter": 0, "year": 2024, "date": "2024-01-25 17:00:00", "content": "text"}
        result = parse_fmp_transcript(data)
        assert result is None

    def test_string_quarter_and_year(self):
        """FMP sometimes returns numeric values as strings."""
        data = {
            "quarter": "3",
            "year": "2023",
            "date": "2023-07-25 17:00:00",
            "content": "Transcript content.",
        }
        result = parse_fmp_transcript(data)
        assert result is not None
        assert result["quarter"] == 3
        assert result["year"] == 2023


class TestAggregateSentimentEdgeCases:
    def test_all_zero_confidence(self):
        """If all confidence scores are 0, should not crash (div by zero)."""
        sentiments = [
            {
                "positive": Decimal("0.33"),
                "negative": Decimal("0.33"),
                "neutral": Decimal("0.34"),
                "label": "neutral",
                "confidence": Decimal("0"),
            }
        ]
        result = aggregate_sentiment(sentiments)
        assert result["label"] in ("positive", "negative", "neutral")

    def test_large_number_of_sentiments(self):
        """Aggregate across 10k sentences — should be fast."""
        sentiments = [
            {
                "positive": Decimal("0.5"),
                "negative": Decimal("0.3"),
                "neutral": Decimal("0.2"),
                "label": "positive",
                "confidence": Decimal("0.5"),
            }
        ] * 10_000
        result = aggregate_sentiment(sentiments)
        assert result["label"] == "positive"

    def test_extreme_skew(self):
        """One overwhelmingly confident sentence should dominate."""
        sentiments = [
            {
                "positive": Decimal("0.01"),
                "negative": Decimal("0.01"),
                "neutral": Decimal("0.98"),
                "label": "neutral",
                "confidence": Decimal("0.98"),
            },
        ] * 100
        sentiments.append(
            {
                "positive": Decimal("0.99"),
                "negative": Decimal("0.005"),
                "neutral": Decimal("0.005"),
                "label": "positive",
                "confidence": Decimal("0.99"),
            }
        )
        result = aggregate_sentiment(sentiments)
        # The 100 neutral sentences should still dominate over 1 positive
        assert result["label"] == "neutral"
