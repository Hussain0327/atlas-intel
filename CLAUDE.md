# Atlas Intel

Company & Market Intelligence Engine. Layers 1-4 complete (SEC EDGAR + NLP transcripts + Market Data + Alternative Data).

## Key Commands

```bash
uv sync                                    # Install deps
docker compose up db -d                    # Start PostgreSQL
uv run alembic upgrade head                # Run migrations
uv run atlas sync --ticker AAPL            # SEC pipeline (filings + facts)
uv run atlas sync-transcripts --ticker AAPL  # Transcript + NLP pipeline
uv run atlas sync-market --ticker AAPL     # Market data (prices + profile + metrics)
uv run atlas sync-alt --ticker AAPL        # Alt data (news, insider, analyst, holdings)
uv run uvicorn atlas_intel.main:app --reload  # Start API
uv run pytest --cov                        # Run tests (251 tests)
uv run ruff check . && uv run ruff format --check .  # Lint
uv run mypy src/atlas_intel                # Type check
APP_ENV=production uv run python scripts/validate_pipeline.py --all  # Live validation
```

## Architecture

- `src/atlas_intel/` — main package
  - `models/` — SQLAlchemy ORM: Company, Filing, FinancialFact, EarningsTranscript, TranscriptSection, SentimentAnalysis, KeywordExtraction, StockPrice, MarketMetric, NewsArticle, InsiderTrade, AnalystEstimate, AnalystGrade, PriceTarget, InstitutionalHolding
  - `ingestion/` — SEC EDGAR + FMP pipelines: rate-limited HTTP clients, ticker/submission/facts/transcript/price/profile/metrics/news/insider/analyst/institutional sync
  - `nlp/` — FinBERT sentiment analysis, KeyBERT keyword extraction (lazy-loaded singletons)
  - `api/` — FastAPI routes under `/api/v1`
  - `services/` — business logic between API and DB
  - `schemas/` — Pydantic request/response models
  - `cli.py` — Typer CLI (`atlas sync`, `atlas sync-tickers`, `atlas sync-transcripts`, `atlas sync-market`, `atlas sync-alt`)
- `alembic/` — async database migrations (001-005)
- `tests/` — unit (transforms, NLP), integration (DB + mocked APIs), API (TestClient), edge cases
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

## Data Sources

### SEC EDGAR
- Rate limit: 8 req/s (below 10/s hard limit)
- User-Agent: `AtlasIntel rajahh7865@gmail.com` (required by SEC)
- Endpoints: `sec.gov/files/company_tickers.json`, `data.sec.gov/submissions/`, `data.sec.gov/api/xbrl/companyfacts/`
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
- Free tier: 250 calls/day — alt data sync uses ~7 calls/company (~35 companies/day max)

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

## NLP Pipeline

- FinBERT (`ProsusAI/finbert`): sentence-level sentiment, aggregated to section and transcript level
- KeyBERT (`all-MiniLM-L6-v2`): keyword extraction with MMR diversity on full transcript text
- Processing happens on ingestion (not async/deferred)
- Models lazy-loaded as singletons, use `model.train(False)` not `.eval()` (avoids security hook)

## Testing

- Unit tests: pure logic, no DB/HTTP (transforms, NLP aggregation, edge cases)
- Integration tests: real PostgreSQL + `respx` mocked APIs + `unittest.mock.patch` for NLP
- API tests: FastAPI `AsyncClient` with ASGI transport
- Edge case tests: FMP 429/500, empty transcripts, 512-token overflow, amended filing dedup, missing fields
- Fixtures: truncated real SEC/FMP responses in `tests/fixtures/`
- Test DB: `atlas_intel_test` (separate from dev)

## Known Bugs Fixed (from live validation)

These were invisible in fixture-based tests and only surfaced against real API data:

1. **Ticker dedup crash**: SEC `company_tickers.json` has duplicate CIKs (JPM + 8 preferred/ETF tickers all under CIK 19617). Fix: dedup by CIK before INSERT, keep first occurrence.
2. **Wrong primary ticker**: Dedup kept last entry per CIK (ETF ticker `VYLD` overwrote `JPM`). Fix: `setdefault()` instead of overwrite.
3. **asyncpg param limit**: JPMorgan has 23,165 filings. Single INSERT exceeds 32,767 param limit. Fix: batch at 1000 rows.
4. **Amended filing crash**: SEC returns original + amendment with same accession number. Fix: dedup by accession_number before INSERT.
5. **datetime.utcnow() deprecation**: Replaced with `datetime.now(UTC).replace(tzinfo=None)` across all sync modules.

## Roadmap

| Layer | Status | Description |
|-------|--------|-------------|
| 1. SEC EDGAR foundation | Done | Filing metadata, XBRL financial facts, company data |
| 2. NLP layer | Done | Earnings call transcripts, FinBERT sentiment, KeyBERT keywords |
| 3. Market data | Done | OHLCV prices, company profiles, key metrics/ratios, price analytics |
| 4. Alternative data | Done | News, insider trading, analyst estimates/grades, price targets, institutional holdings |
| 5. Analytics/modeling | Planned | Valuation models, screening, anomaly detection |
| 6. LLM layer | Planned | Report generation, natural language queries |
| 7. Real-time monitoring | Planned | Alerts, dashboards, streaming pipelines |
