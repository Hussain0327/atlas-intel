# -- Builder stage --
FROM python:3.12-slim AS builder

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --no-install-project

COPY alembic.ini .
COPY alembic/ alembic/
COPY src/ src/

RUN uv sync --no-dev

# -- Runtime stage --
FROM python:3.12-slim

ARG GIT_SHA=dev
ENV GIT_SHA=${GIT_SHA}

RUN useradd --create-home --shell /bin/bash atlas
WORKDIR /app

# Copy the full virtual environment + project from builder
COPY --from=builder /app /app

USER atlas

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health/live')"]

CMD ["/app/.venv/bin/uvicorn", "atlas_intel.main:app", "--host", "0.0.0.0", "--port", "8000"]
