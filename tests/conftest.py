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


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
def engine():
    return create_async_engine(TEST_DATABASE_URL, echo=False)


@pytest.fixture(scope="session")
async def setup_db(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db_connection(engine, setup_db):
    """One connection + transaction per test. Rolled back after the test.

    When a Session is bound to a connection that already has a transaction,
    session.commit() just flushes without actually committing the connection's
    transaction (SQLAlchemy "join existing transaction" behavior). This means
    all data is visible within the test but rolled back at the end.
    """
    async with engine.connect() as conn:
        txn = await conn.begin()
        yield conn
        await txn.rollback()


@pytest.fixture
async def session(db_connection):
    """AsyncSession bound to the test's isolated connection."""
    async_sess = async_sessionmaker(bind=db_connection, expire_on_commit=False)
    async with async_sess() as s:
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


# FastAPI test client — shares the same connection as `session` fixture
@pytest.fixture
async def client(db_connection):
    from httpx import ASGITransport, AsyncClient

    from atlas_intel.database import get_session
    from atlas_intel.main import create_app

    _app = create_app()

    async_sess = async_sessionmaker(bind=db_connection, expire_on_commit=False)

    async def override_get_session():
        async with async_sess() as s:
            yield s

    _app.dependency_overrides[get_session] = override_get_session

    transport = ASGITransport(app=_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
