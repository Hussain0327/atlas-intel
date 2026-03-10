"""Tool definitions for natural language query mode."""

import json
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "get_company",
        "description": (
            "Get company profile (sector, industry, CEO, employees, description) "
            "plus key valuation metrics (PE, PB, ROE, EV/EBITDA, market cap, "
            "debt-to-equity). Use this as the first call for any company question."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "identifier": {
                    "type": "string",
                    "description": "Company ticker (e.g. AAPL) or CIK number",
                }
            },
            "required": ["identifier"],
        },
    },
    {
        "name": "screen_companies",
        "description": (
            "Screen/filter companies by metrics (PE, ROE, market cap, etc.), "
            "sector, industry. Returns matching companies sorted by criteria."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sector": {"type": "string", "description": "Filter by sector"},
                "industry": {"type": "string", "description": "Filter by industry"},
                "pe_lt": {"type": "number", "description": "PE ratio less than"},
                "pe_gt": {"type": "number", "description": "PE ratio greater than"},
                "roe_gt": {"type": "number", "description": "ROE greater than"},
                "market_cap_gt": {"type": "number", "description": "Market cap greater than"},
                "sort_by": {
                    "type": "string",
                    "description": "Sort field (market_cap, pe_ratio, roe, etc.)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results (default 10)",
                    "default": 10,
                },
            },
        },
    },
    {
        "name": "get_signals",
        "description": (
            "Get composite fusion signals (sentiment, growth, risk, smart_money) for a company."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "identifier": {"type": "string", "description": "Company ticker or CIK"}
            },
            "required": ["identifier"],
        },
    },
    {
        "name": "get_valuation",
        "description": (
            "Get full valuation analysis "
            "(DCF, relative multiples, analyst consensus) for a company."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "identifier": {"type": "string", "description": "Company ticker or CIK"}
            },
            "required": ["identifier"],
        },
    },
    {
        "name": "get_anomalies",
        "description": (
            "Detect anomalies in a company's price, fundamentals, activity, and sector positioning."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "identifier": {"type": "string", "description": "Company ticker or CIK"},
                "lookback_days": {
                    "type": "integer",
                    "description": "Days to look back (default 90)",
                    "default": 90,
                },
            },
            "required": ["identifier"],
        },
    },
    {
        "name": "get_financials",
        "description": (
            "Get XBRL financial facts (revenue, net income, EPS, total assets, "
            "liabilities, operating cash flow) from 10-K filings over recent years. "
            "Includes YoY change % and derived margins. Source: SEC EDGAR."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "identifier": {"type": "string", "description": "Company ticker or CIK"},
                "years": {
                    "type": "integer",
                    "description": "Years of history (default 5)",
                    "default": 5,
                },
            },
            "required": ["identifier"],
        },
    },
    {
        "name": "get_prices",
        "description": (
            "Get price analytics including returns, volatility, SMAs, 52-week range for a company."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "identifier": {"type": "string", "description": "Company ticker or CIK"}
            },
            "required": ["identifier"],
        },
    },
    {
        "name": "get_news",
        "description": (
            "Get recent news articles with headlines, source, date, URL, "
            "and text snippet for a company. Source: FMP."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "identifier": {"type": "string", "description": "Company ticker or CIK"},
                "limit": {
                    "type": "integer",
                    "description": "Max articles (default 10)",
                    "default": 10,
                },
            },
            "required": ["identifier"],
        },
    },
    {
        "name": "get_insider",
        "description": "Get insider trading sentiment and recent trades for a company.",
        "input_schema": {
            "type": "object",
            "properties": {
                "identifier": {"type": "string", "description": "Company ticker or CIK"}
            },
            "required": ["identifier"],
        },
    },
    {
        "name": "get_macro",
        "description": (
            "Get macro economic indicators summary (GDP, unemployment, "
            "fed funds rate, 10Y yield, CPI, housing starts, industrial production). "
            "Source: FRED."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_metrics",
        "description": (
            "Get detailed valuation and quality metrics for a company: PE, PB, "
            "EV/EBITDA, P/S, EV/S, ROE, ROIC, net margin, operating margin, "
            "dividend yield, debt-to-equity, current ratio. Source: FMP (TTM)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "identifier": {"type": "string", "description": "Company ticker or CIK"}
            },
            "required": ["identifier"],
        },
    },
    {
        "name": "get_analyst_consensus",
        "description": (
            "Get analyst consensus: price target (high/low/avg/current), "
            "EPS estimates, grade distribution (buy/hold/sell counts), "
            "and implied upside %. Source: FMP."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "identifier": {"type": "string", "description": "Company ticker or CIK"}
            },
            "required": ["identifier"],
        },
    },
    {
        "name": "get_transcript_sentiment",
        "description": (
            "Get earnings call sentiment trends: per-quarter FinBERT scores "
            "(positive/negative/neutral) and top keywords from transcripts. "
            "Shows management tone over time. Source: NLP on FMP transcripts."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "identifier": {"type": "string", "description": "Company ticker or CIK"},
                "quarters": {
                    "type": "integer",
                    "description": "Number of quarters to look back (default 8)",
                    "default": 8,
                },
            },
            "required": ["identifier"],
        },
    },
    {
        "name": "get_events",
        "description": (
            "Get 8-K material events for a company: event counts by type "
            "(leadership changes, acquisitions, financial restatements, etc.) "
            "and time windows. Source: SEC EDGAR."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "identifier": {"type": "string", "description": "Company ticker or CIK"}
            },
            "required": ["identifier"],
        },
    },
]


