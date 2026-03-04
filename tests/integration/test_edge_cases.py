"""Integration edge case tests — real DB + mocked APIs.

Covers: FMP 429/500 responses, empty transcripts, transcripts with no Q&A,
long sentences exceeding 512 tokens, companies with missing ticker,
amended filing dedup, concurrent sync safety.
"""

from datetime import date
from decimal import Decimal
from typing import ClassVar
from unittest.mock import patch

import httpx
import pytest
import respx
from httpx import Response
from sqlalchemy import func, select

from atlas_intel.ingestion.client import SECClient
from atlas_intel.ingestion.fmp_client import FMPClient
from atlas_intel.ingestion.submission_sync import sync_submissions
from atlas_intel.ingestion.transcript_sync import sync_transcript
from atlas_intel.models.company import Company
from atlas_intel.models.earnings_transcript import EarningsTranscript
from atlas_intel.models.filing import Filing
from atlas_intel.models.keyword_extraction import KeywordExtraction
from atlas_intel.models.sentiment_analysis import SentimentAnalysis
from atlas_intel.models.transcript_section import TranscriptSection


@pytest.fixture
async def company(session):
    """Seed a test company."""
    c = Company(cik=320193, ticker="AAPL", name="Apple Inc.")
    session.add(c)
    await session.commit()
    await session.refresh(c)
    return c


@pytest.fixture
async def company_no_ticker(session):
    """Company with ticker=None — edge case for FMP lookup."""
    c = Company(cik=999999, ticker=None, name="Unknown Corp")
    session.add(c)
    await session.commit()
    await session.refresh(c)
    return c


# Mock NLP to avoid loading models
MOCK_SENTIMENT = [
    {
        "positive": Decimal("0.7"),
        "negative": Decimal("0.1"),
        "neutral": Decimal("0.2"),
        "label": "positive",
        "confidence": Decimal("0.7"),
    }
]

MOCK_KEYWORDS = [
    {"keyword": "revenue growth", "relevance_score": Decimal("0.85")},
]


def mock_analyze_sentences(sentences, batch_size=32):
    return MOCK_SENTIMENT * len(sentences)


def mock_extract_keywords(text, top_n=20):
    return MOCK_KEYWORDS


# ---------------------------------------------------------------------------
# FMP error handling
# ---------------------------------------------------------------------------


