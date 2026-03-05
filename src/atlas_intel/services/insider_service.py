"""Insider trading business logic and analytics."""

from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.models.insider_trade import InsiderTrade


async def get_insider_trades(
    session: AsyncSession,
    company_id: int,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[InsiderTrade], int]:
    """Query insider trades paginated. Returns (trades, total_count)."""
    count_stmt = select(func.count(InsiderTrade.id)).where(InsiderTrade.company_id == company_id)
    total = (await session.execute(count_stmt)).scalar() or 0

    stmt = (
        select(InsiderTrade)
        .where(InsiderTrade.company_id == company_id)
        .order_by(InsiderTrade.filing_date.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all()), total


async def get_insider_sentiment(
    session: AsyncSession,
    company_id: int,
    ticker: str,
    days: int = 90,
) -> dict[str, Any]:
    """Compute insider sentiment over the given period."""
    cutoff = date.today() - timedelta(days=days)
    analytics: dict[str, Any] = {"ticker": ticker, "days": days}

    stmt = select(InsiderTrade).where(
        InsiderTrade.company_id == company_id,
        InsiderTrade.filing_date >= cutoff,
    )
    result = await session.execute(stmt)
    trades = list(result.scalars().all())

    buys = [t for t in trades if t.transaction_type == "P"]
    sells = [t for t in trades if t.transaction_type == "S"]

    analytics["buy_count"] = len(buys)
    analytics["sell_count"] = len(sells)

    # Total values
    total_buy = sum(
        float(t.securities_transacted * t.price)
        for t in buys
        if t.securities_transacted and t.price
    )
    total_sell = sum(
        float(t.securities_transacted * t.price)
        for t in sells
        if t.securities_transacted and t.price
    )
    analytics["total_buy_value"] = round(total_buy, 2) if total_buy else None
    analytics["total_sell_value"] = round(total_sell, 2) if total_sell else None

    # Net ratio: buy_count / (buy_count + sell_count)
    total_trades = len(buys) + len(sells)
    if total_trades > 0:
        analytics["net_ratio"] = round(len(buys) / total_trades, 4)
    else:
        analytics["net_ratio"] = None

    # Sentiment label
    if analytics["net_ratio"] is not None:
        if analytics["net_ratio"] >= 0.6:
            analytics["sentiment"] = "bullish"
        elif analytics["net_ratio"] <= 0.4:
            analytics["sentiment"] = "bearish"
        else:
            analytics["sentiment"] = "neutral"
    else:
        analytics["sentiment"] = "neutral"

    # Top 5 buyers/sellers by value
    def _top_by_value(
        trade_list: list[InsiderTrade],
    ) -> list[dict[str, object]]:
        by_name: dict[str, float] = {}
        for t in trade_list:
            if t.securities_transacted and t.price:
                val = float(t.securities_transacted * t.price)
                by_name[t.reporting_name] = by_name.get(t.reporting_name, 0) + val
        sorted_names = sorted(by_name.items(), key=lambda x: x[1], reverse=True)[:5]
        return [{"name": n, "value": round(v, 2)} for n, v in sorted_names]

    analytics["top_buyers"] = _top_by_value(buys)
    analytics["top_sellers"] = _top_by_value(sells)

    return analytics
