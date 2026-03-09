# Atlas Intel

Atlas Intel is an async Python backend for ingesting public-company data into Postgres, enriching it with NLP and derived analytics, and serving it over a FastAPI API and Typer CLI.

The project is not just an API wrapper. It is a persistent data platform with:

- SEC EDGAR ingestion for company metadata, filings, and XBRL facts
- Earnings-call transcript ingestion with FinBERT sentiment and KeyBERT keywords
- Market data ingestion for profiles, prices, and curated metrics
- Alternative and expanded data for news, insider trades, analyst data, institutional holdings, macro indicators, material events, patents, and congress trades
- Operational tooling for scheduled sync jobs, job runs, and freshness monitoring
- Hot-read caching for company detail, latest metrics, price analytics, and analyst consensus

## Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- Docker for local Postgres

### Local Setup

```bash
uv sync
docker compose up db -d
uv run alembic upgrade head
```

The Docker setup initializes both `atlas_intel` and `atlas_intel_test`, and enables `pg_trgm` for fuzzy search and ranked company lookup.

### Environment

Create a `.env` file as needed:

```bash
DATABASE_URL=postgresql+asyncpg://atlas:atlas@localhost:5432/atlas_intel
SEC_USER_AGENT="AtlasIntel your-email@example.com"
FMP_API_KEY=your_fmp_key
FRED_API_KEY=your_fred_key
APP_ENV=development
LOG_LEVEL=INFO
```

Notes:

- `SEC_USER_AGENT` should identify you with real contact information.
- `FMP_API_KEY` is required for market data, transcripts, news, analyst data, and institutional holdings.
- `FRED_API_KEY` is required for macro sync.

### Common Commands

```bash
# SEC foundation
uv run atlas sync-tickers
uv run atlas sync --ticker AAPL --ticker MSFT

# FMP-backed datasets
uv run atlas sync-market --ticker AAPL --years 3
uv run atlas sync-transcripts --ticker AAPL --years 3
uv run atlas sync-alt --ticker AAPL

# Additional domains
uv run atlas sync-macro
uv run atlas sync-expanded --ticker AAPL

# API
uv run uvicorn atlas_intel.main:app --reload
```

Interactive docs are available at `http://localhost:8000/docs`.

## What Is Implemented

### SEC Foundation

- Company master data and ticker/CIK mapping
- Filing metadata from EDGAR submissions
- Tall/EAV XBRL facts table for SEC company facts
- Incremental freshness-aware sync with force overrides

### Transcript + NLP Layer

- Available-transcript discovery before transcript fetches
- Transcript parsing into sections and sentences
- FinBERT sentence sentiment aggregated to section and transcript level
- KeyBERT keyword extraction
- Transcript sentiment trends and keyword analysis endpoints

### Market Data Layer

- Company profiles
- Daily OHLCV prices
- Curated TTM and annual metrics
- Derived analytics such as returns, volatility, SMAs, and 52-week high/low

### Alternative and Expanded Data

- News articles and news activity
- Insider trades and insider sentiment
- Analyst estimates, grades, price targets, and consensus
- Institutional holdings
- FRED macro indicators
- Material events from 8-K-style event extraction
- Patents and innovation summaries
- Congress trades
- Composite signals built from multiple datasets

### Operations

- Postgres-backed sync jobs and sync job runs
- Freshness summary across company sync domains
- Read-side TTL cache for hot endpoints

## Public API

All endpoints are under `/api/v1`.

Important: the public company search endpoint is `GET /api/v1/companies/`.
There is no Atlas endpoint called `search-index`.
`https://efts.sec.gov/LATEST/search-index` is only an internal SEC EFTS endpoint used by the ingestion client for filing search.

### Core Endpoints

