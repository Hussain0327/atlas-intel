"""Test fixtures: DB setup, mock SEC API, factory helpers."""

import json
from pathlib import Path

import pytest
import respx
from httpx import Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from atlas_intel.models import Base

FIXTURES_DIR = Path(__file__).parent / "fixtures"

# Use a separate test database
TEST_DATABASE_URL = "postgresql+asyncpg://atlas:atlas@localhost:5432/atlas_intel_test"


@pytest.fixture
async def engine():
    """Function-scoped engine — each test gets its own pool on the correct event loop."""
    eng = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
    async with eng.begin() as conn:
        # Reset the whole schema so tests do not inherit state from tables outside Base.metadata.
        await conn.exec_driver_sql("DROP SCHEMA IF EXISTS public CASCADE")
        await conn.exec_driver_sql("CREATE SCHEMA public")
        await conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture
async def _db_cleanup(engine):
    """Delete all rows after each DB-using test for isolation."""
    yield
    async with engine.begin() as conn:
        table_names = [table.name for table in reversed(Base.metadata.sorted_tables)]
        if not table_names:
            return
        quoted = ", ".join(f'"{name}"' for name in table_names)
        await conn.execute(text(f"TRUNCATE TABLE {quoted} RESTART IDENTITY CASCADE"))


@pytest.fixture
async def session(engine, _db_cleanup):
    """AsyncSession with its own connection from the pool."""
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as s:
        yield s


@pytest.fixture
def mock_sec_api():
    """Mock SEC EDGAR API responses using respx."""
    with respx.mock(assert_all_called=False) as mock:
        # Company tickers
        tickers_data = json.loads((FIXTURES_DIR / "company_tickers.json").read_text())
        mock.get("https://www.sec.gov/files/company_tickers.json").mock(
            return_value=Response(200, json=tickers_data)
        )

        # Submissions for AAPL
        submissions_data = json.loads((FIXTURES_DIR / "submissions_aapl.json").read_text())
        mock.get("https://data.sec.gov/submissions/CIK0000320193.json").mock(
            return_value=Response(200, json=submissions_data)
        )

        # Company facts for AAPL
        facts_data = json.loads((FIXTURES_DIR / "companyfacts_aapl.json").read_text())
        mock.get("https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json").mock(
            return_value=Response(200, json=facts_data)
        )

        yield mock


@pytest.fixture
def tickers_json():
    return json.loads((FIXTURES_DIR / "company_tickers.json").read_text())


@pytest.fixture
def submissions_json():
    return json.loads((FIXTURES_DIR / "submissions_aapl.json").read_text())


@pytest.fixture
def companyfacts_json():
    return json.loads((FIXTURES_DIR / "companyfacts_aapl.json").read_text())


@pytest.fixture
def fmp_transcript_json():
    return json.loads((FIXTURES_DIR / "fmp_transcript_aapl.json").read_text())


@pytest.fixture
def fmp_prices_json():
    return json.loads((FIXTURES_DIR / "fmp_historical_prices.json").read_text())


@pytest.fixture
def fmp_profile_json():
    return json.loads((FIXTURES_DIR / "fmp_profile_aapl.json").read_text())


@pytest.fixture
def fmp_metrics_json():
    return json.loads((FIXTURES_DIR / "fmp_key_metrics_aapl.json").read_text())


@pytest.fixture
def fmp_news_json():
    return json.loads((FIXTURES_DIR / "fmp_news_aapl.json").read_text())


@pytest.fixture
def fmp_insider_trading_json():
    return json.loads((FIXTURES_DIR / "fmp_insider_trading_aapl.json").read_text())


@pytest.fixture
def fmp_analyst_estimates_json():
    return json.loads((FIXTURES_DIR / "fmp_analyst_estimates_aapl.json").read_text())


@pytest.fixture
def fmp_analyst_grades_json():
    return json.loads((FIXTURES_DIR / "fmp_analyst_grades_aapl.json").read_text())


@pytest.fixture
def fmp_price_target_json():
    return json.loads((FIXTURES_DIR / "fmp_price_target_aapl.json").read_text())


@pytest.fixture
def fmp_institutional_json():
    return json.loads((FIXTURES_DIR / "fmp_institutional_aapl.json").read_text())


