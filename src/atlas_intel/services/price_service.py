"""Stock price business logic and analytics."""

import math
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.models.stock_price import StockPrice


def _pct_return(old: Decimal, new: Decimal) -> float | None:
    """Calculate percentage return between two prices."""
    if old == 0:
        return None
    return float((new - old) / old * 100)


def _annualized_volatility(closes: list[Decimal]) -> float | None:
    """Calculate annualized volatility from a list of closing prices (log returns)."""
    if len(closes) < 2:
        return None
    log_returns = []
    for i in range(1, len(closes)):
        if closes[i - 1] > 0 and closes[i] > 0:
            log_returns.append(math.log(float(closes[i]) / float(closes[i - 1])))
    if len(log_returns) < 2:
        return None
    mean = sum(log_returns) / len(log_returns)
    variance = sum((r - mean) ** 2 for r in log_returns) / (len(log_returns) - 1)
    daily_vol = math.sqrt(variance)
    return daily_vol * math.sqrt(252) * 100  # annualized, as percentage


async def get_prices(
    session: AsyncSession,
    company_id: int,
    from_date: date | None = None,
    to_date: date | None = None,
    offset: int = 0,
    limit: int = 100,
) -> tuple[list[StockPrice], int]:
    """Query stock prices with optional date range. Returns (prices, total_count)."""
    stmt = select(StockPrice).where(StockPrice.company_id == company_id)
    count_stmt = select(func.count(StockPrice.id)).where(StockPrice.company_id == company_id)

    if from_date:
        stmt = stmt.where(StockPrice.price_date >= from_date)
        count_stmt = count_stmt.where(StockPrice.price_date >= from_date)
    if to_date:
        stmt = stmt.where(StockPrice.price_date <= to_date)
        count_stmt = count_stmt.where(StockPrice.price_date <= to_date)

    total = (await session.execute(count_stmt)).scalar() or 0

    stmt = stmt.order_by(StockPrice.price_date.desc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all()), total


async def get_price_analytics(
    session: AsyncSession,
    company_id: int,
    ticker: str,
) -> dict[str, Any]:
    """Compute price analytics on-the-fly from last 252 trading days."""
    stmt = (
        select(StockPrice)
        .where(StockPrice.company_id == company_id)
        .order_by(StockPrice.price_date.desc())
        .limit(252)
    )
    result = await session.execute(stmt)
    prices = list(result.scalars().all())

    analytics: dict[str, Any] = {"ticker": ticker}

    if not prices:
        return analytics

    # Prices are ordered desc, so prices[0] is most recent
    latest = prices[0]
    analytics["latest_close"] = latest.close
    analytics["latest_date"] = latest.price_date

    closes = [p.close for p in reversed(prices) if p.close is not None]

    if len(closes) < 2:
        return analytics

    # Returns
    analytics["daily_return_pct"] = _pct_return(closes[-2], closes[-1])

    if len(closes) >= 5:
        analytics["weekly_return_pct"] = _pct_return(closes[-5], closes[-1])
    if len(closes) >= 21:
        analytics["monthly_return_pct"] = _pct_return(closes[-21], closes[-1])

    # YTD return
    today = date.today()
    year_start = date(today.year, 1, 1)
    ytd_prices = [p for p in reversed(prices) if p.price_date >= year_start and p.close is not None]
    if len(ytd_prices) >= 2:
        analytics["ytd_return_pct"] = _pct_return(ytd_prices[0].close, ytd_prices[-1].close)  # type: ignore[arg-type]

    # Volatility
    if len(closes) >= 30:
        analytics["volatility_30d"] = _annualized_volatility(closes[-30:])
    if len(closes) >= 90:
        analytics["volatility_90d"] = _annualized_volatility(closes[-90:])

    # SMAs
    if len(closes) >= 50:
        analytics["sma_50"] = sum(float(c) for c in closes[-50:]) / 50
    if len(closes) >= 200:
        analytics["sma_200"] = sum(float(c) for c in closes[-200:]) / 200

    # 52-week high/low (252 trading days ~ 1 year)
    analytics["high_52w"] = max(p.high for p in prices if p.high is not None)
    analytics["low_52w"] = min(p.low for p in prices if p.low is not None)

    # 30-day avg volume
    recent_volumes = [p.volume for p in prices[:30] if p.volume is not None]
    if recent_volumes:
        analytics["avg_volume_30d"] = sum(recent_volumes) / len(recent_volumes)

    return analytics


async def get_daily_returns(
    session: AsyncSession,
    company_id: int,
    from_date: date | None = None,
    to_date: date | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Compute daily returns series."""
    stmt = (
        select(StockPrice)
        .where(StockPrice.company_id == company_id)
        .order_by(StockPrice.price_date.asc())
    )
    if from_date:
        # Fetch one extra day before from_date for the first return calculation
        stmt = stmt.where(StockPrice.price_date >= from_date - timedelta(days=7))
    if to_date:
        stmt = stmt.where(StockPrice.price_date <= to_date)

    result = await session.execute(stmt)
    prices = list(result.scalars().all())

    returns = []
    for i in range(1, len(prices)):
        prev_close = prices[i - 1].close
        curr_close = prices[i].close
        if prev_close is None or curr_close is None:
            continue

        daily_return = _pct_return(prev_close, curr_close)

        # Apply from_date filter (we fetched extra data for calculation)
        if from_date and prices[i].price_date < from_date:
            continue

        returns.append(
            {
                "price_date": prices[i].price_date,
                "close": curr_close,
                "daily_return": daily_return,
            }
        )

    # Apply limit from end (most recent)
    if len(returns) > limit:
        returns = returns[-limit:]

    return returns
