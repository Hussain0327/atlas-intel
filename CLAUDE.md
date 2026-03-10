# Atlas Intel

Company & Market Intelligence Engine. Layers 1-8 complete (SEC EDGAR + NLP transcripts + Market Data + Alternative Data + Expanded Data & Fusion Signals + Analytics & Modeling + LLM Intelligence + Real-time Monitoring).

## Key Commands

```bash
uv sync                                    # Install deps
docker compose up db -d                    # Start PostgreSQL
uv run alembic upgrade head                # Run migrations
uv run atlas sync --ticker AAPL            # SEC pipeline (filings + facts)
uv run atlas sync-transcripts --ticker AAPL  # Transcript + NLP pipeline
uv run atlas sync-market --ticker AAPL     # Market data (prices + profile + metrics)
uv run atlas sync-alt --ticker AAPL        # Alt data (news, insider, analyst, holdings)
uv run atlas sync-macro                    # FRED macro indicators (GDP, rates, etc.)
uv run atlas sync-expanded --ticker AAPL   # Expanded data (8-K events, patents, congress)
uv run atlas report AAPL                   # LLM company report (requires ANTHROPIC_API_KEY)
uv run atlas query "AAPL PE ratio?"        # Natural language query
uv run atlas alerts check                  # Evaluate alert rules
uv run atlas dashboard                     # Market overview dashboard
uv run uvicorn atlas_intel.main:app --reload  # Start API
uv run pytest --cov                        # Run tests (457+ tests)
uv run ruff check . && uv run ruff format --check .  # Lint
uv run mypy src/atlas_intel                # Type check
APP_ENV=production uv run python scripts/validate_pipeline.py --all  # Live validation
```

## Architecture

- `src/atlas_intel/` — main package
  - `models/` — SQLAlchemy ORM: Company, Filing, FinancialFact, EarningsTranscript, TranscriptSection, SentimentAnalysis, KeywordExtraction, StockPrice, MarketMetric, NewsArticle, InsiderTrade, AnalystEstimate, AnalystGrade, PriceTarget, InstitutionalHolding, MacroIndicator, MaterialEvent, Patent, CongressTrade, AlertRule, AlertEvent
  - `ingestion/` — SEC EDGAR + FMP + FRED + PatentsView pipelines: rate-limited HTTP clients, ticker/submission/facts/transcript/price/profile/metrics/news/insider/analyst/institutional/macro/event/patent/congress sync, post-sync alert hooks
  - `nlp/` — FinBERT sentiment analysis, KeyBERT keyword extraction (lazy-loaded singletons)
  - `llm/` — Anthropic Claude integration: client.py (lazy singleton), context.py (data gathering), prompts.py (report/query templates), tools.py (10 tool definitions for NL queries)
  - `api/` — FastAPI routes under `/api/v1` (24 routers including reports, query, alerts, dashboard)
  - `services/` — business logic between API and DB, including fusion_service for composite signals, valuation_service (DCF/relative/analyst), anomaly_service (z-score detection), screening_service (multi-criteria filtering), report_service (LLM report generation), query_service (NL query with tool-use loop), alert_service (rule CRUD + evaluation engine), dashboard_service (aggregations), event_bus (SSE pub/sub)
  - `schemas/` — Pydantic request/response models
  - `cli.py` — Typer CLI (`atlas sync`, `atlas sync-tickers`, `atlas sync-transcripts`, `atlas sync-market`, `atlas sync-alt`, `atlas sync-macro`, `atlas sync-expanded`, `atlas report`, `atlas query`, `atlas alerts`, `atlas dashboard`)
- `alembic/` — async database migrations (001-011)
- `tests/` — unit (transforms, NLP, fusion, LLM tools/context, alert evaluation, event bus), integration (DB + mocked APIs), API (TestClient), edge cases
- `scripts/validate_pipeline.py` — live API validation against 5 real tickers

## Conventions

