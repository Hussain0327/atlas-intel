"""News article business logic and analytics."""

from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.models.news_article import NewsArticle
from atlas_intel.schemas.news import NewsArticleResponse


async def get_news(
    session: AsyncSession,
    company_id: int,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[NewsArticle], int]:
    """Query news articles paginated. Returns (articles, total_count)."""
    count_stmt = select(func.count(NewsArticle.id)).where(NewsArticle.company_id == company_id)
    total = (await session.execute(count_stmt)).scalar() or 0

    stmt = (
        select(NewsArticle)
        .where(NewsArticle.company_id == company_id)
        .order_by(NewsArticle.published_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all()), total


async def get_news_activity(
    session: AsyncSession,
    company_id: int,
    ticker: str,
) -> dict[str, Any]:
    """Compute news activity analytics."""
    today = date.today()
    analytics: dict[str, Any] = {"ticker": ticker}

    # Count articles in time windows
    for label, days in [("articles_7d", 7), ("articles_30d", 30), ("articles_90d", 90)]:
        cutoff = today - timedelta(days=days)
        count = (
            await session.execute(
                select(func.count(NewsArticle.id)).where(
                    NewsArticle.company_id == company_id,
                    NewsArticle.published_at >= cutoff,
                )
            )
        ).scalar() or 0
        analytics[label] = count

    # Unique sources
    unique = (
        await session.execute(
            select(func.count(func.distinct(NewsArticle.source_name))).where(
                NewsArticle.company_id == company_id
            )
        )
    ).scalar() or 0
    analytics["unique_sources"] = unique

    # Articles per week avg (90d)
    if analytics["articles_90d"] > 0:
        analytics["articles_per_week_avg"] = round(analytics["articles_90d"] / (90 / 7), 2)
    else:
        analytics["articles_per_week_avg"] = None

    # Top 5 sources
    top_sources_result = await session.execute(
        select(NewsArticle.source_name, func.count(NewsArticle.id).label("cnt"))
        .where(NewsArticle.company_id == company_id, NewsArticle.source_name.isnot(None))
        .group_by(NewsArticle.source_name)
        .order_by(func.count(NewsArticle.id).desc())
        .limit(5)
    )
    analytics["top_sources"] = [
        {"source": row[0], "count": row[1]} for row in top_sources_result.all()
    ]

    # Latest article
    latest_result = await session.execute(
        select(NewsArticle)
        .where(NewsArticle.company_id == company_id)
        .order_by(NewsArticle.published_at.desc())
        .limit(1)
    )
    latest = latest_result.scalar_one_or_none()
    analytics["latest_article"] = NewsArticleResponse.model_validate(latest) if latest else None

    return analytics
