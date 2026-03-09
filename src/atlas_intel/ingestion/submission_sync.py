"""Sync SEC filing submissions for tracked companies."""

import logging
from datetime import timedelta
from typing import Any

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.ingestion.client import SECClient
from atlas_intel.ingestion.transforms import parse_submissions
from atlas_intel.ingestion.utils import utcnow
from atlas_intel.models.company import Company
from atlas_intel.models.filing import Filing
from atlas_intel.services.company_service import invalidate_company_detail_cache

logger = logging.getLogger(__name__)

# asyncpg has a 32767 parameter limit. Each filing row has ~8 columns,
# so we batch at 1000 rows to stay safely under that limit.
BATCH_SIZE = 1000


async def sync_submissions(
    session: AsyncSession,
    client: SECClient,
    company: Company,
    force: bool = False,
) -> int:
    """Sync filing submissions for a single company.

    Returns the number of filings upserted.
    """
    if (
        not force
        and company.submissions_synced_at
        and (company.submissions_synced_at > utcnow() - timedelta(hours=24))
    ):
        logger.info("Skipping submissions for %s (synced recently)", company.ticker)
        return 0

    logger.info("Fetching submissions for %s (CIK %d)...", company.ticker, company.cik)
    data = await client.get_submissions(company.cik)
    company_info, filings = parse_submissions(data)

    # Update company metadata from submission data
    update_fields = {k: v for k, v in company_info.items() if v is not None}
    if update_fields:
        await session.execute(
            update(Company).where(Company.id == company.id).values(**update_fields)
        )

    if not filings:
        logger.info("No filings found for %s", company.ticker)
        await session.execute(
            update(Company).where(Company.id == company.id).values(submissions_synced_at=utcnow())
        )
        await session.commit()
        return 0

    # Add company_id and deduplicate by accession_number within the batch.
    # SEC responses can contain an original + amendment with the same accession
    # number. PostgreSQL ON CONFLICT DO UPDATE cannot affect the same row twice
    # in a single INSERT, so we keep only the last occurrence (the amendment).
    deduped: dict[str, dict[str, Any]] = {}
    for f in filings:
        f["company_id"] = company.id
        deduped[f["accession_number"]] = f
    filings = list(deduped.values())

    for i in range(0, len(filings), BATCH_SIZE):
        batch = filings[i : i + BATCH_SIZE]
        stmt = pg_insert(Filing).values(batch)
        stmt = stmt.on_conflict_do_update(
            index_elements=["accession_number"],
            set_={
                "form_type": stmt.excluded.form_type,
                "filing_date": stmt.excluded.filing_date,
                "period_of_report": stmt.excluded.period_of_report,
                "primary_document": stmt.excluded.primary_document,
                "is_xbrl": stmt.excluded.is_xbrl,
                "filing_url": stmt.excluded.filing_url,
            },
        )
        await session.execute(stmt)

    await session.execute(
        update(Company).where(Company.id == company.id).values(submissions_synced_at=utcnow())
    )
    await session.commit()
    await invalidate_company_detail_cache(company)

    logger.info("Upserted %d filings for %s", len(filings), company.ticker)
    return len(filings)