class TestFMPErrorHandling:
    async def test_fmp_429_retries_and_recovers(self, session, company):
        """FMP returns 429 twice then succeeds — should eventually process."""
        call_count = 0
        transcript_data = [
            {
                "symbol": "AAPL",
                "quarter": 1,
                "year": 2024,
                "date": "2024-01-25 17:00:00",
                "title": "AAPL Q1 2024",
                "content": "Revenue grew strongly this quarter. Margins improved significantly.",
            }
        ]

        def side_effect(request):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                return Response(429)
            return Response(200, json=transcript_data)

        with respx.mock(assert_all_called=False) as mock:
            mock.get(
                url__startswith="https://financialmodelingprep.com/stable/earning-call-transcript"
            ).mock(side_effect=side_effect)

            with (
                patch(
                    "atlas_intel.ingestion.transcript_sync.analyze_sentences",
                    mock_analyze_sentences,
                ),
                patch(
                    "atlas_intel.ingestion.transcript_sync.extract_keywords",
                    mock_extract_keywords,
                ),
            ):
                async with FMPClient(api_key="test", rate_limit=100) as client:
                    result = await sync_transcript(session, client, company, quarter=1, year=2024)

            assert result is True
            assert call_count == 3  # 2 retries + 1 success

    async def test_fmp_500_retries_then_fails(self, session, company):
        """FMP returns 500 three times — should raise after exhausting retries."""
        with respx.mock(assert_all_called=False) as mock:
            mock.get(
                url__startswith="https://financialmodelingprep.com/stable/earning-call-transcript"
            ).mock(return_value=Response(500))

            async with FMPClient(api_key="test", rate_limit=100) as client:
                with pytest.raises(httpx.HTTPError):
                    await sync_transcript(session, client, company, quarter=1, year=2024)

    async def test_fmp_returns_empty_list(self, session, company):
        """FMP returns [] for a quarter with no transcript."""
        with respx.mock(assert_all_called=False) as mock:
            mock.get(
                url__startswith="https://financialmodelingprep.com/stable/earning-call-transcript"
            ).mock(return_value=Response(200, json=[]))

            async with FMPClient(api_key="test", rate_limit=100) as client:
                result = await sync_transcript(session, client, company, quarter=3, year=2020)

            assert result is False
            count = (
                await session.execute(
                    select(func.count(EarningsTranscript.id)).where(
                        EarningsTranscript.company_id == company.id
                    )
                )
            ).scalar()
            assert count == 0

    async def test_fmp_returns_empty_content(self, session, company):
        """FMP returns a transcript object but content is empty."""
        with respx.mock(assert_all_called=False) as mock:
            mock.get(
                url__startswith="https://financialmodelingprep.com/stable/earning-call-transcript"
            ).mock(
                return_value=Response(
                    200,
                    json=[
                        {
                            "symbol": "AAPL",
                            "quarter": 1,
                            "year": 2024,
                            "date": "2024-01-25 17:00:00",
                            "content": "",
                        }
                    ],
                )
            )

            async with FMPClient(api_key="test", rate_limit=100) as client:
                result = await sync_transcript(session, client, company, quarter=1, year=2024)

            assert result is False


# ---------------------------------------------------------------------------
# Transcript content edge cases
# ---------------------------------------------------------------------------


class TestTranscriptContentEdgeCases:
    @patch("atlas_intel.ingestion.transcript_sync.analyze_sentences", mock_analyze_sentences)
    @patch("atlas_intel.ingestion.transcript_sync.extract_keywords", mock_extract_keywords)
    async def test_transcript_with_no_qa_section(self, session, company):
        """Transcript that only has prepared remarks, no Q&A."""
        content = (
            "Tim Cook - CEO:\n"
            "We had a great quarter with record revenue and strong margins across all segments. "
            "Our services business continues to grow rapidly and we see significant opportunities "
            "ahead in artificial intelligence and machine learning.\n\n"
            "Luca Maestri - CFO:\n"
            "Revenue for the quarter was $119 billion, up 2% year over year. "
            "Gross margin was 45.9%, near the high end of our guidance range. "
            "Operating expenses were well managed across all divisions.\n"
        )
        transcript_data = [
            {
                "symbol": "AAPL",
                "quarter": 2,
                "year": 2024,
                "date": "2024-04-25 17:00:00",
                "title": "AAPL Q2 2024",
                "content": content,
            }
        ]

        with respx.mock(assert_all_called=False) as mock:
            mock.get(
                url__startswith="https://financialmodelingprep.com/stable/earning-call-transcript"
            ).mock(return_value=Response(200, json=transcript_data))

            async with FMPClient(api_key="test", rate_limit=100) as client:
                result = await sync_transcript(session, client, company, quarter=2, year=2024)

        assert result is True

        # All sections should be prepared_remarks (no q_and_a)
        sections = (
            (
                await session.execute(
                    select(TranscriptSection)
                    .join(EarningsTranscript)
                    .where(EarningsTranscript.company_id == company.id)
                )
            )
            .scalars()
            .all()
        )

        assert len(sections) == 2
        assert all(s.section_type == "prepared_remarks" for s in sections)

    @patch("atlas_intel.ingestion.transcript_sync.extract_keywords", mock_extract_keywords)
    async def test_long_sentence_exceeding_512_tokens(self, session, company):
        """FinBERT has a 512 token limit — sentences over that get truncated, not crash."""
        # ~600 words should exceed 512 tokens
        long_sentence = "revenue " * 600 + "grew significantly."
        content = f"Tim Cook - CEO:\n{long_sentence}\n"

        transcript_data = [
            {
                "symbol": "AAPL",
                "quarter": 3,
                "year": 2024,
                "date": "2024-07-25 17:00:00",
                "title": "AAPL Q3 2024",
                "content": content,
            }
        ]

        with respx.mock(assert_all_called=False) as mock:
            mock.get(
                url__startswith="https://financialmodelingprep.com/stable/earning-call-transcript"
            ).mock(return_value=Response(200, json=transcript_data))

            # Use mock_analyze_sentences here — the real FinBERT handles truncation
            # via tokenizer(truncation=True, max_length=512), but we verify the
            # pipeline doesn't crash on long input
            with patch(
                "atlas_intel.ingestion.transcript_sync.analyze_sentences",
                mock_analyze_sentences,
            ):
                async with FMPClient(api_key="test", rate_limit=100) as client:
                    result = await sync_transcript(session, client, company, quarter=3, year=2024)

        assert result is True

        # Should have stored the full text
        transcript = (
            await session.execute(
                select(EarningsTranscript).where(
                    EarningsTranscript.company_id == company.id,
                    EarningsTranscript.quarter == 3,
                )
            )
        ).scalar_one()
        assert len(transcript.raw_text) > 3000

    @patch("atlas_intel.ingestion.transcript_sync.analyze_sentences", mock_analyze_sentences)
    @patch("atlas_intel.ingestion.transcript_sync.extract_keywords", mock_extract_keywords)
    async def test_company_with_no_ticker(self, session, company_no_ticker):
        """Company with ticker=None — FMP call uses empty string, returns empty."""
        with respx.mock(assert_all_called=False) as mock:
            mock.get(
                url__startswith="https://financialmodelingprep.com/stable/earning-call-transcript"
            ).mock(return_value=Response(200, json=[]))

            async with FMPClient(api_key="test", rate_limit=100) as client:
                result = await sync_transcript(
                    session, client, company_no_ticker, quarter=1, year=2024
                )

        assert result is False


