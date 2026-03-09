"""Sync earnings call transcripts from FMP and run NLP analysis."""

import logging
from datetime import timedelta
from typing import Any

import httpx
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.ingestion.fmp_client import FMPClient
from atlas_intel.ingestion.transcript_transforms import (
    parse_fmp_transcript,
    parse_transcript_sections,
    split_into_sentences,
)
from atlas_intel.ingestion.utils import utcnow
from atlas_intel.models.company import Company
from atlas_intel.models.earnings_transcript import EarningsTranscript
from atlas_intel.models.keyword_extraction import KeywordExtraction
from atlas_intel.models.sentiment_analysis import SentimentAnalysis
from atlas_intel.models.transcript_section import TranscriptSection
from atlas_intel.nlp.keywords import extract_keywords
from atlas_intel.nlp.sentiment import aggregate_sentiment, analyze_sentences
from atlas_intel.services.company_service import invalidate_company_detail_cache

logger = logging.getLogger(__name__)


def _available_transcript_pairs(
    available: list[dict[str, Any]],
    current_year: int,
    years: int,
) -> list[tuple[int, int]]:
    """Normalize and filter available transcript metadata to unique quarter/year pairs."""
    earliest_year = current_year - years + 1
    discovered: set[tuple[int, int]] = set()

    for entry in available:
        quarter = entry.get("quarter")
        year = entry.get("year")
        try:
            quarter_int = int(quarter)  # type: ignore[arg-type]
            year_int = int(year)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue

        if quarter_int not in {1, 2, 3, 4}:
            continue
        if year_int < earliest_year or year_int > current_year:
            continue

        discovered.add((year_int, quarter_int))

    return sorted(discovered, reverse=True)


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
    try:
        raw_data = await client.get_earning_call_transcript(company.ticker or "", quarter, year)
    except httpx.HTTPStatusError as e:
        logger.warning(
            "HTTP %d fetching transcript for %s Q%d %d: %s",
            e.response.status_code,
            company.ticker,
            quarter,
            year,
            e,
        )
        return False

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
            try:
                sentiments = analyze_sentences(sentences)
            except Exception:
                logger.exception(
                    "Sentiment analysis failed for %s Q%d %d section %d",
                    company.ticker,
                    quarter,
                    year,
                    sec_data["section_order"],
                )
                sentiments = []

            for idx, (sentence, sent_result) in enumerate(zip(sentences, sentiments, strict=False)):
                sentiment_record = SentimentAnalysis(
                    section_id=section.id,
                    sentence_index=idx,
                    sentence_text=sentence,
                    positive=sent_result["positive"],
                    negative=sent_result["negative"],
                    neutral=sent_result["neutral"],
                    label=sent_result["label"],
                    confidence=sent_result["confidence"],
                )
                session.add(sentiment_record)

            # Aggregate section-level sentiment
            if sentiments:
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
    try:
        keywords = extract_keywords(parsed["raw_text"])
    except Exception:
        logger.exception(
            "Keyword extraction failed for %s Q%d %d",
            company.ticker,
            quarter,
            year,
        )
        keywords = []

    for kw in keywords:
        keyword_record = KeywordExtraction(
            transcript_id=transcript.id,
            keyword=kw["keyword"],
            relevance_score=kw["relevance_score"],
        )
        session.add(keyword_record)

    transcript.nlp_processed_at = utcnow()
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
        and (company.transcripts_synced_at > utcnow() - timedelta(hours=24))
    ):
        logger.info("Skipping transcripts for %s (synced recently)", company.ticker)
        return 0

    current_year = utcnow().year
    ticker = company.ticker or ""
    available = await client.get_available_transcripts(ticker)
    transcript_pairs = _available_transcript_pairs(
        available,
        current_year=current_year,
        years=years,
    )

    if not transcript_pairs:
        logger.info("No available transcripts discovered for %s in lookback window", ticker)
        await session.execute(
            update(Company).where(Company.id == company.id).values(transcripts_synced_at=utcnow())
        )
        await session.commit()
        await invalidate_company_detail_cache(company)
        return 0

    count = 0

    for year, quarter in transcript_pairs:
        processed = await sync_transcript(session, client, company, quarter, year, force=force)
        if processed:
            count += 1

    # Update sync timestamp
    await session.execute(
        update(Company).where(Company.id == company.id).values(transcripts_synced_at=utcnow())
    )
    await session.commit()
    await invalidate_company_detail_cache(company)

    logger.info("Synced %d transcripts for %s", count, company.ticker)
    return count
