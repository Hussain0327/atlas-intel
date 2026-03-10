# Atlas Intel

Atlas Intel is an async Python backend for ingesting public-company data into Postgres, enriching it with NLP and derived analytics, and serving it over a FastAPI API and Typer CLI.

The project is not just an API wrapper. It is a persistent data platform with:

- SEC EDGAR ingestion for company metadata, filings, and XBRL facts
- Earnings-call transcript ingestion with FinBERT sentiment and KeyBERT keywords
- Market data ingestion for profiles, prices, and curated metrics
- Alternative and expanded data for news, insider trades, analyst data, institutional holdings, macro indicators, material events, patents, and congress trades
- Operational tooling for scheduled sync jobs, job runs, and freshness monitoring
- Hot-read caching for company detail, latest metrics, price analytics, and analyst consensus
- Valuation models (DCF, relative, analyst-implied), multi-criteria stock screening, and statistical anomaly detection
- LLM-powered report generation and natural language querying via Anthropic Claude
- Real-time alert monitoring with configurable rules, an in-memory event bus, SSE streaming, and aggregated dashboards

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
ANTHROPIC_API_KEY=your_anthropic_key
APP_ENV=development
LOG_LEVEL=INFO
```

Notes:

- `SEC_USER_AGENT` should identify you with real contact information.
- `FMP_API_KEY` is required for market data, transcripts, news, analyst data, and institutional holdings.
- `FRED_API_KEY` is required for macro sync.
- `ANTHROPIC_API_KEY` is required for LLM report generation and natural language queries. Endpoints gracefully return 503 when unavailable.

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

# LLM reports and queries
uv run atlas report AAPL
uv run atlas report AAPL --report-type quick
uv run atlas query "Which tech stocks have the best growth signals?"

# Alerts and dashboard
uv run atlas alerts list
uv run atlas alerts create "AAPL price drop" price_threshold --company-id 1 --conditions '{"field":"close","op":"lt","value":150}'
uv run atlas alerts check
uv run atlas alerts events
uv run atlas dashboard

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

### Analytics and Modeling

- DCF valuation with bear/base/bull scenarios from XBRL cash flow data
- Relative valuation comparing company multiples against sector peers
- Analyst-implied valuation from price target consensus vs current price
- Full valuation combining all three models with majority-vote composite assessment
- Statistical anomaly detection across price (volume spikes, return spikes, volatility breakouts), fundamentals (metric surges vs history), activity (insider/event/analyst clustering), and sector (company vs peer distribution)
- Multi-criteria stock screening with metric filters, company attribute filters, and fusion signal post-filtering
- Simple GET screening with common query params and POST screening for complex filter criteria

### LLM Intelligence

- Report generation via Anthropic Claude with four report types: comprehensive deep-dive, quick executive summary, multi-company comparison, and sector overview
- Streaming report generation via SSE for real-time token delivery
- Natural language querying with a tool-use loop — Claude calls 10 tools mapped to existing services (company lookup, screening, signals, valuation, anomalies, financials, prices, news, insider data, macro indicators)
- Context gathering assembles data from all existing services into compact JSON for LLM consumption
- Graceful degradation: endpoints return 503 when no API key is configured

### Real-time Monitoring

- Configurable alert rules with six rule types: price threshold, volume spike, signal drop, anomaly detected, freshness stale, and metric threshold
- Alert events with severity levels (info, warning, critical) and acknowledgement workflow
- Post-sync alert evaluation: rules are automatically checked after each ingestion pipeline run
- In-memory EventBus with asyncio-based pub/sub and SSE streaming for real-time notifications
- Aggregated dashboard with market overview (sector breakdown, company counts), top movers (gainers, losers, volume leaders), and alert summary
- Cooldown enforcement prevents alert storms from repeated triggers

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
| Valuation | `GET` | `/companies/{identifier}/valuation` | Full valuation (DCF + relative + analyst) |
| Valuation | `GET` | `/companies/{identifier}/valuation/dcf` | DCF valuation with bear/base/bull scenarios |
| Valuation | `GET` | `/companies/{identifier}/valuation/relative` | Relative valuation vs sector peers |
| Valuation | `GET` | `/companies/{identifier}/valuation/analyst` | Analyst price target valuation |
| Anomalies | `GET` | `/companies/{identifier}/anomalies` | All anomaly types |
| Anomalies | `GET` | `/companies/{identifier}/anomalies/price` | Price anomalies (volume, return, volatility) |
| Anomalies | `GET` | `/companies/{identifier}/anomalies/fundamental` | Fundamental anomalies vs history |
| Anomalies | `GET` | `/companies/{identifier}/anomalies/activity` | Activity anomalies (insider, events, grades) |
| Anomalies | `GET` | `/companies/{identifier}/anomalies/sector` | Sector anomalies vs peer distribution |
| Screening | `POST` | `/screen` | Screen companies with complex filter criteria |
| Screening | `GET` | `/screen` | Screen with simple query params |
| Screening | `GET` | `/screen/stats` | Screening universe statistics |
| Reports | `GET` | `/companies/{identifier}/report` | LLM-generated company report |
| Reports | `GET` | `/companies/{identifier}/report/stream` | Streaming company report (SSE) |
| Reports | `POST` | `/reports/comparison` | Multi-company comparison report |
| Reports | `GET` | `/reports/sector/{sector}` | Sector overview report |
| Query | `POST` | `/query` | Natural language query with tool use |
| Query | `POST` | `/query/stream` | Streaming NL query (SSE) |
| Alerts | `POST` | `/alerts/rules` | Create alert rule |
| Alerts | `GET` | `/alerts/rules` | List alert rules |
| Alerts | `GET` | `/alerts/rules/{rule_id}` | Get alert rule |
| Alerts | `PATCH` | `/alerts/rules/{rule_id}` | Update alert rule |
| Alerts | `DELETE` | `/alerts/rules/{rule_id}` | Delete alert rule |
| Alerts | `GET` | `/alerts/events` | List alert events with pagination |
| Alerts | `POST` | `/alerts/events/{event_id}/ack` | Acknowledge an event |
| Alerts | `POST` | `/alerts/events/ack-all` | Acknowledge all events |
| Alerts | `GET` | `/alerts/stream` | SSE stream for real-time alerts |
| Alerts | `POST` | `/alerts/check` | Manually evaluate all alert rules |
| Dashboard | `GET` | `/dashboard` | Full aggregated dashboard |
| Dashboard | `GET` | `/dashboard/market-overview` | Market overview with sector breakdown |
| Dashboard | `GET` | `/dashboard/top-movers` | Top gainers, losers, volume leaders |
| Dashboard | `GET` | `/dashboard/alert-summary` | Alert activity summary |
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

### LLM Commands

```bash
uv run atlas report AAPL                             # Comprehensive report
uv run atlas report AAPL --report-type quick          # Quick executive summary
uv run atlas report AAPL --output report.md           # Save to file
uv run atlas query "What is AAPL's PE ratio?"         # Natural language query
```

### Alert Commands

```bash
uv run atlas alerts list                              # List all alert rules
uv run atlas alerts create "Price drop" price_threshold --company-id 1 \
  --conditions '{"field":"close","op":"lt","value":150}'
