"""Sync company profile data from FMP."""

import logging
from datetime import timedelta

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.ingestion.fmp_client import FMPClient
from atlas_intel.ingestion.market_transforms import parse_company_profile
from atlas_intel.ingestion.utils import utcnow
from atlas_intel.models.company import Company

logger = logging.getLogger(__name__)


async def sync_profile(
    session: AsyncSession,
    client: FMPClient,
    company: Company,
    force: bool = False,
) -> bool:
    """Sync company profile (sector, industry, CEO, etc.) from FMP.

    Returns True if the profile was updated.
    """
    if (
        not force
        and company.profile_synced_at
        and (company.profile_synced_at > utcnow() - timedelta(days=7))
    ):
        logger.info("Skipping profile for %s (synced recently)", company.ticker)
        return False

    ticker = company.ticker or ""
    logger.info("Fetching profile for %s...", ticker)
    raw_data = await client.get_company_profile(ticker)
    profile = parse_company_profile(raw_data)

    if not profile:
        logger.warning("No profile data for %s", ticker)
        return False

    profile["profile_synced_at"] = utcnow()

    await session.execute(update(Company).where(Company.id == company.id).values(**profile))
    await session.commit()

    logger.info(
        "Updated profile for %s (sector=%s, industry=%s)",
        ticker,
        profile.get("sector"),
        profile.get("industry"),
    )
    return True
