"""Sync patents from USPTO PatentsView."""

import logging
from datetime import timedelta
from typing import Any

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.ingestion.patent_client import PatentClient
from atlas_intel.ingestion.patent_transforms import parse_patents
from atlas_intel.ingestion.utils import utcnow
from atlas_intel.models.company import Company
from atlas_intel.models.patent import Patent

logger = logging.getLogger(__name__)

BATCH_SIZE = 1000

# Sectors where patent data is not relevant
_SKIP_SECTORS = {"Financial Services", "Financial"}


async def sync_patents(
    session: AsyncSession,
    client: PatentClient,
    company: Company,
    force: bool = False,
) -> int:
    """Sync patents for a company from USPTO PatentsView.

    Freshness: 30d (patent data changes slowly).
    Uses company name as assignee search term.
    Returns the number of patents inserted.
    """
    if (
        not force
        and company.patents_synced_at
        and (company.patents_synced_at > utcnow() - timedelta(days=30))
    ):
        logger.info("Skipping patents for %s (synced recently)", company.ticker)
        return 0

    # Skip purely financial companies
    if company.sector and company.sector in _SKIP_SECTORS:
        logger.info("Skipping patents for %s (financial sector)", company.ticker)
        await session.execute(
            update(Company).where(Company.id == company.id).values(patents_synced_at=utcnow())
        )
        await session.commit()
        return 0

    company_name = company.name
    logger.info("Fetching patents for %s (%s)...", company.ticker, company_name)

    try:
        raw_data = await client.search_patents(company_name)
    except Exception:
        logger.exception("Failed to fetch patents for %s", company.ticker)
        return 0

    patents = parse_patents(raw_data)

    if not patents:
        await session.execute(
            update(Company).where(Company.id == company.id).values(patents_synced_at=utcnow())
        )
        await session.commit()
        return 0

    # In-batch dedup by patent_number
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for p in patents:
        if p["patent_number"] not in seen:
            seen.add(p["patent_number"])
            deduped.append(p)
    patents = deduped

    total_inserted = 0
    for i in range(0, len(patents), BATCH_SIZE):
        batch = patents[i : i + BATCH_SIZE]
        for p in batch:
            p["company_id"] = company.id

        stmt = pg_insert(Patent).values(batch)
        stmt = stmt.on_conflict_do_nothing(constraint="uq_patent_company_number")
        result = await session.execute(stmt)
        total_inserted += result.rowcount  # type: ignore[attr-defined]

    await session.execute(
        update(Company).where(Company.id == company.id).values(patents_synced_at=utcnow())
    )
    await session.commit()

    logger.info("Inserted %d patents for %s", total_inserted, company.ticker)
    return total_inserted