@pytest.fixture
def mock_fmp_alt_data_api(
    fmp_news_json,
    fmp_insider_trading_json,
    fmp_analyst_estimates_json,
    fmp_analyst_grades_json,
    fmp_price_target_json,
    fmp_institutional_json,
):
    """Mock FMP API responses for alternative data endpoints."""
    with respx.mock(assert_all_called=False) as mock:
        mock.get(url__startswith="https://financialmodelingprep.com/stable/news/stock").mock(
            return_value=Response(200, json=fmp_news_json)
        )

        mock.get(url__startswith="https://financialmodelingprep.com/stable/insider-trading").mock(
            return_value=Response(200, json=fmp_insider_trading_json)
        )

        mock.get(url__startswith="https://financialmodelingprep.com/stable/analyst-estimates").mock(
            return_value=Response(200, json=fmp_analyst_estimates_json)
        )

        mock.get(url__startswith="https://financialmodelingprep.com/stable/grades").mock(
            return_value=Response(200, json=fmp_analyst_grades_json)
        )

        mock.get(
            url__startswith="https://financialmodelingprep.com/stable/price-target-consensus"
        ).mock(return_value=Response(200, json=fmp_price_target_json))

        mock.get(
            url__startswith="https://financialmodelingprep.com/stable/institutional-ownership"
        ).mock(return_value=Response(200, json=fmp_institutional_json))

        yield mock


@pytest.fixture
def mock_fmp_api(fmp_transcript_json):
    """Mock FMP API responses using respx."""
    available_list = [
        {"symbol": "AAPL", "quarter": 1, "year": 2024, "date": "2024-01-25 17:00:00"},
        {"symbol": "AAPL", "quarter": 4, "year": 2023, "date": "2023-10-26 17:00:00"},
    ]

    def _transcript_side_effect(request):
        if "quarter" in dict(request.url.params):
            return Response(200, json=fmp_transcript_json)
        return Response(200, json=available_list)

    with respx.mock(assert_all_called=False) as mock:
        mock.get(
            url__startswith="https://financialmodelingprep.com/stable/earning-call-transcript"
        ).mock(side_effect=_transcript_side_effect)

        yield mock


@pytest.fixture
def mock_fmp_market_api(fmp_prices_json, fmp_profile_json, fmp_metrics_json):
    """Mock FMP API responses for market data endpoints (stable API)."""
    ttm_data = [
        {
            "dividendYieldTTM": 0.0050,
            "peRatioTTM": 30.82,
            "pbRatioTTM": 47.89,
            "marketCapTTM": 2987123456789,
            "enterpriseValueTTM": 3091234567890,
            "revenuePerShareTTM": 24.32,
            "netIncomePerShareTTM": 6.13,
            "bookValuePerShareTTM": 3.95,
            "freeCashFlowPerShareTTM": 6.73,
            "roeTTM": 1.51,
            "roicTTM": 0.57,
            "currentRatioTTM": 0.99,
            "debtToEquityTTM": 1.79,
        }
    ]

    with respx.mock(assert_all_called=False) as mock:
        # Historical prices
        mock.get(
            url__startswith="https://financialmodelingprep.com/stable/historical-price-eod/full"
        ).mock(return_value=Response(200, json=fmp_prices_json))

        # Company profile
        mock.get(url__startswith="https://financialmodelingprep.com/stable/profile").mock(
            return_value=Response(200, json=fmp_profile_json)
        )

        # TTM endpoints (must be before non-TTM to avoid prefix collision)
        mock.get(url__startswith="https://financialmodelingprep.com/stable/key-metrics-ttm").mock(
            return_value=Response(200, json=ttm_data)
        )

        mock.get(url__startswith="https://financialmodelingprep.com/stable/ratios-ttm").mock(
            return_value=Response(200, json=ttm_data)
        )

        # Annual endpoints
        mock.get(url__startswith="https://financialmodelingprep.com/stable/key-metrics").mock(
            return_value=Response(200, json=fmp_metrics_json)
        )

        mock.get(url__startswith="https://financialmodelingprep.com/stable/ratios").mock(
            return_value=Response(200, json=fmp_metrics_json)
        )

        yield mock


# FastAPI test client — own connection from pool (no sharing with `session`)
@pytest.fixture
async def client(engine, _db_cleanup):
    from httpx import ASGITransport, AsyncClient

    from atlas_intel.database import get_session
    from atlas_intel.main import create_app

    _app = create_app()

    sm = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_session():
        async with sm() as s:
            yield s

    _app.dependency_overrides[get_session] = override_get_session

    transport = ASGITransport(app=_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
