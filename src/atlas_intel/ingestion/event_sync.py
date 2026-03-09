"""Sync SEC 8-K material events."""

import logging
from datetime import date, timedelta
from typing import Any

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.ingestion.client import SECClient
from atlas_intel.ingestion.event_transforms import parse_8k_events
from atlas_intel.ingestion.utils import utcnow
from atlas_intel.models.company import Company
from atlas_intel.models.material_event import MaterialEvent

logger = logging.getLogger(__name__)

BATCH_SIZE = 1000


async def sync_material_events(
    session: AsyncSession,
    client: SECClient,
    company: Company,
    force: bool = False,
) -> int:
    """Sync 8-K material events for a company.

    Freshness: 24h. Fetches last 12 months of 8-K filings.
    Returns the number of events inserted.
    """
    if (
        not force
        and company.material_events_synced_at
        and (company.material_events_synced_at > utcnow() - timedelta(hours=24))
    ):
        logger.info("Skipping material events for %s (synced recently)", company.ticker)
        return 0

    start_date = (date.today() - timedelta(days=365)).isoformat()

    logger.info("Fetching 8-K events for %s...", company.ticker)
    filings = await client.get_8k_filings(company.cik, start_date=start_date)
    events = parse_8k_events(filings)

    if not events:
        await session.execute(
            update(Company)
            .where(Company.id == company.id)
            .values(material_events_synced_at=utcnow())
        )
        await session.commit()
        return 0

    # In-batch dedup by (accession_number, item_number)
    seen: set[tuple[str | None, str | None]] = set()
    deduped: list[dict[str, Any]] = []
    for e in events:
        key = (e["accession_number"], e["item_number"])
        if key not in seen:
            seen.add(key)
            deduped.append(e)
    events = deduped

    total_inserted = 0
    for i in range(0, len(events), BATCH_SIZE):
        batch = events[i : i + BATCH_SIZE]
        for e in batch:
            e["company_id"] = company.id

        stmt = pg_insert(MaterialEvent).values(batch)
        stmt = stmt.on_conflict_do_nothing(constraint="uq_material_event_dedup")
        result = await session.execute(stmt)
        total_inserted += result.rowcount  # type: ignore[attr-defined]

    await session.execute(
        update(Company).where(Company.id == company.id).values(material_events_synced_at=utcnow())
    )
    await session.commit()

    logger.info("Inserted %d material events for %s", total_inserted, company.ticker)
    return total_inserted