- Python 3.12, async throughout, uv package manager
- SQLAlchemy 2.0 mapped_column style, all DB operations use `AsyncSession`
- Pydantic v2 with `model_config = {"from_attributes": True}`
- Bulk upserts via `INSERT ... ON CONFLICT` (PostgreSQL dialect)
- All bulk INSERTs batched at 1000-5000 rows (asyncpg 32767 param limit)
- In-batch dedup before INSERT to avoid "cannot affect row a second time" errors
- `{identifier}` in API routes auto-resolves: numeric = CIK, otherwise = ticker
- Naive UTC datetimes via `datetime.now(UTC).replace(tzinfo=None)` — `_utcnow()` helpers
- Ruff for linting/formatting, B008 suppressed in API files (Depends pattern)
- NLP models use `Any` types to avoid mypy issues with transformers/keybert stubs
- LLM client is lazy-loaded singleton (same pattern as NLP), raises `LLMUnavailableError` if no API key
- Alert evaluation runs post-sync in try/except — failures never break ingestion
- EventBus is in-process asyncio pub/sub (no Redis), 30s heartbeat, 10min timeout

## Data Sources

### SEC EDGAR
- Rate limit: 8 req/s (below 10/s hard limit)
- User-Agent: `AtlasIntel rajahh7865@gmail.com` (required by SEC)
- Endpoints: `sec.gov/files/company_tickers.json`, `data.sec.gov/submissions/`, `data.sec.gov/api/xbrl/companyfacts/`
- 8-K events extracted from submissions data (filtered by form type, items parsed from comma-separated item numbers)
- Incremental sync: submissions every 24h, facts every 7d (unless `--force`)
- Ticker dedup: keep first CIK occurrence (SEC orders by market cap, primary ticker first)

### Financial Modeling Prep (FMP)
- API key required (set `FMP_API_KEY` in `.env`)
- Rate limit: 5 req/s (configurable)
- Stable API (`/stable/` base URL) — all endpoints use `?symbol=` query params
- Transcript sync: last 3 years of quarters, freshness check 24h
- Market data: historical prices (incremental, 24h freshness), company profiles (7d), key metrics + ratios (7d)
- Metrics fetched from two endpoints (`key-metrics` + `ratios`) and merged by date
- Alt data: news (6h), insider trades (24h), analyst estimates (7d), analyst grades (24h), price targets (24h), institutional holdings (30d)
- Alt data endpoints: `news/stock`, `insider-trading`, `analyst-estimates`, `grades`, `price-target-consensus`, `institutional-ownership/symbol`
- Congress trading: `senate-trading`, `house-disclosure` (tries `/stable/` then `/api/v4/` fallback, requires paid plan)
- Free tier: 250 calls/day — alt data sync uses ~7 calls/company (~35 companies/day max)

### FRED (Federal Reserve Economic Data)
- API key required (set `FRED_API_KEY` in `.env`)
- Rate limit: 100 req/min (configurable)
- Endpoint: `api.stlouisfed.org/fred/series/observations`
- Default series: GDP, UNRATE, DFF, DGS10, CPIAUCSL, HOUST, INDPRO
- Global data (no company_id) — freshness checked via MAX(observation_date) per series
- ON CONFLICT DO UPDATE (values may be revised)

### Anthropic Claude (LLM)
- API key required (set `ANTHROPIC_API_KEY` in `.env`)
- Default model: `claude-sonnet-4-20250514` (configurable via `LLM_MODEL`)
- Max tokens: 4096 (configurable via `LLM_MAX_TOKENS`)
- Report cache TTL: 3600s (configurable via `LLM_REPORT_CACHE_TTL`)
- Lazy-loaded `AsyncAnthropic` singleton. Graceful 503 when unavailable.
- Tool-use loop for NL queries: max 5 iterations, 10 tools mapped to existing services

### USPTO PatentsView
- API key required (set `PATENT_API_KEY` in `.env`, sent as `X-Api-Key` header)
- Rate limit: 40 req/min (configurable, below 45/min limit)
- Endpoint: `search.patentsview.org/api/v1/patent/`
- Searches by assignee organization name (fuzzy company name match)
- Freshness: 30d. Skips financial sector companies. ON CONFLICT DO NOTHING
- Note: PatentsView has temporarily suspended new API key grants

## Database

