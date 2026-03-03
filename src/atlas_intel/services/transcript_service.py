"""Earnings transcript business logic."""

from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from atlas_intel.models.earnings_transcript import EarningsTranscript
from atlas_intel.models.keyword_extraction import KeywordExtraction
from atlas_intel.models.transcript_section import TranscriptSection


async def get_transcripts(
    session: AsyncSession,
    company_id: int,
    year: int | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[EarningsTranscript], int]:
    """Get paginated list of transcripts for a company."""
    stmt = select(EarningsTranscript).where(EarningsTranscript.company_id == company_id)
    count_stmt = select(func.count(EarningsTranscript.id)).where(
        EarningsTranscript.company_id == company_id
    )

    if year:
        stmt = stmt.where(EarningsTranscript.year == year)
        count_stmt = count_stmt.where(EarningsTranscript.year == year)

    total = (await session.execute(count_stmt)).scalar() or 0

    stmt = (
        stmt.order_by(EarningsTranscript.year.desc(), EarningsTranscript.quarter.desc())
        .offset(offset)
        .limit(limit)
    )

    result = await session.execute(stmt)
    return list(result.scalars().all()), total


async def get_transcript_detail(
    session: AsyncSession,
    company_id: int,
    transcript_id: int,
) -> EarningsTranscript | None:
    """Get a single transcript with sections, sentiments, and keywords eagerly loaded."""
    stmt = (
        select(EarningsTranscript)
        .where(
            EarningsTranscript.id == transcript_id,
            EarningsTranscript.company_id == company_id,
        )
        .options(
            selectinload(EarningsTranscript.sections).selectinload(TranscriptSection.sentiments),
            selectinload(EarningsTranscript.keywords),
        )
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_sentiment_trend(
    session: AsyncSession,
    company_id: int,
    quarters: int = 12,
) -> list[dict[str, Any]]:
    """Get chronological sentiment scores for the last N quarters."""
    stmt = (
        select(EarningsTranscript)
        .where(
            EarningsTranscript.company_id == company_id,
            EarningsTranscript.sentiment_label.is_not(None),
        )
        .order_by(EarningsTranscript.year.desc(), EarningsTranscript.quarter.desc())
        .limit(quarters)
    )
    result = await session.execute(stmt)
    transcripts = list(result.scalars().all())

    # Return in chronological order (oldest first)
    return [
        {
            "quarter": t.quarter,
            "year": t.year,
            "transcript_date": t.transcript_date,
            "sentiment_positive": t.sentiment_positive,
            "sentiment_negative": t.sentiment_negative,
            "sentiment_neutral": t.sentiment_neutral,
            "sentiment_label": t.sentiment_label,
        }
        for t in reversed(transcripts)
    ]


async def get_keyword_analysis(
    session: AsyncSession,
    company_id: int,
    year: int | None = None,
    top_n: int = 30,
) -> list[dict[str, Any]]:
    """Get aggregated keyword analysis across transcripts."""
    stmt = (
        select(
            KeywordExtraction.keyword,
            func.sum(KeywordExtraction.relevance_score).label("total_relevance"),
            func.count(KeywordExtraction.id).label("occurrence_count"),
        )
        .join(EarningsTranscript)
        .where(EarningsTranscript.company_id == company_id)
    )

    if year:
        stmt = stmt.where(EarningsTranscript.year == year)

    stmt = (
        stmt.group_by(KeywordExtraction.keyword)
        .order_by(func.sum(KeywordExtraction.relevance_score).desc())
        .limit(top_n)
    )

    result = await session.execute(stmt)
    rows = result.all()

    return [
        {
            "keyword": row.keyword,
            "total_relevance": Decimal(str(round(float(row.total_relevance), 4))),
            "occurrence_count": row.occurrence_count,
        }
        for row in rows
    ]
