"""API key authentication and request ID middleware."""

import logging
import secrets
import time
from uuid import uuid4

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from atlas_intel.config import settings

logger = logging.getLogger(__name__)

# Paths that bypass API key auth
_PUBLIC_PREFIXES = (
    "/api/v1/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/metrics",
    "/dashboard",
    "/static",
    "/",
)


class AuthMiddleware(BaseHTTPMiddleware):
    """API key authentication.

    If ``settings.api_key`` is empty, all requests pass through (dev mode).
    Otherwise checks ``Authorization: Bearer <key>``, ``X-API-Key: <key>``,
    or ``?token=<key>`` (for SSE clients).
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Dev mode: no auth configured
        if not settings.api_key:
            return await call_next(request)

        path = request.url.path

        # Public endpoints skip auth
        if path == "/" or any(
            path.startswith(prefix) for prefix in _PUBLIC_PREFIXES if prefix != "/"
        ):
            return await call_next(request)

        # Extract key from multiple sources
        key = _extract_key(request)
        if not key or not secrets.compare_digest(key, settings.api_key):
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key"},
            )

        return await call_next(request)


def _extract_key(request: Request) -> str | None:
    """Try Authorization header, X-API-Key header, then query param."""
    # Bearer token
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()

    # Custom header
    api_key = request.headers.get("x-api-key")
    if api_key:
        return api_key

    # Query param (SSE / browser)
    return request.query_params.get("token")


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach a unique request ID to each request, bind to structlog context."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("x-request-id", str(uuid4()))
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        start = time.perf_counter()
        logger.info("request_started")

        response = await call_next(request)

        duration_ms = round((time.perf_counter() - start) * 1000, 1)
        logger.info(
            "request_completed",
            extra={"status_code": response.status_code, "duration_ms": duration_ms},
        )

        response.headers["x-request-id"] = request_id
        structlog.contextvars.clear_contextvars()
        return response