async def _resolve_company(session: AsyncSession, identifier: str) -> tuple[int, str] | None:
    """Resolve identifier to (company_id, ticker)."""
    from atlas_intel.services.company_service import get_company_by_identifier

    company = await get_company_by_identifier(session, identifier)
    if not company:
        return None
    return company.id, company.ticker or identifier


async def execute_tool(
    session: AsyncSession,
    tool_name: str,
    tool_input: dict[str, Any],
) -> str:
    """Execute a tool and return JSON result string."""
    try:
        result = await _execute_tool_inner(session, tool_name, tool_input)
        return json.dumps(result, default=str)
    except Exception as exc:
        logger.exception("Tool execution failed: %s", tool_name)
        return json.dumps({"error": str(exc)})


async def _execute_tool_inner(
    session: AsyncSession,
    tool_name: str,
    tool_input: dict[str, Any],
) -> Any:
    """Dispatch tool call to appropriate service function."""
    if tool_name == "get_company":
        from atlas_intel.services.company_service import (
            get_company_by_identifier,
            get_company_detail,
        )

        result = await get_company_detail(session, tool_input["identifier"])
        if not result:
            return {"error": "Company not found"}

        # Enrich with key valuation metrics
        company = await get_company_by_identifier(session, tool_input["identifier"])
        if company:
            from atlas_intel.services.metric_service import get_latest_metrics_cached

            metrics = await get_latest_metrics_cached(session, company.id)
            if metrics:
                for key in (
                    "pe_ratio",
                    "pb_ratio",
                    "market_cap",
                    "roe",
                    "ev_to_ebitda",
                    "debt_to_equity",
                ):
                    if metrics.get(key) is not None:
                        result[key] = metrics[key]
        return result

    if tool_name == "screen_companies":
        from atlas_intel.schemas.screening import ScreenFilter
        from atlas_intel.services.screening_service import screen_companies

        c_filters: list[ScreenFilter] = []
        m_filters: list[ScreenFilter] = []
        if tool_input.get("sector"):
            c_filters.append(ScreenFilter(field="sector", op="eq", value=tool_input["sector"]))
        if tool_input.get("industry"):
            c_filters.append(ScreenFilter(field="industry", op="eq", value=tool_input["industry"]))
        if tool_input.get("pe_lt"):
            m_filters.append(ScreenFilter(field="pe_ratio", op="lt", value=tool_input["pe_lt"]))
        if tool_input.get("pe_gt"):
            m_filters.append(ScreenFilter(field="pe_ratio", op="gt", value=tool_input["pe_gt"]))
        if tool_input.get("roe_gt"):
            m_filters.append(ScreenFilter(field="roe", op="gt", value=tool_input["roe_gt"]))
        if tool_input.get("market_cap_gt"):
            m_filters.append(
                ScreenFilter(field="market_cap", op="gt", value=tool_input["market_cap_gt"])
            )

        screen_result = await screen_companies(
            session,
            metric_filters=m_filters or None,
            company_filters=c_filters or None,
            sort_by=tool_input.get("sort_by", "market_cap"),
            sort_order="desc",
            limit=tool_input.get("limit", 10),
        )
        return screen_result.model_dump()

    if tool_name == "get_signals":
        info = await _resolve_company(session, tool_input["identifier"])
        if not info:
            return {"error": "Company not found"}
        company_id, _ticker = info

        from atlas_intel.services.fusion_service import (
            compute_growth_signal,
            compute_risk_signal,
            compute_sentiment_signal,
            compute_smart_money_signal,
        )

        sentiment = await compute_sentiment_signal(session, company_id)
        growth = await compute_growth_signal(session, company_id)
        risk = await compute_risk_signal(session, company_id)
        smart_money = await compute_smart_money_signal(session, company_id)
        return {
            "sentiment": sentiment.model_dump(),
            "growth": growth.model_dump(),
            "risk": risk.model_dump(),
            "smart_money": smart_money.model_dump(),
        }

    if tool_name == "get_valuation":
        info = await _resolve_company(session, tool_input["identifier"])
        if not info:
            return {"error": "Company not found"}
        company_id, ticker = info

        from atlas_intel.services.valuation_service import compute_full_valuation_cached

        val = await compute_full_valuation_cached(session, company_id, ticker)
        return val.model_dump()

    if tool_name == "get_anomalies":
        info = await _resolve_company(session, tool_input["identifier"])
        if not info:
            return {"error": "Company not found"}
        company_id, ticker = info

        from atlas_intel.services.anomaly_service import detect_all_anomalies_cached

        lookback = tool_input.get("lookback_days", 90)
        anomalies = await detect_all_anomalies_cached(
            session, company_id, ticker, lookback_days=lookback
        )
        return anomalies.model_dump()

    if tool_name == "get_financials":
        info = await _resolve_company(session, tool_input["identifier"])
        if not info:
            return {"error": "Company not found"}
        company_id, _ticker = info

        from atlas_intel.services.financial_service import get_financial_summary

        summary = await get_financial_summary(session, company_id, years=tool_input.get("years", 5))

        # Enrich with YoY changes and derived margins
        revenue_by_year: dict[int, float] = {}
        net_income_by_year: dict[int, float] = {}
        for item in summary:
            values = item.get("values", [])
            for i, v in enumerate(values):
                fy = v.get("fiscal_year")
                val = v.get("value")
                if fy is None or val is None:
                    continue
                if item["concept"] == "Revenues":
                    revenue_by_year[fy] = float(val)
                elif item["concept"] == "NetIncomeLoss":
                    net_income_by_year[fy] = float(val)
                # Compute YoY change % (values are ordered desc)
                if i + 1 < len(values):
                    prev = values[i + 1].get("value")
                    if prev and float(prev) != 0:
                        v["yoy_change_pct"] = round(
                            (float(val) - float(prev)) / abs(float(prev)) * 100, 2
                        )

        # Add net margin where both revenue and net income exist
        margins = []
        for fy in sorted(revenue_by_year.keys(), reverse=True):
            rev = revenue_by_year[fy]
            ni = net_income_by_year.get(fy)
            if rev and ni and rev != 0:
                margins.append({"fiscal_year": fy, "net_margin_pct": round(ni / rev * 100, 2)})
        if margins:
            summary.append({"concept": "_derived_net_margin", "values": margins})

        return summary

    if tool_name == "get_prices":
        info = await _resolve_company(session, tool_input["identifier"])
        if not info:
            return {"error": "Company not found"}
        company_id, ticker = info

        from atlas_intel.services.price_service import get_price_analytics_cached

        return await get_price_analytics_cached(session, company_id, ticker)

    if tool_name == "get_news":
        info = await _resolve_company(session, tool_input["identifier"])
        if not info:
            return {"error": "Company not found"}
        company_id, _ticker = info

        from atlas_intel.services.news_service import get_news

        articles, total = await get_news(session, company_id, limit=tool_input.get("limit", 10))
        return {
            "total": total,
            "articles": [
                {
                    "title": a.title,
                    "published_at": str(a.published_at),
                    "source": a.source_name,
                    "url": a.url,
                    "snippet": a.snippet,
                }
                for a in articles
            ],
        }

    if tool_name == "get_insider":
        info = await _resolve_company(session, tool_input["identifier"])
        if not info:
            return {"error": "Company not found"}
        company_id, ticker = info

        from atlas_intel.services.insider_service import get_insider_sentiment

        return await get_insider_sentiment(session, company_id, ticker)

    if tool_name == "get_macro":
        from atlas_intel.services.macro_service import get_macro_summary

        return await get_macro_summary(session)

    if tool_name == "get_metrics":
        info = await _resolve_company(session, tool_input["identifier"])
        if not info:
            return {"error": "Company not found"}
        company_id, _ticker = info

        from atlas_intel.services.metric_service import get_latest_metrics_cached

        metrics = await get_latest_metrics_cached(session, company_id)
        return metrics or {"error": "No metrics data available"}

    if tool_name == "get_analyst_consensus":
        info = await _resolve_company(session, tool_input["identifier"])
        if not info:
            return {"error": "Company not found"}
        company_id, ticker = info

        from atlas_intel.services.analyst_service import get_analyst_consensus_cached

        return await get_analyst_consensus_cached(session, company_id, ticker)

    if tool_name == "get_transcript_sentiment":
        info = await _resolve_company(session, tool_input["identifier"])
        if not info:
            return {"error": "Company not found"}
        company_id, _ticker = info

        from atlas_intel.services.transcript_service import (
            get_keyword_analysis,
            get_sentiment_trend,
        )

        quarters = tool_input.get("quarters", 8)
        trend = await get_sentiment_trend(session, company_id, quarters=quarters)
        keywords = await get_keyword_analysis(session, company_id, top_n=15)
        return {"sentiment_trend": trend, "top_keywords": keywords}

    if tool_name == "get_events":
        info = await _resolve_company(session, tool_input["identifier"])
        if not info:
            return {"error": "Company not found"}
        company_id, ticker = info

        from atlas_intel.services.event_service import get_event_summary

        return await get_event_summary(session, company_id, ticker)

    return {"error": f"Unknown tool: {tool_name}"}
