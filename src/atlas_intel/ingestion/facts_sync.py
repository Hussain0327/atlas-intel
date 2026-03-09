"""Sync XBRL company facts from SEC EDGAR."""

import logging
from datetime import timedelta

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.ingestion.client import SECClient
from atlas_intel.ingestion.transforms import parse_company_facts
from atlas_intel.ingestion.utils import utcnow
from atlas_intel.models.company import Company
from atlas_intel.models.financial_fact import FinancialFact
from atlas_intel.services.company_service import invalidate_company_detail_cache

logger = logging.getLogger(__name__)

BATCH_SIZE = 1000


async def sync_facts(
    session: AsyncSession,
    client: SECClient,
    company: Company,
    force: bool = False,
) -> int:
    """Sync XBRL financial facts for a single company.

    Returns the number of facts inserted.
    """
    if (
        not force
        and company.facts_synced_at
        and (company.facts_synced_at > utcnow() - timedelta(days=7))
    ):
        logger.info("Skipping facts for %s (synced recently)", company.ticker)
        return 0

    logger.info("Fetching company facts for %s (CIK %d)...", company.ticker, company.cik)
    data = await client.get_company_facts(company.cik)
    facts = parse_company_facts(data)
    logger.info("Parsed %d facts for %s", len(facts), company.ticker)

    if not facts:
        await session.execute(
            update(Company).where(Company.id == company.id).values(facts_synced_at=utcnow())
        )
        await session.commit()
        return 0

    total_inserted = 0
    for i in range(0, len(facts), BATCH_SIZE):
        batch = facts[i : i + BATCH_SIZE]
        for f in batch:
            f["company_id"] = company.id

        stmt = pg_insert(FinancialFact).values(batch)
        stmt = stmt.on_conflict_do_nothing(
            constraint="uq_financial_facts_dedup",
        )
        result = await session.execute(stmt)
        total_inserted += result.rowcount  # type: ignore[attr-defined]

    await session.execute(
        update(Company).where(Company.id == company.id).values(facts_synced_at=utcnow())
    )
    await session.commit()
    await invalidate_company_detail_cache(company)

    logger.info(
        "Inserted %d new facts for %s (total parsed: %d)",
        total_inserted,
        company.ticker,
        len(facts),
    )
    return total_inserted
