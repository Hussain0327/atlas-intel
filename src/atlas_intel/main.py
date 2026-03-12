"""FastAPI application factory."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from atlas_intel.api.middleware import AuthMiddleware, RequestIDMiddleware
from atlas_intel.api.router import api_router
from atlas_intel.config import settings
from atlas_intel.logging import setup_logging

STATIC_DIR = Path(__file__).parent / "static"

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup and shutdown lifecycle."""
    # --- Startup ---
    setup_logging(level=settings.log_level, env=settings.app_env)
    settings.validate_production()
    logger.info(
        "Atlas Intel starting",
        extra={"env": settings.app_env, "git_sha": settings.git_sha},
    )

    # Sentry (optional)
    if settings.sentry_dsn:
        try:
            import sentry_sdk
            from sentry_sdk.integrations.fastapi import FastApiIntegration
            from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

            sentry_sdk.init(
                dsn=settings.sentry_dsn,
                environment=settings.app_env,
                release=settings.git_sha,
                traces_sample_rate=0.1,
                integrations=[FastApiIntegration(), SqlalchemyIntegration()],
            )
            logger.info("Sentry initialized")
        except Exception:
            logger.warning("Failed to initialize Sentry", exc_info=True)

    yield

    # --- Shutdown ---
    logger.info("Atlas Intel shutting down")
    from atlas_intel.database import engine

    await engine.dispose()

    from atlas_intel.services.event_bus import event_bus

    await event_bus.publish({"type": "shutdown", "source": "system"})

    if settings.sentry_dsn:
        try:
            import sentry_sdk

            sentry_sdk.flush(timeout=2)
        except Exception:
            pass


def create_app() -> FastAPI:
    app = FastAPI(
        title="Atlas Intel",
        description="Company & Market Intelligence Engine",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Middleware (order matters: last added = first executed)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(AuthMiddleware)
    app.add_middleware(RequestIDMiddleware)

    # Prometheus metrics
    try:
        from prometheus_fastapi_instrumentator import Instrumentator

        Instrumentator(
            excluded_handlers=["/metrics", "/api/v1/health/live"],
        ).instrument(app).expose(app, endpoint="/metrics")
    except Exception:
        logger.warning("Failed to setup Prometheus metrics", exc_info=True)

    app.include_router(api_router)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/", include_in_schema=False)
    async def root() -> RedirectResponse:
        return RedirectResponse(url="/dashboard")

    @app.get("/dashboard", include_in_schema=False)
    async def dashboard_ui() -> FileResponse:
        return FileResponse(STATIC_DIR / "dashboard.html")

    return app


app = create_app()
