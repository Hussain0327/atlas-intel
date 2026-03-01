"""Financial facts business logic."""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.models.company import Company
from atlas_intel.models.financial_fact import FinancialFact

# Key concepts for the summary endpoint
SUMMARY_CONCEPTS = [
    "Revenues",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "NetIncomeLoss",
    "Assets",
    "Liabilities",
    "StockholdersEquity",
    "EarningsPerShareBasic",
    "EarningsPerShareDiluted",
    "OperatingIncomeLoss",
    "CashAndCashEquivalentsAtCarryingValue",
    "LongTermDebt",
    "CommonStockSharesOutstanding",
]


async def get_financial_facts(
    session: AsyncSession,
    company_id: int,
    concept: str | None = None,
    form_type: str | None = None,
    fiscal_year: int | None = None,
    fiscal_period: str | None = None,
    taxonomy: str | None = None,
    offset: int = 0,
    limit: int = 100,
) -> tuple[list[FinancialFact], int]:
    """Query financial facts with filters."""
    stmt = select(FinancialFact).where(FinancialFact.company_id == company_id)
    count_stmt = select(func.count(FinancialFact.id)).where(FinancialFact.company_id == company_id)

    if concept:
        stmt = stmt.where(FinancialFact.concept == concept)
        count_stmt = count_stmt.where(FinancialFact.concept == concept)
    if form_type:
        stmt = stmt.where(FinancialFact.form_type == form_type)
        count_stmt = count_stmt.where(FinancialFact.form_type == form_type)
    if fiscal_year:
        stmt = stmt.where(FinancialFact.fiscal_year == fiscal_year)
        count_stmt = count_stmt.where(FinancialFact.fiscal_year == fiscal_year)
    if fiscal_period:
        stmt = stmt.where(FinancialFact.fiscal_period == fiscal_period)
        count_stmt = count_stmt.where(FinancialFact.fiscal_period == fiscal_period)
    if taxonomy:
        stmt = stmt.where(FinancialFact.taxonomy == taxonomy)
        count_stmt = count_stmt.where(FinancialFact.taxonomy == taxonomy)

    total = (await session.execute(count_stmt)).scalar() or 0

    stmt = (
        stmt.order_by(
            FinancialFact.fiscal_year.desc(),
            FinancialFact.period_end.desc(),
        )
        .offset(offset)
        .limit(limit)
    )

    result = await session.execute(stmt)
    return list(result.scalars().all()), total


async def get_financial_summary(
    session: AsyncSession,
    company_id: int,
    years: int = 5,
) -> list[dict[str, Any]]:
    """Get key financial metrics for the last N fiscal years."""
    summary = []
    for concept in SUMMARY_CONCEPTS:
        stmt = (
            select(FinancialFact)
            .where(
                FinancialFact.company_id == company_id,
                FinancialFact.concept == concept,
                FinancialFact.form_type == "10-K",
                FinancialFact.fiscal_period == "FY",
            )
            .order_by(FinancialFact.fiscal_year.desc())
            .limit(years)
        )
        result = await session.execute(stmt)
        facts = list(result.scalars().all())
        if facts:
            summary.append(
                {
                    "concept": concept,
                    "values": [
                        {
                            "fiscal_year": f.fiscal_year,
                            "fiscal_period": f.fiscal_period or "FY",
                            "value": f.value,
                            "unit": f.unit,
                            "period_end": f.period_end,
                        }
                        for f in facts
                        if f.fiscal_year is not None
                    ],
                }
            )
    return summary


async def compare_metric(
    session: AsyncSession,
    concept: str,
    tickers: list[str],
    form_type: str = "10-K",
    fiscal_period: str = "FY",
    years: int = 5,
) -> list[dict[str, Any]]:
    """Compare a single metric across multiple companies."""
    results = []
    for ticker in tickers:
        company_result = await session.execute(
            select(Company).where(func.upper(Company.ticker) == ticker.upper())
        )
        company = company_result.scalar_one_or_none()
        if not company:
            continue

        stmt = (
            select(FinancialFact)
            .where(
                FinancialFact.company_id == company.id,
                FinancialFact.concept == concept,
                FinancialFact.form_type == form_type,
                FinancialFact.fiscal_period == fiscal_period,
            )
            .order_by(FinancialFact.fiscal_year.desc())
            .limit(years)
        )
        result = await session.execute(stmt)
        facts = list(result.scalars().all())

        results.append(
            {
                "ticker": company.ticker or ticker,
                "company_name": company.name,
                "values": [
                    {
                        "fiscal_year": f.fiscal_year,
                        "fiscal_period": f.fiscal_period or fiscal_period,
                        "value": f.value,
                        "unit": f.unit,
                        "period_end": f.period_end,
                    }
                    for f in facts
                    if f.fiscal_year is not None
                ],
            }
        )

    return results
