"""Top-level API router combining all sub-routers."""

from fastapi import APIRouter

from atlas_intel.api.companies import router as companies_router
from atlas_intel.api.filings import router as filings_router
from atlas_intel.api.financials import router as financials_router
from atlas_intel.api.health import router as health_router
from atlas_intel.api.transcripts import router as transcripts_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health_router)
api_router.include_router(companies_router)
api_router.include_router(filings_router)
api_router.include_router(financials_router)
api_router.include_router(transcripts_router)
