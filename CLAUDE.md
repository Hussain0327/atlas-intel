# Atlas Intel

Company & Market Intelligence Engine. Phase 1: SEC EDGAR foundation.

## Key Commands

```bash
uv sync                                    # Install deps
docker compose up db -d                    # Start PostgreSQL
uv run alembic upgrade head                # Run migrations
uv run atlas sync --ticker AAPL            # Ingest company data
uv run uvicorn atlas_intel.main:app --reload  # Start API
uv run pytest --cov                        # Run tests
uv run ruff check . && uv run ruff format --check .  # Lint
uv run mypy src/atlas_intel                # Type check
```

## Architecture

- `src/atlas_intel/` — main package
  - `models/` — SQLAlchemy ORM: Company, Filing, FinancialFact (EAV tall table)
  - `ingestion/` — SEC EDGAR pipeline: HTTP client (rate-limited), ticker/submission/facts sync
  - `api/` — FastAPI routes under `/api/v1`
  - `services/` — business logic between API and DB
  - `schemas/` — Pydantic request/response models
  - `cli.py` — Typer CLI (`atlas sync`, `atlas sync-tickers`)
- `alembic/` — async database migrations
- `tests/` — unit (transforms), integration (DB + mocked SEC), API (TestClient)

## Conventions

- Python 3.12, async throughout
- SQLAlchemy 2.0 mapped_column style
- Pydantic v2 with `model_config = {"from_attributes": True}`
- All DB operations use `AsyncSession`
- Bulk upserts via `INSERT ... ON CONFLICT` (PostgreSQL dialect)
- `{identifier}` in API routes auto-resolves: numeric = CIK, otherwise = ticker

## SEC EDGAR

- Rate limit: 8 req/s (below 10/s hard limit)
- User-Agent: `AtlasIntel rajahh7865@gmail.com` (required by SEC)
- Endpoints: `sec.gov/files/company_tickers.json`, `data.sec.gov/submissions/`, `data.sec.gov/api/xbrl/companyfacts/`
- Incremental sync: submissions every 24h, facts every 7d (unless `--force`)

## Database

- PostgreSQL 16 with `pg_trgm` extension (fuzzy company name search)
- `financial_facts` uses tall/EAV design — one row per XBRL data point
- Dedup key: `(company_id, taxonomy, concept, unit, period_end, period_start, accession_number)`

## Testing

- Unit tests: pure logic, no DB/HTTP
- Integration tests: real PostgreSQL + `respx` mocked SEC API
- API tests: FastAPI `AsyncClient` with ASGI transport
- Fixtures: truncated real SEC responses in `tests/fixtures/`
- Test DB: `atlas_intel_test` (separate from dev)
