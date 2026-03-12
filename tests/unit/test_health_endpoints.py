"""Tests for health check endpoints (liveness + readiness)."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from atlas_intel.api.health import router


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    return app


async def test_liveness_always_200(app):
    """Liveness probe always returns 200."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/health/live")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


async def test_readiness_200_when_db_connected(app):
    """Readiness probe returns 200 when DB is connected."""
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock()

    with patch("atlas_intel.api.health.get_session") as mock_get_session:

        async def _override():
            yield mock_session

        app.dependency_overrides[mock_get_session] = _override

        # Use direct function call instead of dependency override
        from atlas_intel.api.health import readiness

        resp = await readiness(session=mock_session)
        assert resp.status_code == 200
        body = resp.body.decode()
        assert "ready" in body


async def test_readiness_503_when_db_disconnected(app):
    """Readiness probe returns 503 when DB is disconnected."""
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(side_effect=Exception("Connection refused"))

    from atlas_intel.api.health import readiness

    resp = await readiness(session=mock_session)
    assert resp.status_code == 503
    body = resp.body.decode()
    assert "not_ready" in body


async def test_readiness_includes_git_sha(app):
    """Readiness probe includes git_sha in response."""
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock()

    with patch("atlas_intel.api.health.settings") as mock_settings:
        mock_settings.git_sha = "abc123"
        from atlas_intel.api.health import readiness

        resp = await readiness(session=mock_session)
        body = resp.body.decode()
        assert "abc123" in body


async def test_health_backward_compat_includes_git_sha():
    """Legacy /health endpoint includes git_sha."""
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock()

    with patch("atlas_intel.api.health.settings") as mock_settings:
        mock_settings.git_sha = "def456"
        from atlas_intel.api.health import health_check

        result = await health_check(session=mock_session)
        assert result["git_sha"] == "def456"
