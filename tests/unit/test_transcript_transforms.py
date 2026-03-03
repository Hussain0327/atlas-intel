"""Unit tests for transcript parsing transforms (pure functions, no DB/HTTP/ML)."""

from datetime import date

from atlas_intel.ingestion.transcript_transforms import (
    parse_fmp_transcript,
    parse_transcript_date,
    parse_transcript_sections,
    split_into_sentences,
)


class TestParseTranscriptDate:
    def test_standard_fmp_format(self):
        assert parse_transcript_date("2024-01-25 17:00:00") == date(2024, 1, 25)

    def test_date_only(self):
        assert parse_transcript_date("2024-01-25") == date(2024, 1, 25)

    def test_none(self):
        assert parse_transcript_date(None) is None

    def test_empty_string(self):
        assert parse_transcript_date("") is None

    def test_invalid_format(self):
        assert parse_transcript_date("Jan 25, 2024") is None


class TestSplitIntoSentences:
    def test_basic_split(self):
        text = "Revenue grew 10%. Margins improved significantly. We are optimistic."
        sentences = split_into_sentences(text)
        assert len(sentences) == 3
        assert sentences[0] == "Revenue grew 10%."

    def test_filters_short_fragments(self):
        text = "Revenue grew 10%. OK. Margins improved significantly."
        sentences = split_into_sentences(text)
        assert len(sentences) == 2  # "OK." is < 10 chars

    def test_empty_text(self):
        assert split_into_sentences("") == []
        assert split_into_sentences(None) == []


class TestParseTranscriptSections:
    def test_detects_speakers(self):
        content = (
            "Tim Cook - CEO:\n"
            "We had a great quarter with record revenue.\n\n"
            "Luca Maestri - CFO:\n"
            "Revenue was $119 billion, up 2% year over year.\n"
        )
        sections = parse_transcript_sections(content)
        assert len(sections) == 2
        assert sections[0]["speaker_name"] == "Tim Cook"
        assert sections[0]["speaker_title"] == "CEO"
        assert sections[0]["section_type"] == "prepared_remarks"
        assert sections[1]["speaker_name"] == "Luca Maestri"

    def test_no_speakers_single_section(self):
        content = "This is plain text without any speaker labels."
        sections = parse_transcript_sections(content)
        assert len(sections) == 1
        assert sections[0]["section_type"] == "prepared_remarks"
        assert sections[0]["speaker_name"] is None

    def test_empty_content(self):
        assert parse_transcript_sections("") == []
        assert parse_transcript_sections(None) == []

    def test_operator_section(self):
        content = (
            "Operator:\n"
            "Good day and welcome to the earnings call.\n\n"
            "Tim Cook - CEO:\n"
            "Thank you. We had a great quarter.\n"
        )
        sections = parse_transcript_sections(content)
        assert sections[0]["section_type"] == "operator"

    def test_qa_detection(self):
        content = (
            "Tim Cook - CEO:\n"
            "Thank you all for joining.\n\n"
            "Operator:\n"
            "We will now begin the question-and-answer session.\n\n"
            "Erik Woodring - Morgan Stanley:\n"
            "Thanks for taking my question about revenue.\n"
        )
        sections = parse_transcript_sections(content)
        # After Q&A indicator, subsequent sections should be q_and_a
        qa_sections = [s for s in sections if s["section_type"] == "q_and_a"]
        assert len(qa_sections) >= 1


class TestParseFmpTranscript:
    def test_valid_transcript(self):
        data = {
            "quarter": 1,
            "year": 2024,
            "date": "2024-01-25 17:00:00",
            "title": "AAPL Q1 2024 Earnings Call",
            "content": "This is the transcript content with enough text to be valid.",
        }
        result = parse_fmp_transcript(data)
        assert result is not None
        assert result["quarter"] == 1
        assert result["year"] == 2024
        assert result["transcript_date"] == date(2024, 1, 25)
        assert result["title"] == "AAPL Q1 2024 Earnings Call"
        assert "transcript content" in result["raw_text"]

    def test_missing_content(self):
        data = {"quarter": 1, "year": 2024, "date": "2024-01-25 17:00:00", "content": ""}
        assert parse_fmp_transcript(data) is None

    def test_missing_quarter(self):
        data = {"year": 2024, "date": "2024-01-25 17:00:00", "content": "Some content"}
        assert parse_fmp_transcript(data) is None

    def test_missing_date(self):
        data = {"quarter": 1, "year": 2024, "content": "Some content"}
        assert parse_fmp_transcript(data) is None

    def test_default_title(self):
        data = {
            "quarter": 3,
            "year": 2023,
            "date": "2023-07-25 17:00:00",
            "content": "Transcript content here.",
        }
        result = parse_fmp_transcript(data)
        assert result is not None
        assert result["title"] == "Q3 2023 Earnings Call"
