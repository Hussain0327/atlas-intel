"""Tests for API key authentication middleware."""

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from atlas_intel.api.middleware import AuthMiddleware


def _make_app(api_key: str = "") -> FastAPI:
    """Create a minimal FastAPI app with AuthMiddleware."""
    app = FastAPI()

    with patch("atlas_intel.api.middleware.settings") as mock_settings:
        mock_settings.api_key = api_key
        # We need to capture the middleware with the patched settings
        # Instead, build app that references settings at request time
        pass

    app.add_middleware(AuthMiddleware)

    @app.get("/api/v1/health/live")
    async def health():
        return {"status": "ok"}

    @app.get("/api/v1/companies")
    async def companies():
        return {"data": []}

    @app.get("/docs")
    async def docs():
        return {"docs": True}

    @app.get("/metrics")
    async def metrics():
        return {"metrics": True}

    @app.get("/dashboard")
    async def dashboard():
        return {"dashboard": True}

    return app


@pytest.fixture
def app_no_auth():
    return _make_app(api_key="")


@pytest.fixture
def app_with_auth():
    return _make_app(api_key="test-secret-key")


async def test_passthrough_when_no_key(app_no_auth):
    """When api_key is empty, all requests pass through."""
    with patch("atlas_intel.api.middleware.settings") as mock_settings:
        mock_settings.api_key = ""
        async with AsyncClient(
            transport=ASGITransport(app=app_no_auth), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/companies")
            assert resp.status_code == 200


async def test_401_on_missing_key(app_with_auth):
    """Returns 401 when API key is required but not provided."""
    with patch("atlas_intel.api.middleware.settings") as mock_settings:
        mock_settings.api_key = "test-secret-key"
        async with AsyncClient(
            transport=ASGITransport(app=app_with_auth), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/companies")
            assert resp.status_code == 401
            assert resp.json()["detail"] == "Invalid or missing API key"


async def test_401_on_wrong_key(app_with_auth):
    """Returns 401 when API key is wrong."""
    with patch("atlas_intel.api.middleware.settings") as mock_settings:
        mock_settings.api_key = "test-secret-key"
        async with AsyncClient(
            transport=ASGITransport(app=app_with_auth), base_url="http://test"
        ) as client:
            resp = await client.get(
                "/api/v1/companies", headers={"Authorization": "Bearer wrong-key"}
            )
            assert resp.status_code == 401


async def test_success_with_bearer_token(app_with_auth):
    """Accepts valid Bearer token."""
    with patch("atlas_intel.api.middleware.settings") as mock_settings:
        mock_settings.api_key = "test-secret-key"
        async with AsyncClient(
            transport=ASGITransport(app=app_with_auth), base_url="http://test"
        ) as client:
            resp = await client.get(
                "/api/v1/companies",
                headers={"Authorization": "Bearer test-secret-key"},
            )
            assert resp.status_code == 200


async def test_success_with_x_api_key_header(app_with_auth):
    """Accepts valid X-API-Key header."""
    with patch("atlas_intel.api.middleware.settings") as mock_settings:
        mock_settings.api_key = "test-secret-key"
        async with AsyncClient(
            transport=ASGITransport(app=app_with_auth), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/companies", headers={"X-API-Key": "test-secret-key"})
            assert resp.status_code == 200


async def test_success_with_token_query_param(app_with_auth):
    """Accepts valid token query parameter (for SSE clients)."""
    with patch("atlas_intel.api.middleware.settings") as mock_settings:
        mock_settings.api_key = "test-secret-key"
        async with AsyncClient(
            transport=ASGITransport(app=app_with_auth), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/companies?token=test-secret-key")
            assert resp.status_code == 200


async def test_health_skips_auth(app_with_auth):
    """Health endpoints bypass authentication."""
    with patch("atlas_intel.api.middleware.settings") as mock_settings:
        mock_settings.api_key = "test-secret-key"
        async with AsyncClient(
            transport=ASGITransport(app=app_with_auth), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/health/live")
            assert resp.status_code == 200


async def test_docs_skips_auth(app_with_auth):
    """Docs endpoint bypasses authentication."""
    with patch("atlas_intel.api.middleware.settings") as mock_settings:
        mock_settings.api_key = "test-secret-key"
        async with AsyncClient(
            transport=ASGITransport(app=app_with_auth), base_url="http://test"
        ) as client:
            resp = await client.get("/docs")
            assert resp.status_code == 200


async def test_metrics_skips_auth(app_with_auth):
    """Metrics endpoint bypasses authentication."""
    with patch("atlas_intel.api.middleware.settings") as mock_settings:
        mock_settings.api_key = "test-secret-key"
        async with AsyncClient(
            transport=ASGITransport(app=app_with_auth), base_url="http://test"
        ) as client:
            resp = await client.get("/metrics")
            assert resp.status_code == 200


async def test_dashboard_skips_auth(app_with_auth):
    """Dashboard endpoint bypasses authentication."""
    with patch("atlas_intel.api.middleware.settings") as mock_settings:
        mock_settings.api_key = "test-secret-key"
        async with AsyncClient(
            transport=ASGITransport(app=app_with_auth), base_url="http://test"
        ) as client:
            resp = await client.get("/dashboard")
            assert resp.status_code == 200