- PostgreSQL 16 with `pg_trgm` extension (fuzzy company name search)
- `financial_facts` uses tall/EAV design — one row per XBRL data point
- Facts dedup key: `(company_id, taxonomy, concept, unit, period_end, period_start, accession_number)`
- Transcript dedup key: `(company_id, quarter, year)`
- Stock prices dedup key: `(company_id, price_date)` — BigInteger PK for high row volume
- Market metrics dedup key: `(company_id, period, period_date)` — period is "TTM" or "annual"
- Company profile columns stored directly on companies table (no separate table)
- Cascade deletes: transcript -> sections -> sentiments; transcript -> keywords
- Cascade deletes: company -> stock_prices, company -> market_metrics
- News articles dedup key: `(company_id, url)` — BigInteger PK, ON CONFLICT DO UPDATE
- Insider trades dedup key: `(company_id, filing_date, reporting_cik, transaction_type, securities_transacted)` — ON CONFLICT DO NOTHING
- Analyst estimates dedup key: `(company_id, period, estimate_date)` — ON CONFLICT DO UPDATE
- Analyst grades dedup key: `(company_id, grade_date, grading_company, new_grade)` — ON CONFLICT DO NOTHING
- Price target: single consensus row per company `(company_id)` — ON CONFLICT DO UPDATE
- Institutional holdings dedup key: `(company_id, holder, date_reported)` — ON CONFLICT DO NOTHING
- Macro indicators dedup key: `(series_id, observation_date)` — no company FK, ON CONFLICT DO UPDATE
- Material events dedup key: `(company_id, accession_number, item_number)` — ON CONFLICT DO NOTHING
- Patents dedup key: `(company_id, patent_number)` — ON CONFLICT DO NOTHING
- Congress trades dedup key: `(company_id, representative, transaction_date, transaction_type)` — ON CONFLICT DO NOTHING
- Alert rules: Integer PK, nullable company FK (null = global rule), JSON conditions, cooldown_minutes, trigger_count
- Alert events: BigInteger PK, rule FK, severity (info/warning/critical), acknowledged flag, JSON data payload
- Alert rules indexes: `(company_id, enabled)`, `(rule_type)`
- Alert events indexes: `(company_id, triggered_at)`, `(rule_id, triggered_at)`, `(acknowledged, triggered_at)`

## NLP Pipeline

- FinBERT (`ProsusAI/finbert`): sentence-level sentiment, aggregated to section and transcript level
- KeyBERT (`all-MiniLM-L6-v2`): keyword extraction with MMR diversity on full transcript text
- Processing happens on ingestion (not async/deferred)
- Models lazy-loaded as singletons, use `model.train(False)` not `.eval()` (avoids security hook)

## Fusion Signals

Multi-source composite intelligence signals computed read-side (no new tables). Each signal uses weighted components with graceful degradation — missing components get weight 0, remaining weights renormalized. Confidence = fraction of components with data.

- **Sentiment** (`/signals/sentiment`): transcript sentiment (0.35) + insider ratio (0.25) + analyst grades (0.25) + news volume (0.15)
- **Growth** (`/signals/growth`): revenue trajectory (0.5) + innovation velocity (0.3) + macro tailwind (0.2)
- **Risk** (`/signals/risk`): insider selling (0.3) + 8-K event risk (0.25) + negative sentiment (0.25) + macro headwinds (0.2)
- **Smart Money** (`/signals/smart-money`): institutional flow (0.4) + insider conviction (0.35) + congress flow (0.25)

## Analytics & Modeling (Layer 6)

All computation is read-side from existing data — no new tables, no new dependencies.

### Valuation (`/companies/{id}/valuation`)
- **DCF** (`/valuation/dcf`): 3 scenarios (bear/base/bull) using XBRL cash flow data. WACC = risk_free + beta × ERP. Gordon growth terminal value. Graceful degradation with `data_quality` field.
- **Relative** (`/valuation/relative`): Company multiples vs sector peers (PE, PB, EV/EBITDA, P/S, EV/S). DISTINCT ON subquery for latest TTM per peer. Premium/discount % per multiple + composite assessment.
- **Analyst** (`/valuation/analyst`): Price target consensus vs current price. Upside %, downside risk %, upside potential %.
- **Full** (`/valuation`): Combines all 3 models with majority-vote composite assessment. Cached 30min.

