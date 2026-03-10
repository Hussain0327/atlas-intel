"""Top-level API router combining all sub-routers."""

from fastapi import APIRouter

from atlas_intel.api.alerts import router as alerts_router
from atlas_intel.api.analyst import router as analyst_router
from atlas_intel.api.anomaly import router as anomaly_router
from atlas_intel.api.companies import router as companies_router
from atlas_intel.api.congress import router as congress_router
from atlas_intel.api.dashboard import router as dashboard_router
from atlas_intel.api.events import router as events_router
from atlas_intel.api.filings import router as filings_router
from atlas_intel.api.financials import router as financials_router
from atlas_intel.api.health import router as health_router
from atlas_intel.api.insider import router as insider_router
from atlas_intel.api.institutional import router as institutional_router
from atlas_intel.api.macro import router as macro_router
from atlas_intel.api.metrics import router as metrics_router
from atlas_intel.api.news import router as news_router
from atlas_intel.api.ops import router as ops_router
from atlas_intel.api.patents import router as patents_router
from atlas_intel.api.prices import router as prices_router
from atlas_intel.api.query import router as query_router
from atlas_intel.api.reports import router as reports_router
from atlas_intel.api.screening import router as screening_router
from atlas_intel.api.signals import router as signals_router
from atlas_intel.api.transcripts import router as transcripts_router
from atlas_intel.api.valuation import router as valuation_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health_router)
api_router.include_router(companies_router)
api_router.include_router(filings_router)
api_router.include_router(financials_router)
api_router.include_router(transcripts_router)
api_router.include_router(prices_router)
api_router.include_router(metrics_router)
api_router.include_router(news_router)
api_router.include_router(insider_router)
api_router.include_router(analyst_router)
api_router.include_router(institutional_router)
api_router.include_router(ops_router)
api_router.include_router(macro_router)
api_router.include_router(events_router)
api_router.include_router(patents_router)
api_router.include_router(congress_router)
api_router.include_router(signals_router)
api_router.include_router(valuation_router)
api_router.include_router(anomaly_router)
api_router.include_router(screening_router)
api_router.include_router(reports_router)
api_router.include_router(query_router)
api_router.include_router(alerts_router)
api_router.include_router(dashboard_router)
