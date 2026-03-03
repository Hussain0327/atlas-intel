"""Sync earnings call transcripts from FMP and run NLP analysis."""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.ingestion.fmp_client import FMPClient
from atlas_intel.ingestion.transcript_transforms import (
    parse_fmp_transcript,
    parse_transcript_sections,
    split_into_sentences,
)
from atlas_intel.models.company import Company
from atlas_intel.models.earnings_transcript import EarningsTranscript
from atlas_intel.models.keyword_extraction import KeywordExtraction
from atlas_intel.models.sentiment_analysis import SentimentAnalysis
from atlas_intel.models.transcript_section import TranscriptSection
from atlas_intel.nlp.keywords import extract_keywords
from atlas_intel.nlp.sentiment import aggregate_sentiment, analyze_sentences

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    """Return current naive UTC datetime (for use with naive DateTime columns)."""
    return datetime.now(UTC).replace(tzinfo=None)


async def sync_transcript(
    session: AsyncSession,
    client: FMPClient,
    company: Company,
    quarter: int,
    year: int,
    force: bool = False,
) -> bool:
    """Sync a single earnings call transcript and run NLP analysis.

    Returns True if a transcript was processed.
    """
    # Check if transcript already exists
    existing = await session.execute(
        select(EarningsTranscript).where(
            EarningsTranscript.company_id == company.id,
            EarningsTranscript.quarter == quarter,
            EarningsTranscript.year == year,
        )
    )
    existing_transcript = existing.scalar_one_or_none()

    if existing_transcript and not force:
        logger.debug("Transcript Q%d %d already exists for %s", quarter, year, company.ticker)
        return False

    # Fetch from FMP
    logger.info("Fetching Q%d %d transcript for %s...", quarter, year, company.ticker)
    raw_data = await client.get_earning_call_transcript(company.ticker or "", quarter, year)

    if not raw_data:
        logger.debug("No transcript data for %s Q%d %d", company.ticker, quarter, year)
        return False

    # FMP returns a list, take first item
    parsed = parse_fmp_transcript(raw_data[0])
    if not parsed:
        logger.warning("Failed to parse transcript for %s Q%d %d", company.ticker, quarter, year)
        return False

    # Upsert transcript
    transcript_values: dict[str, Any] = {
        "company_id": company.id,
        **parsed,
    }

    if existing_transcript and force:
        # Delete existing to cascade-remove sections/sentiments/keywords
        await session.delete(existing_transcript)
        await session.flush()

    stmt = pg_insert(EarningsTranscript).values(transcript_values)
    stmt = stmt.on_conflict_do_nothing(constraint="uq_transcript_company_quarter")
    await session.execute(stmt)
    await session.flush()

    # Retrieve the transcript record
    result = await session.execute(
        select(EarningsTranscript).where(
            EarningsTranscript.company_id == company.id,
            EarningsTranscript.quarter == quarter,
            EarningsTranscript.year == year,
        )
    )
    transcript = result.scalar_one_or_none()
    if not transcript:
        return False

    # Parse sections
    sections_data = parse_transcript_sections(parsed["raw_text"])

    all_section_sentiments: list[dict[str, Any]] = []

    for sec_data in sections_data:
        # Insert section
        section = TranscriptSection(
            transcript_id=transcript.id,
            section_type=sec_data["section_type"],
            section_order=sec_data["section_order"],
            speaker_name=sec_data["speaker_name"],
            speaker_title=sec_data["speaker_title"],
            content=sec_data["content"],
        )
        session.add(section)
        await session.flush()

        # Run FinBERT on section sentences
        sentences = split_into_sentences(sec_data["content"])
        if sentences:
            sentiments = analyze_sentences(sentences)

            for idx, sent_result in enumerate(sentiments):
                sentiment_record = SentimentAnalysis(
                    section_id=section.id,
                    sentence_index=idx,
                    sentence_text=sentences[idx],
                    positive=sent_result["positive"],
                    negative=sent_result["negative"],
                    neutral=sent_result["neutral"],
                    label=sent_result["label"],
                    confidence=sent_result["confidence"],
                )
                session.add(sentiment_record)

            # Aggregate section-level sentiment
            section_agg = aggregate_sentiment(sentiments)
            section.sentiment_positive = section_agg["positive"]
            section.sentiment_negative = section_agg["negative"]
            section.sentiment_neutral = section_agg["neutral"]
            section.sentiment_label = section_agg["label"]

            all_section_sentiments.extend(sentiments)

    # Aggregate transcript-level sentiment
    if all_section_sentiments:
        transcript_agg = aggregate_sentiment(all_section_sentiments)
        transcript.sentiment_positive = transcript_agg["positive"]
        transcript.sentiment_negative = transcript_agg["negative"]
        transcript.sentiment_neutral = transcript_agg["neutral"]
        transcript.sentiment_label = transcript_agg["label"]

    # Run KeyBERT on full transcript text
    keywords = extract_keywords(parsed["raw_text"])
    for kw in keywords:
        keyword_record = KeywordExtraction(
            transcript_id=transcript.id,
            keyword=kw["keyword"],
            relevance_score=kw["relevance_score"],
        )
        session.add(keyword_record)

    transcript.nlp_processed_at = _utcnow()
    await session.commit()

    logger.info(
        "Processed Q%d %d transcript for %s: %d sections, %d sentences, %d keywords",
        quarter,
        year,
        company.ticker,
        len(sections_data),
        len(all_section_sentiments),
        len(keywords),
    )
    return True


async def sync_transcripts(
    session: AsyncSession,
    client: FMPClient,
    company: Company,
    years: int = 3,
    force: bool = False,
) -> int:
    """Sync all earnings call transcripts for a company over the last N years.

    Returns the number of transcripts processed.
    """
    if (
        not force
        and company.transcripts_synced_at
        and (company.transcripts_synced_at > _utcnow() - timedelta(hours=24))
    ):
        logger.info("Skipping transcripts for %s (synced recently)", company.ticker)
        return 0

    current_year = _utcnow().year
    count = 0

    for year in range(current_year, current_year - years, -1):
        for quarter in range(1, 5):
            processed = await sync_transcript(session, client, company, quarter, year, force=force)
            if processed:
                count += 1

    # Update sync timestamp
    await session.execute(
        update(Company).where(Company.id == company.id).values(transcripts_synced_at=_utcnow())
    )
    await session.commit()

    logger.info("Synced %d transcripts for %s", count, company.ticker)
    return count