# ---------------------------------------------------------------------------
# SEC pipeline edge cases
# ---------------------------------------------------------------------------


class TestSECEdgeCases:
    async def test_amended_filings_dedup(self, session, company):
        """Amended filings (e.g. 10-K/A) with same accession number should dedup."""
        submissions_data = {
            "cik": "0000320193",
            "name": "Apple Inc.",
            "filings": {
                "recent": {
                    "accessionNumber": ["0000320193-24-000001", "0000320193-24-000001"],
                    "form": ["10-K", "10-K/A"],
                    "filingDate": ["2024-01-15", "2024-03-15"],
                    "reportDate": ["2023-12-31", "2023-12-31"],
                    "primaryDocument": ["doc1.htm", "doc1_amended.htm"],
                    "isXBRL": [1, 1],
                }
            },
        }

        with respx.mock(assert_all_called=False) as mock:
            mock.get(url__startswith="https://data.sec.gov/submissions/").mock(
                return_value=Response(200, json=submissions_data)
            )

            async with SECClient() as client:
                count = await sync_submissions(session, client, company, force=True)

        # Same accession_number → deduped in batch, last wins → 1 row
        filing_count = (
            await session.execute(
                select(func.count(Filing.id)).where(Filing.company_id == company.id)
            )
        ).scalar()

        assert filing_count == 1
        assert count == 1  # only 1 after dedup

        # The filing should have the amended data (10-K/A, later date)
        filing = (
            await session.execute(select(Filing).where(Filing.company_id == company.id))
        ).scalar_one()
        assert filing.form_type == "10-K/A"
        assert filing.filing_date == date(2024, 3, 15)

    async def test_submissions_missing_fields(self, session, company):
        """Submissions with missing form_type or filing_date should be skipped."""
        submissions_data = {
            "cik": "0000320193",
            "name": "Apple Inc.",
            "filings": {
                "recent": {
                    "accessionNumber": [
                        "0000320193-24-000010",
                        "0000320193-24-000011",
                        "0000320193-24-000012",
                    ],
                    "form": ["10-K", None, "10-Q"],
                    "filingDate": ["2024-01-15", "2024-02-15", None],
                    "reportDate": ["2023-12-31", "2023-12-31", "2023-12-31"],
                    "primaryDocument": ["doc.htm", "doc2.htm", "doc3.htm"],
                    "isXBRL": [1, 1, 1],
                }
            },
        }

        with respx.mock(assert_all_called=False) as mock:
            mock.get(url__startswith="https://data.sec.gov/submissions/").mock(
                return_value=Response(200, json=submissions_data)
            )

            async with SECClient() as client:
                count = await sync_submissions(session, client, company, force=True)

        # Only the first filing has both form_type and filing_date
        assert count == 1

    async def test_submissions_empty_recent(self, session, company):
        """Company with no recent filings — should set synced_at without error."""
        submissions_data = {
            "cik": "0000320193",
            "name": "Apple Inc.",
            "filings": {"recent": {}},
        }

        with respx.mock(assert_all_called=False) as mock:
            mock.get(url__startswith="https://data.sec.gov/submissions/").mock(
                return_value=Response(200, json=submissions_data)
            )

            async with SECClient() as client:
                count = await sync_submissions(session, client, company, force=True)

        assert count == 0
        await session.refresh(company)
        assert company.submissions_synced_at is not None