### Anomaly Detection (`/companies/{id}/anomalies`)
- **Price** (`/anomalies/price`): Volume spikes (vs 20d rolling avg), return spikes (z-score), volatility breakouts (5d vs 30d realized vol).
- **Fundamental** (`/anomalies/fundamental`): Latest TTM metric values vs last 8 historical TTM records. Flags PE spike, margin compression, leverage surge.
- **Activity** (`/anomalies/activity`): Insider trade surge (30d count vs 90d avg), 8-K filing frequency, analyst grade clustering.
- **Sector** (`/anomalies/sector`): Company metrics vs sector distribution. Z-score + percentile rank per metric.
- **All** (`/anomalies`): Combined. Cached 10min. Query params: `lookback_days` (7-365, default 90), `threshold` (1.0-5.0, default 2.0).

### Screening (`/screen`)
- **POST /screen**: Complex multi-criteria filtering via request body. Metric filters (gt/gte/lt/lte/eq/between), company filters (sector/industry/country/exchange), signal filters (post-filter via fusion signals). Max 200 results.
- **GET /screen**: Simple filters via query params (`pe_lt`, `roe_gt`, `sector`, `sort_by`, etc.)
- **GET /screen/stats**: Total companies, companies with metrics, sector/industry lists.
- Filter-then-score strategy: SQL filters first, then compute signals only for filtered set.

## LLM Intelligence (Layer 7)

### Report Types
- **Comprehensive**: Full deep-dive — profile, valuation, signals, anomalies, financials, alt data, macro context
- **Quick**: 1-2 paragraph executive summary
- **Comparison**: Side-by-side analysis of 2-5 companies
- **Sector**: Sector-level aggregation from screening data

### Context Gathering (`llm/context.py`)
- `gather_company_context()` — parallel-fetches from all services into `CompanyContext` dataclass
- `gather_comparison_context()` — gathers contexts for multiple companies via `asyncio.gather()`
- `gather_sector_context()` — screening + aggregation for sector overview
- `_safe_call()` wrapper — exceptions return None, enabling graceful degradation

### NL Query Tools (`llm/tools.py`)
10 tools mapped to existing services: `get_company`, `screen_companies`, `get_signals`, `get_valuation`, `get_anomalies`, `get_financials`, `get_prices`, `get_news`, `get_insider`, `get_macro`

### Service Layer
- `report_service.py` — `generate_company_report()`, `stream_company_report()`, `generate_comparison_report()`, `generate_sector_report()` — cached via TTLCache
- `query_service.py` — `process_natural_language_query()` with tool-use loop (max 5 iterations), `stream_natural_language_query()`

## Real-time Monitoring (Layer 8)

### Alert Rule Types
- `price_threshold` — latest StockPrice field vs operator/value
- `volume_spike` — latest volume vs 20d rolling average × multiplier
- `signal_drop` — fusion signal score below threshold
- `anomaly_detected` — anomaly count > 0
- `freshness_stale` — `*_synced_at` timestamp older than threshold hours
- `metric_threshold` — latest MarketMetric field vs operator/value

### Alert Service (`services/alert_service.py`)
- Full CRUD for rules and events
- `evaluate_rule()` dispatches by rule_type, enforces cooldown
- `check_alerts_for_company()` / `check_all_alerts()` for batch evaluation
- `acknowledge_event()` / `acknowledge_all_events()` for event management

### EventBus (`services/event_bus.py`)
- In-memory asyncio.Queue pub/sub, no external dependencies
- `subscribe()` / `unsubscribe()` / `publish()` / `stream()` (SSE format)
- 30s keepalive heartbeats, 10min connection timeout, cleanup on disconnect

### Dashboard (`services/dashboard_service.py`)
- `get_market_overview()` — total companies, sector breakdown (count, avg PE, avg ROE, total market cap)
- `get_top_movers()` — gainers, losers, volume leaders by price change %
- `get_alert_summary()` — total/active rules, recent events, 24h/7d event counts
- `get_full_dashboard_cached()` — combined, cached 5min

### Post-Sync Hooks
- `_post_sync_alert_check()` in `pipeline.py` — called after each per-ticker sync
- Evaluates company-specific + global rules, publishes events to EventBus
- Wrapped in try/except — alert failures never break sync

## Testing

