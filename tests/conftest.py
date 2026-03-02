"""Test fixtures: DB setup, mock SEC API, factory helpers."""

import json
from pathlib import Path

import pytest
import respx
from httpx import Response
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from atlas_intel.models import Base

FIXTURES_DIR = Path(__file__).parent / "fixtures"

# Use a separate test database
TEST_DATABASE_URL = "postgresql+asyncpg://atlas:atlas@localhost:5432/atlas_intel_test"


@pytest.fixture
async def engine():
    """Function-scoped engine — each test gets its own pool on the correct event loop."""
    eng = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture
async def _db_cleanup(engine):
    """Delete all rows after each DB-using test for isolation."""
    yield
    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())


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