| Area | Method | Path | Description |
|---|---|---|---|
| Health | `GET` | `/health` | Health check with basic DB stats |
| Companies | `GET` | `/companies/` | Search/list companies with filters and ranked fuzzy matching |
| Companies | `GET` | `/companies/{identifier}` | Company detail by ticker or numeric CIK |
| Filings | `GET` | `/companies/{identifier}/filings/` | Filing history |
| Filings | `GET` | `/companies/{identifier}/filings/{accession}` | Filing detail |
| Financials | `GET` | `/companies/{identifier}/financials` | Query financial facts |
| Financials | `GET` | `/companies/{identifier}/financials/summary` | Financial summary by year |
| Financials | `GET` | `/financials/compare` | Multi-ticker comparison with `X-Unresolved-Tickers` header |
| Financials | `GET` | `/financials/compare/report` | Comparison with explicit unresolved ticker payload |
| Transcripts | `GET` | `/companies/{identifier}/transcripts` | Transcript summaries |
| Transcripts | `GET` | `/companies/{identifier}/transcripts/{transcript_id}` | Transcript detail |
| Transcripts | `GET` | `/companies/{identifier}/sentiment` | Transcript sentiment trend |
| Transcripts | `GET` | `/companies/{identifier}/keywords` | Transcript keyword analysis |
| Prices | `GET` | `/companies/{identifier}/prices` | OHLCV prices |
| Prices | `GET` | `/companies/{identifier}/prices/analytics` | Derived price analytics |
| Prices | `GET` | `/companies/{identifier}/prices/returns` | Daily returns |
| Metrics | `GET` | `/companies/{identifier}/metrics` | Market metrics |
| Metrics | `GET` | `/companies/{identifier}/metrics/latest` | Latest TTM metrics |
| Metrics | `GET` | `/metrics/compare` | Metric comparison with unresolved ticker header |
| Metrics | `GET` | `/metrics/compare/report` | Metric comparison with unresolved ticker payload |
| News | `GET` | `/companies/{identifier}/news` | Company news |
| News | `GET` | `/companies/{identifier}/news/activity` | News activity summary |
| Insider | `GET` | `/companies/{identifier}/insider-trades` | Insider trading history |
| Insider | `GET` | `/companies/{identifier}/insider-trades/sentiment` | Insider sentiment summary |
| Analyst | `GET` | `/companies/{identifier}/analyst/estimates` | Analyst estimates |
| Analyst | `GET` | `/companies/{identifier}/analyst/grades` | Analyst grades |
| Analyst | `GET` | `/companies/{identifier}/analyst/price-target` | Price target consensus |
| Analyst | `GET` | `/companies/{identifier}/analyst/consensus` | Fused analyst view |
| Institutional | `GET` | `/companies/{identifier}/institutional-holdings` | Institutional holdings |
| Institutional | `GET` | `/companies/{identifier}/institutional-holdings/top` | Top holders |
| Macro | `GET` | `/macro/indicators` | Macro indicator observations |
| Macro | `GET` | `/macro/summary` | Latest macro snapshot |
| Events | `GET` | `/companies/{identifier}/events` | Material events |
| Events | `GET` | `/companies/{identifier}/events/summary` | Event summary |
| Patents | `GET` | `/companies/{identifier}/patents` | Patent records |
| Patents | `GET` | `/companies/{identifier}/patents/innovation` | Innovation summary |
| Congress | `GET` | `/companies/{identifier}/congress` | Congress trades |
| Congress | `GET` | `/companies/{identifier}/congress/summary` | Congress summary |
| Signals | `GET` | `/companies/{identifier}/signals` | All composite signals |
| Signals | `GET` | `/companies/{identifier}/signals/sentiment` | Sentiment signal |
| Signals | `GET` | `/companies/{identifier}/signals/growth` | Growth signal |
| Signals | `GET` | `/companies/{identifier}/signals/risk` | Risk signal |
| Signals | `GET` | `/companies/{identifier}/signals/smart-money` | Smart money signal |
| Ops | `GET` | `/ops/jobs` | Configured sync jobs |
| Ops | `GET` | `/ops/jobs/{job_id}/runs` | Recent runs for a job |
| Ops | `GET` | `/ops/freshness` | Fresh/stale summary by sync domain |

### Search and Compare Semantics

