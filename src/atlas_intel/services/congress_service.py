"""Congress trading business logic and analytics."""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.models.congress_trade import CongressTrade


async def get_congress_trades(
    session: AsyncSession,
    company_id: int,
    party: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[CongressTrade], int]:
    """Query congress trades paginated with optional party filter."""
    base_where = [CongressTrade.company_id == company_id]
    if party:
        base_where.append(CongressTrade.party == party.upper())

    count_stmt = select(func.count(CongressTrade.id)).where(*base_where)
    total = (await session.execute(count_stmt)).scalar() or 0

    stmt = (
        select(CongressTrade)
        .where(*base_where)
        .order_by(CongressTrade.transaction_date.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all()), total


async def get_congress_summary(
    session: AsyncSession,
    company_id: int,
    ticker: str,
) -> dict[str, Any]:
    """Congress trading summary: buy/sell counts, party breakdown, top traders."""
    analytics: dict[str, Any] = {"ticker": ticker}

    # Total trades
    total = (
        await session.execute(
            select(func.count(CongressTrade.id)).where(CongressTrade.company_id == company_id)
        )
    ).scalar() or 0
    analytics["total_trades"] = total

    # Purchases vs sales
    for label, tx_type in [("purchases", "purchase"), ("sales", "sale")]:
        count = (
            await session.execute(
                select(func.count(CongressTrade.id)).where(
                    CongressTrade.company_id == company_id,
                    CongressTrade.transaction_type == tx_type,
                )
            )
        ).scalar() or 0
        analytics[label] = count

    # Party breakdown
    for label, party_code in [("democrat_trades", "D"), ("republican_trades", "R")]:
        count = (
            await session.execute(
                select(func.count(CongressTrade.id)).where(
                    CongressTrade.company_id == company_id,
                    CongressTrade.party == party_code,
                )
            )
        ).scalar() or 0
        analytics[label] = count

    # Top 5 traders
    trader_result = await session.execute(
        select(CongressTrade.representative, func.count(CongressTrade.id).label("cnt"))
        .where(CongressTrade.company_id == company_id)
        .group_by(CongressTrade.representative)
        .order_by(func.count(CongressTrade.id).desc())
        .limit(5)
    )
    analytics["top_traders"] = [
        {"representative": row[0], "trade_count": row[1]} for row in trader_result.all()
    ]

    return analytics
