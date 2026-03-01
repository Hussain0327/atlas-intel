"""FastAPI application factory."""

from fastapi import FastAPI

from atlas_intel.api.router import api_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="Atlas Intel",
        description="Company & Market Intelligence Engine",
        version="0.1.0",
    )
    app.include_router(api_router)
    return app


app = create_app()