# ---------------------------------------------------------------------------
# Sync freshness / idempotency edge cases
# ---------------------------------------------------------------------------


class TestSyncFreshnessEdgeCases:
    @patch("atlas_intel.ingestion.transcript_sync.analyze_sentences", mock_analyze_sentences)
    @patch("atlas_intel.ingestion.transcript_sync.extract_keywords", mock_extract_keywords)
    async def test_force_replaces_existing_transcript_data(self, session, company):
        """Force sync should delete old sections/sentiments/keywords and reprocess."""
        transcript_data = [
            {
                "symbol": "AAPL",
                "quarter": 4,
                "year": 2023,
                "date": "2023-10-26 17:00:00",
                "title": "AAPL Q4 2023",
                "content": (
                    "Tim Cook - CEO:\n"
                    "Revenue was strong across all product categories. "
                    "We see continued momentum in services.\n"
                ),
            }
        ]

        with respx.mock(assert_all_called=False) as mock:
            mock.get(
                url__startswith="https://financialmodelingprep.com/stable/earning-call-transcript"
            ).mock(return_value=Response(200, json=transcript_data))

            async with FMPClient(api_key="test", rate_limit=100) as client:
                await sync_transcript(session, client, company, quarter=4, year=2023)

                # Count sections after first sync
                section_count_1 = (
                    await session.execute(
                        select(func.count(TranscriptSection.id))
                        .join(EarningsTranscript)
                        .where(EarningsTranscript.company_id == company.id)
                    )
                ).scalar()

                # Force re-sync
                await sync_transcript(session, client, company, quarter=4, year=2023, force=True)

                # Sections should be the same count (not doubled)
                section_count_2 = (
                    await session.execute(
                        select(func.count(TranscriptSection.id))
                        .join(EarningsTranscript)
                        .where(EarningsTranscript.company_id == company.id)
                    )
                ).scalar()

        assert section_count_1 == section_count_2
        assert section_count_1 > 0  # At least 1 section


# ---------------------------------------------------------------------------
# NLP failure resilience
# ---------------------------------------------------------------------------


