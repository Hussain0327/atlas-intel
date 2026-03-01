# Atlas Intel

Company & Market Intelligence Engine — SEC EDGAR ingestion pipeline, XBRL financial data extraction, and queryable REST API.

## What it does

- Ingests company data from SEC EDGAR (CIK-ticker mapping, filing metadata, XBRL financial facts)
- Stores structured financial data in PostgreSQL using an EAV/tall table design
- Exposes a FastAPI REST API for querying companies, filings, and financial metrics
- Supports cross-company financial comparisons

## Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (package manager)
- Docker (for PostgreSQL)

### Setup

```bash
# Install dependencies
uv sync

# Start PostgreSQL
docker compose up db -d

# Run migrations
uv run alembic upgrade head

# Sync some companies from SEC EDGAR
uv run atlas sync --ticker AAPL --ticker MSFT --ticker GOOGL

# Start the API
uv run uvicorn atlas_intel.main:app --reload
```

Visit http://localhost:8000/docs for the interactive API docs.

### API Endpoints

All under `/api/v1`:

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check + DB stats |
| GET | `/companies/` | Search/list companies |
| GET | `/companies/{identifier}` | Company detail (by ticker or CIK) |
| GET | `/companies/{identifier}/filings/` | Filing history |
| GET | `/companies/{identifier}/filings/{accession}` | Specific filing |
| GET | `/companies/{identifier}/financials` | Query financial facts |
| GET | `/companies/{identifier}/financials/summary` | Key metrics summary |
| GET | `/financials/compare` | Compare metric across companies |

### CLI Commands

```bash
# Full sync for specific companies
uv run atlas sync --ticker AAPL --ticker MSFT

# Force refresh (ignore recent sync timestamps)
uv run atlas sync --ticker AAPL --force

# Sync only the CIK-ticker mapping (~13K companies)
uv run atlas sync-tickers
```

## Development

```bash
# Run tests (requires PostgreSQL)
uv run pytest

# With coverage
uv run pytest --cov

# Lint
uv run ruff check .

# Format
uv run ruff format .

# Type check
uv run mypy src/atlas_intel
```

## Architecture

```
src/atlas_intel/
├── main.py          # FastAPI app factory
├── config.py        # Pydantic Settings
├── database.py      # Async SQLAlchemy engine
├── models/          # SQLAlchemy ORM (companies, filings, financial_facts)
├── schemas/         # Pydantic request/response models
├── api/             # FastAPI routes
├── services/        # Business logic layer
├── ingestion/       # SEC EDGAR pipeline (client, transforms, sync modules)
└── cli.py           # Typer CLI
```

### Data Model

- **companies** — Core entity with CIK, ticker, name, SIC, exchange
- **filings** — SEC filing metadata (10-K, 10-Q, etc.)
- **financial_facts** — XBRL data points in EAV/tall format (one row per data point)

The tall table design handles the thousands of distinct XBRL taxonomy tags without schema changes.

## Tech Stack

- **FastAPI** + **uvicorn** — async REST API
- **SQLAlchemy 2.0** (async) + **asyncpg** — ORM and PostgreSQL driver
- **Alembic** — database migrations
- **httpx** — async HTTP client for SEC EDGAR
- **Typer** — CLI framework
- **uv** — package management
