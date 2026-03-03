# Atlas Intel

A Company & Market Intelligence Engine that ingests public financial data and produces analytical outputs. One platform, layered capabilities — turn messy data into investment and strategic decisions.

**What's built so far:**
- SEC EDGAR pipeline ingesting filings, financial facts, and company metadata for 8,000+ public companies
- NLP layer analyzing earnings call transcripts with FinBERT sentiment analysis and KeyBERT keyword extraction
- REST API exposing all data with filtering, pagination, and cross-company comparison
- 123 automated tests + live validation against real SEC/FMP APIs

## Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (package manager)
- Docker (for PostgreSQL)

### Setup

```bash
uv sync                          # Install dependencies
docker compose up db -d          # Start PostgreSQL
uv run alembic upgrade head      # Run migrations

# Ingest SEC data for some companies
uv run atlas sync --ticker AAPL --ticker MSFT --ticker JPM

# Start the API
uv run uvicorn atlas_intel.main:app --reload
```

Visit http://localhost:8000/docs for interactive API docs.

### Transcript Pipeline (optional)

Requires a [Financial Modeling Prep](https://financialmodelingprep.com/) API key:

```bash
# Add to .env
echo "FMP_API_KEY=your_key_here" >> .env

# Sync earnings call transcripts with NLP analysis
uv run atlas sync-transcripts --ticker AAPL --years 3
```

## What It Does

### Layer 1: SEC EDGAR Foundation

Ingests structured financial data from SEC EDGAR for any public company:

- **Company data** — CIK-ticker mapping for 8,000+ companies, SIC codes, exchange info
- **Filing metadata** — Full filing history (10-K, 10-Q, 8-K, etc.) with accession numbers and dates
- **Financial facts** — XBRL data points in a tall/EAV table design (Revenue, Assets, EPS, and thousands more concepts across all SEC taxonomies)
- **Incremental sync** — submissions refresh every 24h, facts every 7d, with `--force` override

### Layer 2: NLP Analysis

Processes earnings call transcripts from FMP with on-ingestion NLP:

- **Transcript parsing** — Speaker detection, section classification (prepared remarks vs Q&A), sentence splitting
- **FinBERT sentiment** — Sentence-level financial sentiment (positive/negative/neutral), aggregated to section and transcript level
- **KeyBERT keywords** — Top keywords extracted with MMR diversity scoring
- **Trend tracking** — Sentiment trends over time, keyword frequency analysis across quarters

## API Endpoints

All under `/api/v1`:

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check + DB stats |
| GET | `/companies/` | Search/list companies (fuzzy name search) |
| GET | `/companies/{id}` | Company detail (by ticker or CIK) |
| GET | `/companies/{id}/filings/` | Filing history (filterable by form type) |
| GET | `/companies/{id}/filings/{accession}` | Specific filing detail |
| GET | `/companies/{id}/financials` | Query financial facts |
| GET | `/companies/{id}/financials/summary` | Key metrics summary |
| GET | `/financials/compare` | Compare metric across companies |
| GET | `/companies/{id}/transcripts` | Earnings call transcripts |
| GET | `/companies/{id}/transcripts/{tid}` | Full transcript + NLP analysis |
| GET | `/companies/{id}/sentiment` | Sentiment trend over time |
| GET | `/companies/{id}/keywords` | Keyword frequency analysis |

The `{id}` parameter auto-resolves: numeric values are treated as CIK, strings as ticker.

## CLI

```bash
uv run atlas sync --ticker AAPL              # Full SEC sync (filings + facts)
uv run atlas sync --ticker AAPL --force      # Force refresh (ignore freshness)
uv run atlas sync-tickers                    # Sync CIK-ticker mapping (~8K companies)
uv run atlas sync-transcripts --ticker AAPL  # Transcript + NLP pipeline
uv run atlas sync-transcripts --years 5      # Override lookback window
```

## Architecture

```
src/atlas_intel/
├── main.py              # FastAPI app
├── config.py            # Pydantic Settings (.env)
├── database.py          # Async SQLAlchemy engine
├── cli.py               # Typer CLI
├── models/              # ORM (7 models)
│   ├── company.py
│   ├── filing.py
│   ├── financial_fact.py
│   ├── earnings_transcript.py
│   ├── transcript_section.py
│   ├── sentiment_analysis.py
│   └── keyword_extraction.py
├── ingestion/           # Data pipelines
│   ├── client.py            # SEC EDGAR client (rate-limited)
│   ├── fmp_client.py        # FMP client (rate-limited)
│   ├── transforms.py        # SEC response parsing
│   ├── transcript_transforms.py  # Transcript parsing
│   ├── ticker_sync.py       # CIK-ticker sync
│   ├── submission_sync.py   # Filing metadata sync
│   ├── facts_sync.py        # XBRL facts sync
│   ├── transcript_sync.py   # Transcript + NLP sync
│   └── pipeline.py          # Orchestration
├── nlp/                 # NLP models
│   ├── sentiment.py         # FinBERT (ProsusAI/finbert)
│   └── keywords.py          # KeyBERT (all-MiniLM-L6-v2)
├── services/            # Business logic
├── schemas/             # Pydantic models
└── api/                 # FastAPI routes

alembic/                 # Database migrations (001-003)
tests/                   # Unit, integration, API, edge case tests
scripts/                 # Live validation script
```

### Data Model

```
companies ──< filings
    │
    └──< financial_facts (EAV/tall table, one row per XBRL data point)
    │
    └──< earnings_transcripts ──< transcript_sections ──< sentiment_analyses
              │
              └──< keyword_extractions
```

The tall table design for financial facts handles thousands of distinct XBRL concepts without schema changes. Sentiment analysis cascades from sentence to section to transcript level.

## Tech Stack

- **Python 3.12** — async throughout
- **FastAPI** + **uvicorn** — REST API
- **SQLAlchemy 2.0** (async) + **asyncpg** — ORM and PostgreSQL driver
- **Alembic** — database migrations
- **PostgreSQL 16** — with `pg_trgm` for fuzzy search
- **httpx** — async HTTP clients (rate-limited, with retry)
- **transformers** + **PyTorch** — FinBERT sentiment analysis
- **KeyBERT** + **sentence-transformers** — keyword extraction
- **Typer** — CLI framework
- **uv** — package management

## Development

```bash
uv run pytest --cov                          # 123 tests, 78% coverage
uv run ruff check . && uv run ruff format .  # Lint + format
uv run mypy src/atlas_intel                  # Type check

# Live validation against real APIs (hits SEC EDGAR, writes to dev DB)
APP_ENV=production uv run python scripts/validate_pipeline.py
# With transcript pipeline (requires FMP_API_KEY):
APP_ENV=production uv run python scripts/validate_pipeline.py --with-transcripts
```

### Test Structure

- **Unit tests** — Pure logic: transforms, NLP aggregation, parsing edge cases (no DB/HTTP)
- **Integration tests** — Real PostgreSQL + mocked APIs (`respx`), mocked NLP models
- **API tests** — FastAPI `AsyncClient` with ASGI transport
- **Edge case tests** — FMP 429/500 retry, empty transcripts, 512-token overflow, amended filing dedup, concurrent safety

## Roadmap

Each layer is a standalone milestone that independently demonstrates a skill:

| Layer | Status | What It Demonstrates |
|-------|--------|---------------------|
| 1. SEC EDGAR foundation | **Done** | Data engineering, ETL, API design, PostgreSQL |
| 2. NLP layer | **Done** | NLP/ML integration, FinBERT, pipeline architecture |
| 3. Market data integration | Planned | Quantitative finance, time series, factor models |
| 4. Alternative data | Planned | Data sourcing, web scraping, multi-source fusion |
| 5. Analytics/modeling | Planned | Valuation models, screening, anomaly detection |
| 6. LLM layer | Planned | RAG, report generation, natural language queries |
| 7. Real-time monitoring | Planned | Streaming, alerts, dashboards |