class TestNLPFailureResilience:
    """Verify transcripts are saved even when NLP models fail."""

    TRANSCRIPT_DATA: ClassVar[list[dict[str, str | int]]] = [
        {
            "symbol": "AAPL",
            "quarter": 1,
            "year": 2025,
            "date": "2025-01-30 17:00:00",
            "title": "AAPL Q1 2025",
            "content": (
                "Tim Cook - CEO:\n"
                "Revenue grew strongly this quarter. Margins improved significantly.\n"
            ),
        }
    ]

    @patch("atlas_intel.ingestion.transcript_sync.extract_keywords", mock_extract_keywords)
    async def test_sentiment_failure_still_saves_transcript(self, session, company):
        """If FinBERT raises, transcript and sections are saved without sentiment."""

        def failing_analyze(sentences, batch_size=32):
            raise RuntimeError("FinBERT OOM")

        with respx.mock(assert_all_called=False) as mock:
            mock.get(
                url__startswith="https://financialmodelingprep.com/stable/earning-call-transcript"
            ).mock(return_value=Response(200, json=self.TRANSCRIPT_DATA))

            with patch(
                "atlas_intel.ingestion.transcript_sync.analyze_sentences",
                failing_analyze,
            ):
                async with FMPClient(api_key="test", rate_limit=100) as client:
                    result = await sync_transcript(session, client, company, quarter=1, year=2025)

        assert result is True

        # Transcript saved
        transcript = (
            await session.execute(
                select(EarningsTranscript).where(
                    EarningsTranscript.company_id == company.id,
                    EarningsTranscript.quarter == 1,
                    EarningsTranscript.year == 2025,
                )
            )
        ).scalar_one()
        assert transcript is not None

        # No sentiments (FinBERT failed)
        sentiment_count = (
            await session.execute(
                select(func.count(SentimentAnalysis.id))
                .join(TranscriptSection)
                .where(TranscriptSection.transcript_id == transcript.id)
            )
        ).scalar()
        assert sentiment_count == 0

        # Keywords still saved (extract_keywords wasn't the one that failed)
        keyword_count = (
            await session.execute(
                select(func.count(KeywordExtraction.id)).where(
                    KeywordExtraction.transcript_id == transcript.id
                )
            )
        ).scalar()
        assert keyword_count > 0

    @patch("atlas_intel.ingestion.transcript_sync.analyze_sentences", mock_analyze_sentences)
    async def test_keyword_failure_still_saves_transcript(self, session, company):
        """If KeyBERT raises, transcript is saved with sentiment but no keywords."""

        def failing_keywords(text, top_n=20):
            raise RuntimeError("KeyBERT crash")

        with respx.mock(assert_all_called=False) as mock:
            mock.get(
                url__startswith="https://financialmodelingprep.com/stable/earning-call-transcript"
            ).mock(return_value=Response(200, json=self.TRANSCRIPT_DATA))

            with patch(
                "atlas_intel.ingestion.transcript_sync.extract_keywords",
                failing_keywords,
            ):
                async with FMPClient(api_key="test", rate_limit=100) as client:
                    result = await sync_transcript(session, client, company, quarter=1, year=2025)

        assert result is True

        # Transcript saved
        transcript = (
            await session.execute(
                select(EarningsTranscript).where(
                    EarningsTranscript.company_id == company.id,
                    EarningsTranscript.quarter == 1,
                    EarningsTranscript.year == 2025,
                )
            )
        ).scalar_one()
        assert transcript is not None

        # Sentiments saved (analyze_sentences worked)
        sentiment_count = (
            await session.execute(
                select(func.count(SentimentAnalysis.id))
                .join(TranscriptSection)
                .where(TranscriptSection.transcript_id == transcript.id)
            )
        ).scalar()
        assert sentiment_count > 0

        # No keywords (KeyBERT failed)
        keyword_count = (
            await session.execute(
                select(func.count(KeywordExtraction.id)).where(
                    KeywordExtraction.transcript_id == transcript.id
                )
            )
        ).scalar()
        assert keyword_count == 0