uv run atlas alerts events                            # List recent alert events
uv run atlas alerts check                             # Manually evaluate all rules
uv run atlas dashboard                                # Market overview dashboard
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
│   ├── valuation.py
│   ├── anomaly.py
│   ├── screening.py
│   ├── reports.py
│   ├── query.py
│   ├── alerts.py
│   ├── dashboard.py
│   └── ops.py
├── ingestion/
│   ├── client.py
│   ├── fmp_client.py
│   ├── fred_client.py
│   ├── patent_client.py
│   ├── *_sync.py
│   └── pipeline.py
├── llm/
│   ├── client.py
│   ├── context.py
│   ├── prompts.py
│   └── tools.py
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
├── 010_add_congress_trades.py
└── 011_add_alert_tables.py
```

The general runtime shape is:

1. Ingestion jobs fetch from SEC, FMP, FRED, or PatentsView.
2. Transform modules normalize source payloads.
3. SQLAlchemy upserts data into Postgres.
4. Post-sync hooks evaluate alert rules against fresh data and publish events to the EventBus.
5. Services expose read/query logic, derived analytics, and LLM-powered synthesis.
6. FastAPI routes stay thin and mostly delegate to services.

## Operational Notes

- The read cache is currently in-process TTL memory, not Redis.
- Transcript sync now discovers available transcripts before fetching transcript bodies.
- Profile sync records empty-response attempts so uncovered symbols do not spin forever.
- HTTP request spacing is serialized to avoid rate-limit drift under concurrency.
- Freshness data is tracked per company and exposed through `/api/v1/ops/freshness`.
- The LLM client is lazy-loaded as a singleton. Reports and queries gracefully return 503 when no API key is configured.
- Alert evaluation runs after every sync pipeline completion. Failures are logged but never break the sync.
- The EventBus is in-process asyncio-based pub/sub with 30-second heartbeats and 10-minute connection timeout. It does not require Redis or any external broker.

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

The platform is usable as a local financial intelligence backend with eight complete layers: data ingestion, NLP enrichment, market data, alternative data, expanded data with fusion signals, analytics/modeling, LLM intelligence, and real-time monitoring.

The LLM layer synthesizes data from all existing services into actionable reports and supports natural language querying with tool use. The monitoring layer adds configurable alert rules that are evaluated after each sync, an in-memory event bus for SSE streaming, and aggregated dashboards.

Possible next steps:

- More efficient batched compare/read paths
- External cache support (Redis)
- Richer job orchestration and observability
- WebSocket support for the event bus
- Additional alert rule types and notification channels (email, Slack)
