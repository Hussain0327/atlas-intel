"""Data gathering for LLM context — pulls from existing services."""

import asyncio
import json
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.schemas.report import CompanyContext, SectorContext

logger = logging.getLogger(__name__)


async def _safe_call(coro: Any, default: Any = None) -> Any:
    """Call an async function, returning default on failure."""
    try:
        return await coro
    except Exception:
        logger.debug("Context fetch failed", exc_info=True)
        return default


async def gather_company_context(
    session: AsyncSession,
    company_id: int,
    ticker: str,
    *,
    include_valuation: bool = True,
    include_signals: bool = True,
    include_anomalies: bool = True,
    include_financials: bool = True,
    include_alt_data: bool = True,
) -> CompanyContext:
    """Parallel-fetch data from existing services into compact context."""
    from atlas_intel.services.company_service import get_company_detail

    detail = await _safe_call(get_company_detail(session, ticker), {})
    if not detail:
        detail = {}

    ctx = CompanyContext(
        ticker=ticker,
        name=detail.get("name", ticker),
        sector=detail.get("sector"),
        industry=detail.get("industry"),
        country=detail.get("country"),
        exchange=detail.get("exchange"),
        ceo=detail.get("ceo"),
        employees=detail.get("full_time_employees"),
        description=detail.get("description"),
    )

    tasks: dict[str, Any] = {}

    if include_valuation:
        from atlas_intel.services.valuation_service import compute_full_valuation_cached

        tasks["valuation"] = _safe_call(
            compute_full_valuation_cached(session, company_id, ticker), None
        )

    if include_signals:
        from atlas_intel.services.fusion_service import (
            compute_growth_signal,
            compute_risk_signal,
            compute_sentiment_signal,
            compute_smart_money_signal,
        )

        tasks["sentiment"] = _safe_call(compute_sentiment_signal(session, company_id), None)
        tasks["growth"] = _safe_call(compute_growth_signal(session, company_id), None)
        tasks["risk"] = _safe_call(compute_risk_signal(session, company_id), None)
        tasks["smart_money"] = _safe_call(compute_smart_money_signal(session, company_id), None)

    if include_anomalies:
        from atlas_intel.services.anomaly_service import detect_all_anomalies_cached

        tasks["anomalies"] = _safe_call(
            detect_all_anomalies_cached(session, company_id, ticker), None
        )

    if include_financials:
        from atlas_intel.services.financial_service import get_financial_summary
        from atlas_intel.services.price_service import get_price_analytics_cached

        tasks["financials"] = _safe_call(get_financial_summary(session, company_id), [])
        tasks["price_analytics"] = _safe_call(
            get_price_analytics_cached(session, company_id, ticker), {}
        )

    if include_alt_data:
        from atlas_intel.services.insider_service import get_insider_sentiment
        from atlas_intel.services.macro_service import get_macro_summary
        from atlas_intel.services.news_service import get_news
        from atlas_intel.services.transcript_service import get_sentiment_trend

        tasks["sentiment_trend"] = _safe_call(get_sentiment_trend(session, company_id), [])
        tasks["news_raw"] = _safe_call(get_news(session, company_id, limit=10), ([], 0))
        tasks["insider_sentiment"] = _safe_call(
            get_insider_sentiment(session, company_id, ticker), {}
        )
        tasks["macro_summary"] = _safe_call(get_macro_summary(session), {})

    if tasks:
        keys = list(tasks.keys())
        results = await asyncio.gather(*tasks.values())
        resolved = dict(zip(keys, results, strict=True))

        if include_valuation and resolved.get("valuation"):
            ctx.valuation = resolved["valuation"].model_dump()

        if include_signals:
            signals: dict[str, Any] = {}
            for key in ("sentiment", "growth", "risk", "smart_money"):
                val = resolved.get(key)
                if val:
                    signals[key] = val.model_dump()
            ctx.signals = signals

        if include_anomalies and resolved.get("anomalies"):
            ctx.anomalies = resolved["anomalies"].model_dump()

        if include_financials:
            ctx.financials = resolved.get("financials") or []
            ctx.price_analytics = resolved.get("price_analytics") or {}

        if include_alt_data:
            ctx.sentiment_trend = resolved.get("sentiment_trend") or []
            news_raw = resolved.get("news_raw", ([], 0))
            if news_raw and isinstance(news_raw, tuple):
                articles, _ = news_raw
                ctx.recent_news = [
                    {
                        "title": getattr(a, "title", ""),
                        "published_at": str(getattr(a, "published_at", "")),
                        "source": getattr(a, "source_name", ""),
                    }
                    for a in (articles or [])
                ]
            ctx.insider_sentiment = resolved.get("insider_sentiment") or {}
            ctx.macro_summary = resolved.get("macro_summary") or {}

    return ctx


async def gather_comparison_context(
    session: AsyncSession,
    company_infos: list[tuple[int, str]],
) -> list[CompanyContext]:
    """Gather context for multiple companies in parallel."""
    tasks = [
        gather_company_context(
            session, cid, ticker, include_alt_data=False, include_anomalies=False
        )
        for cid, ticker in company_infos
    ]
    return list(await asyncio.gather(*tasks))


async def gather_sector_context(
    session: AsyncSession,
    sector: str,
) -> SectorContext:
    """Gather sector-level context via screening service."""
    from atlas_intel.schemas.screening import ScreenFilter
    from atlas_intel.services.screening_service import get_screening_stats, screen_companies

    stats = await _safe_call(get_screening_stats(session), None)
    sector_filter = [ScreenFilter(field="sector", op="eq", value=sector)]
    screen_result = await _safe_call(
        screen_companies(
            session,
            company_filters=sector_filter,
            sort_by="market_cap",
            sort_order="desc",
            limit=20,
        ),
        None,
    )

    companies: list[dict[str, Any]] = []
    if screen_result:
        companies = [item.model_dump() for item in screen_result.items]

    return SectorContext(
        sector=sector,
        companies=companies,
        stats=stats.model_dump() if stats else {},
    )


def context_to_json(ctx: CompanyContext | SectorContext | list[CompanyContext]) -> str:
    """Serialize context to compact JSON for LLM consumption."""
    if isinstance(ctx, list):
        return json.dumps([c.model_dump() for c in ctx], default=str, indent=1)
    return json.dumps(ctx.model_dump(), default=str, indent=1)
