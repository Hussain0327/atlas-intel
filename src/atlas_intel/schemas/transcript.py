"""Earnings transcript schemas."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class SentimentAnalysisResponse(BaseModel):
    id: int
    sentence_index: int
    sentence_text: str
    positive: Decimal
    negative: Decimal
    neutral: Decimal
    label: str
    confidence: Decimal

    model_config = {"from_attributes": True}


class TranscriptSectionResponse(BaseModel):
    id: int
    section_type: str
    section_order: int
    speaker_name: str | None = None
    speaker_title: str | None = None
    content: str
    sentiment_positive: Decimal | None = None
    sentiment_negative: Decimal | None = None
    sentiment_neutral: Decimal | None = None
    sentiment_label: str | None = None
    sentiments: list[SentimentAnalysisResponse] = []

    model_config = {"from_attributes": True}


class KeywordResponse(BaseModel):
    id: int
    keyword: str
    relevance_score: Decimal
    frequency: int

    model_config = {"from_attributes": True}


class TranscriptSummary(BaseModel):
    id: int
    quarter: int
    year: int
    transcript_date: date
    title: str | None = None
    sentiment_positive: Decimal | None = None
    sentiment_negative: Decimal | None = None
    sentiment_neutral: Decimal | None = None
    sentiment_label: str | None = None
    nlp_processed_at: datetime | None = None

    model_config = {"from_attributes": True}


class TranscriptDetail(BaseModel):
    id: int
    company_id: int
    quarter: int
    year: int
    transcript_date: date
    title: str | None = None
    raw_text: str
    sentiment_positive: Decimal | None = None
    sentiment_negative: Decimal | None = None
    sentiment_neutral: Decimal | None = None
    sentiment_label: str | None = None
    nlp_processed_at: datetime | None = None
    sections: list[TranscriptSectionResponse] = []
    keywords: list[KeywordResponse] = []

    model_config = {"from_attributes": True}


class SentimentTrendPoint(BaseModel):
    quarter: int
    year: int
    transcript_date: date
    sentiment_positive: Decimal | None = None
    sentiment_negative: Decimal | None = None
    sentiment_neutral: Decimal | None = None
    sentiment_label: str | None = None


class KeywordAnalysisItem(BaseModel):
    keyword: str
    total_relevance: Decimal
    occurrence_count: int
