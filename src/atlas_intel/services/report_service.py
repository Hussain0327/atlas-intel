"""LLM-powered report generation service."""

import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.cache import read_cache
from atlas_intel.config import settings
from atlas_intel.llm.client import LLMUnavailableError, get_provider
from atlas_intel.llm.context import (
    context_to_json,
    gather_company_context,
    gather_comparison_context,
    gather_sector_context,
)
from atlas_intel.llm.prompts import (
    COMPARISON_REPORT_PROMPT,
    COMPREHENSIVE_REPORT_PROMPT,
    QUICK_REPORT_PROMPT,
    SECTOR_REPORT_PROMPT,
    SYSTEM_PROMPT,
)
from atlas_intel.schemas.report import ReportResponse

logger = logging.getLogger(__name__)

REPORT_CACHE_TTL = settings.llm_report_cache_ttl


async def generate_company_report(
    session: AsyncSession,
    company_id: int,
    ticker: str,
    name: str,
    report_type: str = "comprehensive",
) -> ReportResponse:
    """Generate an LLM-powered company report."""
    cache_key = f"report:{ticker}:{report_type}"
    cached = await read_cache.get(cache_key)
    if cached is not None:
        return cached  # type: ignore[return-value]

    ctx = await gather_company_context(session, company_id, ticker)
    context_json = context_to_json(ctx)

    if report_type == "quick":
        prompt = QUICK_REPORT_PROMPT.format(ticker=ticker, name=name, context=context_json)
    else:
        prompt = COMPREHENSIVE_REPORT_PROMPT.format(ticker=ticker, name=name, context=context_json)

    provider = get_provider()
    response = await provider.generate(
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=settings.llm_max_tokens,
    )

    content = response.text
    if not content.strip():
        raise LLMUnavailableError("LLM returned empty response")

    result = ReportResponse(
        ticker=ticker,
        report_type=report_type,
        content=content,
        data_context={"signals": ctx.signals, "valuation": ctx.valuation},
        generated_at=datetime.now(UTC).replace(tzinfo=None),
    )

    await read_cache.set(cache_key, result, REPORT_CACHE_TTL)
    return result


async def stream_company_report(
    session: AsyncSession,
    company_id: int,
    ticker: str,
    name: str,
    report_type: str = "comprehensive",
) -> AsyncIterator[str]:
    """Stream an LLM-powered company report via SSE."""
    ctx = await gather_company_context(session, company_id, ticker)
    context_json = context_to_json(ctx)

    if report_type == "quick":
        prompt = QUICK_REPORT_PROMPT.format(ticker=ticker, name=name, context=context_json)
    else:
        prompt = COMPREHENSIVE_REPORT_PROMPT.format(ticker=ticker, name=name, context=context_json)

    provider = get_provider()
    async for text in provider.stream(
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=settings.llm_max_tokens,
    ):
        yield f"data: {text}\n\n"
    yield "data: [DONE]\n\n"


async def generate_comparison_report(
    session: AsyncSession,
    company_infos: list[tuple[int, str, str]],
) -> ReportResponse:
    """Generate a comparison report for multiple companies."""
    tickers = [t for _, t, _ in company_infos]
    cache_key = f"report:comparison:{','.join(sorted(tickers))}"
    cached = await read_cache.get(cache_key)
    if cached is not None:
        return cached  # type: ignore[return-value]

    id_ticker_pairs = [(cid, ticker) for cid, ticker, _ in company_infos]
    contexts = await gather_comparison_context(session, id_ticker_pairs)
    context_json = context_to_json(contexts)
    companies_str = ", ".join(f"{t} ({n})" for _, t, n in company_infos)

    prompt = COMPARISON_REPORT_PROMPT.format(companies=companies_str, context=context_json)

    provider = get_provider()
    response = await provider.generate(
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=settings.llm_max_tokens,
    )

    content = response.text

    result = ReportResponse(
        report_type="comparison",
        content=content,
        data_context={"tickers": tickers},
        generated_at=datetime.now(UTC).replace(tzinfo=None),
    )

    await read_cache.set(cache_key, result, REPORT_CACHE_TTL)
    return result


async def generate_sector_report(
    session: AsyncSession,
    sector: str,
) -> ReportResponse:
    """Generate a sector analysis report."""
    cache_key = f"report:sector:{sector}"
    cached = await read_cache.get(cache_key)
    if cached is not None:
        return cached  # type: ignore[return-value]

    ctx = await gather_sector_context(session, sector)
    context_json = context_to_json(ctx)

    prompt = SECTOR_REPORT_PROMPT.format(sector=sector, context=context_json)

    provider = get_provider()
    response = await provider.generate(
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=settings.llm_max_tokens,
    )

    content = response.text

    result = ReportResponse(
        report_type="sector",
        content=content,
        data_context={"sector": sector, "company_count": len(ctx.companies)},
        generated_at=datetime.now(UTC).replace(tzinfo=None),
    )

    await read_cache.set(cache_key, result, REPORT_CACHE_TTL)
    return result