- Company search is `GET /api/v1/companies/?q=Apple`.
- `identifier` resolves automatically: numeric values are treated as CIK, other values as tickers.
- Missing companies return `404`.
- Existing companies with no related records typically return empty collections or sparse analytics payloads.
- Compare endpoints preserve the original list-based responses and expose unresolved tickers through `X-Unresolved-Tickers`.
- Report endpoints are the additive API for explicit unresolved-target reporting.

## CLI

### Ingestion Commands

```bash
uv run atlas sync --ticker AAPL --ticker MSFT
uv run atlas sync --ticker AAPL --force
uv run atlas sync-tickers
uv run atlas sync-transcripts --ticker AAPL --years 3
uv run atlas sync-market --ticker AAPL --years 5
uv run atlas sync-alt --ticker AAPL
uv run atlas sync-macro
uv run atlas sync-expanded --ticker AAPL
```

### Operational Commands

```bash
uv run atlas freshness
uv run atlas jobs list
uv run atlas jobs create --name nightly-market --sync-type market_data --ticker AAPL --ticker MSFT --interval-minutes 1440
uv run atlas jobs run-due
uv run atlas jobs run --job-id 1
uv run atlas jobs runs --job-id 1
```

Supported scheduled job sync types are currently:

- `sec_full`
- `transcripts`
- `market_data`
- `alt_data`

## Architecture

```text
src/atlas_intel/
├── main.py
├── config.py
├── database.py
├── cli.py
├── cache.py
├── api/
│   ├── companies.py
│   ├── filings.py
│   ├── financials.py
│   ├── transcripts.py
│   ├── prices.py
│   ├── metrics.py
│   ├── news.py
│   ├── insider.py
│   ├── analyst.py
│   ├── institutional.py
│   ├── macro.py
│   ├── events.py
│   ├── patents.py
│   ├── congress.py
│   ├── signals.py
│   └── ops.py
├── ingestion/
│   ├── client.py
│   ├── fmp_client.py
│   ├── fred_client.py
│   ├── patent_client.py
│   ├── *_sync.py
│   └── pipeline.py
├── models/
├── nlp/
├── schemas/
└── services/

alembic/versions/
├── 001_initial_schema.py
├── 002_nulls_not_distinct_dedup.py
├── 003_add_transcript_tables.py
├── 004_add_market_data_tables.py
├── 005_add_alternative_data_tables.py
├── 006_add_sync_job_tables.py
├── 007_add_macro_indicators.py
├── 008_add_material_events.py
├── 009_add_patents.py
└── 010_add_congress_trades.py
```

The general runtime shape is:

1. Ingestion jobs fetch from SEC, FMP, FRED, or PatentsView.
2. Transform modules normalize source payloads.
3. SQLAlchemy upserts data into Postgres.
4. Services expose read/query logic and derived analytics.
5. FastAPI routes stay thin and mostly delegate to services.

## Operational Notes

- The read cache is currently in-process TTL memory, not Redis.
- Transcript sync now discovers available transcripts before fetching transcript bodies.
- Profile sync records empty-response attempts so uncovered symbols do not spin forever.
- HTTP request spacing is serialized to avoid rate-limit drift under concurrency.
- Freshness data is tracked per company and exposed through `/api/v1/ops/freshness`.

## Testing and Validation

Run tests with `uv run pytest`, not bare `pytest`.

```bash
uv run pytest -q
uv run ruff check src tests
uv run mypy src/atlas_intel
```

Notes:

- DB-backed tests use `atlas_intel_test`.
- `docker compose up db -d` plus the repo's `init-db.sql` is enough for local test DB bootstrap.
- The test harness resets schema state between tests.

### Live Validation

```bash
APP_ENV=production uv run python scripts/validate_pipeline.py
APP_ENV=production uv run python scripts/validate_pipeline.py --with-transcripts
```

These commands hit real upstream APIs and write into your configured database.

## Current State

The platform is already usable as a local financial intelligence backend. The current strength is the data and ingestion plane: broad coverage, normalized storage, incremental sync, and a consistent API surface.

The next likely steps are:

- deeper ranking and screening analytics
- more efficient batched compare/read paths
- external cache support
- richer job orchestration and observability
- LLM and report-generation layers on top of the existing warehouse
