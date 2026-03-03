"""API tests for transcript endpoints."""

from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from atlas_intel.models.company import Company
from atlas_intel.models.earnings_transcript import EarningsTranscript
from atlas_intel.models.keyword_extraction import KeywordExtraction
from atlas_intel.models.sentiment_analysis import SentimentAnalysis
from atlas_intel.models.transcript_section import TranscriptSection


@pytest.fixture
async def seeded_transcript(engine):
    """Seed a company with transcript data for API tests."""
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as session:
        company = Company(cik=320193, ticker="AAPL", name="Apple Inc.")
        session.add(company)
        await session.flush()

        transcript = EarningsTranscript(
            company_id=company.id,
            quarter=1,
            year=2024,
            transcript_date=date(2024, 1, 25),
            raw_text="Full transcript text here.",
            title="Apple Q1 2024 Earnings Call",
            sentiment_positive=Decimal("0.65"),
            sentiment_negative=Decimal("0.15"),
            sentiment_neutral=Decimal("0.20"),
            sentiment_label="positive",
            nlp_processed_at=datetime(2024, 2, 1, 12, 0, 0),
        )
        session.add(transcript)
        await session.flush()

        section = TranscriptSection(
            transcript_id=transcript.id,
            section_type="prepared_remarks",
            section_order=0,
            speaker_name="Tim Cook",
            speaker_title="CEO",
            content="We had a great quarter with record revenue.",
            sentiment_positive=Decimal("0.70"),
            sentiment_negative=Decimal("0.10"),
            sentiment_neutral=Decimal("0.20"),
            sentiment_label="positive",
        )
        session.add(section)
        await session.flush()

        sentiment = SentimentAnalysis(
            section_id=section.id,
            sentence_index=0,
            sentence_text="We had a great quarter with record revenue.",
            positive=Decimal("0.70"),
            negative=Decimal("0.10"),
            neutral=Decimal("0.20"),
            label="positive",
            confidence=Decimal("0.70"),
        )
        session.add(sentiment)

        keyword = KeywordExtraction(
            transcript_id=transcript.id,
            keyword="record revenue",
            relevance_score=Decimal("0.85"),
            frequency=1,
        )
        session.add(keyword)

        await session.commit()
        return {"company_id": company.id, "transcript_id": transcript.id}


class TestListTranscripts:
    async def test_list_transcripts(self, client, seeded_transcript):
        resp = await client.get("/api/v1/companies/AAPL/transcripts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["quarter"] == 1
        assert data["items"][0]["year"] == 2024
        assert data["items"][0]["sentiment_label"] == "positive"

    async def test_filter_by_year(self, client, seeded_transcript):
        resp = await client.get("/api/v1/companies/AAPL/transcripts?year=2024")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

        resp = await client.get("/api/v1/companies/AAPL/transcripts?year=2023")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    async def test_company_not_found(self, client):
        resp = await client.get("/api/v1/companies/INVALID/transcripts")
        assert resp.status_code == 404


class TestGetTranscript:
    async def test_get_transcript_detail(self, client, seeded_transcript):
        tid = seeded_transcript["transcript_id"]
        resp = await client.get(f"/api/v1/companies/AAPL/transcripts/{tid}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["quarter"] == 1
        assert data["year"] == 2024
        assert len(data["sections"]) == 1
        assert data["sections"][0]["speaker_name"] == "Tim Cook"
        assert len(data["sections"][0]["sentiments"]) == 1
        assert len(data["keywords"]) == 1
        assert data["keywords"][0]["keyword"] == "record revenue"

    async def test_transcript_not_found(self, client, seeded_transcript):
        resp = await client.get("/api/v1/companies/AAPL/transcripts/9999")
        assert resp.status_code == 404


class TestSentimentTrend:
    async def test_sentiment_trend(self, client, seeded_transcript):
        resp = await client.get("/api/v1/companies/AAPL/sentiment")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["sentiment_label"] == "positive"
        assert data[0]["quarter"] == 1
        assert data[0]["year"] == 2024


class TestKeywordAnalysis:
    async def test_keyword_analysis(self, client, seeded_transcript):
        resp = await client.get("/api/v1/companies/AAPL/keywords")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["keyword"] == "record revenue"
        assert data[0]["occurrence_count"] == 1

    async def test_keyword_year_filter(self, client, seeded_transcript):
        resp = await client.get("/api/v1/companies/AAPL/keywords?year=2024")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

        resp = await client.get("/api/v1/companies/AAPL/keywords?year=2023")
        assert resp.status_code == 200
        assert len(resp.json()) == 0
