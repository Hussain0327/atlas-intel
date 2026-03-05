"""Earnings transcript API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.api.dependencies import valid_company
from atlas_intel.database import get_session
from atlas_intel.models.company import Company
from atlas_intel.schemas.common import PaginatedResponse
from atlas_intel.schemas.transcript import (
    KeywordAnalysisItem,
    SentimentTrendPoint,
    TranscriptDetail,
    TranscriptSummary,
)
from atlas_intel.services.transcript_service import (
    get_keyword_analysis,
    get_sentiment_trend,
    get_transcript_detail,
    get_transcripts,
)

router = APIRouter(tags=["transcripts"])


@router.get(
    "/companies/{identifier}/transcripts",
    response_model=PaginatedResponse[TranscriptSummary],
)
async def list_transcripts(
    company: Company = Depends(valid_company),
    year: int | None = Query(None, description="Filter by fiscal year"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
) -> PaginatedResponse[TranscriptSummary]:
    """List earnings call transcripts for a company."""
    transcripts, total = await get_transcripts(
        session, company.id, year=year, offset=offset, limit=limit
    )
    return PaginatedResponse(
        items=[TranscriptSummary.model_validate(t) for t in transcripts],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/companies/{identifier}/transcripts/{transcript_id}",
    response_model=TranscriptDetail,
)
async def get_transcript(
    transcript_id: int,
    company: Company = Depends(valid_company),
    session: AsyncSession = Depends(get_session),
) -> TranscriptDetail:
    """Get full transcript with sections, sentiments, and keywords."""
    transcript = await get_transcript_detail(session, company.id, transcript_id)
    if not transcript:
        raise HTTPException(status_code=404, detail=f"Transcript not found: {transcript_id}")

    return TranscriptDetail.model_validate(transcript)


@router.get(
    "/companies/{identifier}/sentiment",
    response_model=list[SentimentTrendPoint],
)
async def sentiment_trend(
    company: Company = Depends(valid_company),
    quarters: int = Query(12, ge=1, le=40, description="Number of quarters to include"),
    session: AsyncSession = Depends(get_session),
) -> list[SentimentTrendPoint]:
    """Get sentiment trend over time for a company's earnings calls."""
    trend = await get_sentiment_trend(session, company.id, quarters=quarters)
    return [SentimentTrendPoint(**point) for point in trend]


@router.get(
    "/companies/{identifier}/keywords",
    response_model=list[KeywordAnalysisItem],
)
async def keyword_analysis(
    company: Company = Depends(valid_company),
    year: int | None = Query(None, description="Filter by fiscal year"),
    top_n: int = Query(30, ge=1, le=100, description="Number of top keywords"),
    session: AsyncSession = Depends(get_session),
) -> list[KeywordAnalysisItem]:
    """Get keyword frequency analysis from earnings call transcripts."""
    keywords = await get_keyword_analysis(session, company.id, year=year, top_n=top_n)
    return [KeywordAnalysisItem(**kw) for kw in keywords]
