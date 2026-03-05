"""Shared FastAPI dependencies for API routes."""

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.database import get_session
from atlas_intel.models.company import Company
from atlas_intel.services.company_service import get_company_by_identifier


async def valid_company(
    identifier: str,
    session: AsyncSession = Depends(get_session),
) -> Company:
    """Resolve a company by ticker or CIK, or raise 404."""
    company = await get_company_by_identifier(session, identifier)
    if not company:
        raise HTTPException(status_code=404, detail=f"Company not found: {identifier}")
    return company
