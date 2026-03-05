"""News article schemas."""

from datetime import datetime

from pydantic import BaseModel


class NewsArticleResponse(BaseModel):
    id: int
    title: str
    snippet: str | None = None
    url: str
    source_name: str | None = None
    image_url: str | None = None
    published_at: datetime

    model_config = {"from_attributes": True}


class NewsActivityResponse(BaseModel):
    ticker: str
    articles_7d: int = 0
    articles_30d: int = 0
    articles_90d: int = 0
    unique_sources: int = 0
    articles_per_week_avg: float | None = None
    top_sources: list[dict[str, object]] = []
    latest_article: NewsArticleResponse | None = None

    model_config = {"from_attributes": True}
