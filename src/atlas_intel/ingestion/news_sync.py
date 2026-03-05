"""Sync stock news from FMP."""

import logging
from datetime import timedelta
from typing import Any

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.ingestion.alt_data_transforms import parse_news_articles
from atlas_intel.ingestion.fmp_client import FMPClient
from atlas_intel.ingestion.utils import utcnow
from atlas_intel.models.company import Company
from atlas_intel.models.news_article import NewsArticle

logger = logging.getLogger(__name__)

BATCH_SIZE = 1000


async def sync_news(
    session: AsyncSession,
    client: FMPClient,
    company: Company,
    force: bool = False,
) -> int:
    """Sync news articles for a company.

    Returns the number of news records upserted.
    """
    if (
        not force
        and company.news_synced_at
        and (company.news_synced_at > utcnow() - timedelta(hours=6))
    ):
        logger.info("Skipping news for %s (synced recently)", company.ticker)
        return 0

    ticker = company.ticker or ""

    logger.info("Fetching news for %s...", ticker)
    raw_data = await client.get_stock_news(ticker, limit=50)
    articles = parse_news_articles(raw_data)

    if not articles:
        await session.execute(
            update(Company).where(Company.id == company.id).values(news_synced_at=utcnow())
        )
        await session.commit()
        return 0

    # Dedup by url within batch
    seen_urls: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for a in articles:
        if a["url"] not in seen_urls:
            seen_urls.add(a["url"])
            deduped.append(a)
    articles = deduped

    total_upserted = 0
    for i in range(0, len(articles), BATCH_SIZE):
        batch = articles[i : i + BATCH_SIZE]
        for a in batch:
            a["company_id"] = company.id

        stmt = pg_insert(NewsArticle).values(batch)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_news_article_company_url",
            set_={
                "title": stmt.excluded.title,
                "snippet": stmt.excluded.snippet,
                "source_name": stmt.excluded.source_name,
                "image_url": stmt.excluded.image_url,
                "published_at": stmt.excluded.published_at,
            },
        )
        result = await session.execute(stmt)
        total_upserted += result.rowcount  # type: ignore[attr-defined]

    await session.execute(
        update(Company).where(Company.id == company.id).values(news_synced_at=utcnow())
    )
    await session.commit()

    logger.info("Upserted %d news articles for %s", total_upserted, ticker)
    return total_upserted