- Unit tests: pure logic, no DB/HTTP (transforms, NLP aggregation, fusion, valuation DCF, anomaly z-scores, screening filters, LLM context/tools, alert evaluation, event bus)
- Integration tests: real PostgreSQL + `respx` mocked APIs + `unittest.mock.patch` for NLP
- API tests: FastAPI `AsyncClient` with ASGI transport
- Edge case tests: FMP 429/500, empty transcripts, 512-token overflow, amended filing dedup, missing fields
- LLM tests: mock `anthropic.AsyncAnthropic` via `unittest.mock.patch`, test tool routing, context gathering, graceful degradation
- Alert tests: unit test each rule_type evaluation, cooldown logic, EventBus pub/sub, integration test post-sync hooks
- Fixtures: truncated real SEC/FMP/FRED/USPTO responses in `tests/fixtures/`
- Test DB: `atlas_intel_test` (separate from dev)

## Known Bugs Fixed (from live validation)

These were invisible in fixture-based tests and only surfaced against real API data:

1. **Ticker dedup crash**: SEC `company_tickers.json` has duplicate CIKs (JPM + 8 preferred/ETF tickers all under CIK 19617). Fix: dedup by CIK before INSERT, keep first occurrence.
2. **Wrong primary ticker**: Dedup kept last entry per CIK (ETF ticker `VYLD` overwrote `JPM`). Fix: `setdefault()` instead of overwrite.
3. **asyncpg param limit**: JPMorgan has 23,165 filings. Single INSERT exceeds 32,767 param limit. Fix: batch at 1000 rows.
4. **Amended filing crash**: SEC returns original + amendment with same accession number. Fix: dedup by accession_number before INSERT.
5. **datetime.utcnow() deprecation**: Replaced with `datetime.now(UTC).replace(tzinfo=None)` across all sync modules.
6. **SEC EFTS wrong endpoint**: `search-index` endpoint doesn't search structured CIK fields. Fix: use submissions API which already has 8-K form/items data.
7. **PatentsView 403**: API now requires `X-Api-Key` header. Fix: added `PATENT_API_KEY` config + graceful skip when unconfigured.
8. **FMP Congress 403/404**: Senate/house trading endpoints require paid plan. Fix: try `/stable/` then `/api/v4/` fallback, handle 403 gracefully.
9. **Pipeline crash on partial failure**: One failed source killed the whole ticker sync. Fix: per-source try/except so partial results are returned.

## Migrations

- 001: Initial schema (companies, filings, financial_facts)
- 002: Nulls not distinct dedup
- 003: Transcript tables (earnings_transcripts, transcript_sections, sentiment_analysis, keyword_extraction)
- 004: Market data (stock_prices, market_metrics, company profile columns)
- 005: Alternative data (news_articles, insider_trades, analyst_estimates, analyst_grades, price_targets, institutional_holdings)
- 006: Sync job tables (sync_jobs, sync_job_runs)
- 007: Macro indicators (macro_indicators — no company FK, global data)
- 008: Material events (material_events + material_events_synced_at on companies)
- 009: Patents (patents + patents_synced_at on companies)
- 010: Congress trades (congress_trades + congress_trades_synced_at on companies)
- 011: Alert tables (alert_rules + alert_events with indexes)

## Roadmap

| Layer | Status | Description |
|-------|--------|-------------|
| 1. SEC EDGAR foundation | Done | Filing metadata, XBRL financial facts, company data |
| 2. NLP layer | Done | Earnings call transcripts, FinBERT sentiment, KeyBERT keywords |
| 3. Market data | Done | OHLCV prices, company profiles, key metrics/ratios, price analytics |
| 4. Alternative data | Done | News, insider trading, analyst estimates/grades, price targets, institutional holdings |
| 5. Expanded data & fusion | Done | FRED macro, 8-K events, patents, congress trades, composite signals |
| 6. Analytics/modeling | Done | DCF/relative/analyst valuation, multi-criteria screening, anomaly detection |
| 7. LLM intelligence | Done | Anthropic Claude report generation (4 types), natural language queries with tool use, SSE streaming |
| 8. Real-time monitoring | Done | Alert rules (6 types), alert events, EventBus SSE streaming, aggregated dashboards, post-sync hooks |
