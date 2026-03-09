"""Valuation models: DCF, relative valuation, analyst-implied.

All computation is read-side from existing data. Missing inputs produce reduced
data_quality / confidence, never errors.
"""

import statistics

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.cache import read_cache
from atlas_intel.ingestion.utils import utcnow
from atlas_intel.models.company import Company
from atlas_intel.models.financial_fact import FinancialFact
from atlas_intel.models.macro_indicator import MacroIndicator
from atlas_intel.models.market_metric import MarketMetric
from atlas_intel.models.price_target import PriceTarget
from atlas_intel.models.stock_price import StockPrice
from atlas_intel.schemas.valuation import (
    AnalystValuationResponse,
    DCFResponse,
    DCFScenario,
    FullValuationResponse,
    MultipleBenchmark,
    RelativeValuationResponse,
)

# Constants
EQUITY_RISK_PREMIUM = 0.055  # 5.5% historical avg
TERMINAL_GROWTH_RATE = 0.025  # 2.5% long-term GDP proxy
DCF_PROJECTION_YEARS = 5
VALUATION_CACHE_TTL = 1800  # 30 minutes

# XBRL concept fallback chains (try in order)
OCF_CONCEPTS = [
    "NetCashProvidedByUsedInOperatingActivities",
    "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
]
CAPEX_CONCEPTS = [
    "PaymentsToAcquirePropertyPlantAndEquipment",
    "PaymentsToAcquireProductiveAssets",
]
REVENUE_CONCEPTS = ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax"]
SHARES_CONCEPTS = ["CommonStockSharesOutstanding"]

# Multiples used for relative valuation
RELATIVE_MULTIPLES = [
    ("pe_ratio", "P/E"),
    ("pb_ratio", "P/B"),
    ("ev_to_ebitda", "EV/EBITDA"),
    ("price_to_sales", "P/S"),
    ("ev_to_sales", "EV/S"),
]


async def _get_fact_series(
    session: AsyncSession,
    company_id: int,
    concepts: list[str],
    years: int = 5,
) -> list[tuple[int, float]]:
    """Query EAV table for first matching concept, returns (fiscal_year, value) pairs."""
    for concept in concepts:
        stmt = (
            select(FinancialFact.fiscal_year, FinancialFact.value)
            .where(
                FinancialFact.company_id == company_id,
                FinancialFact.concept == concept,
                FinancialFact.form_type == "10-K",
                FinancialFact.fiscal_period == "FY",
                FinancialFact.fiscal_year.is_not(None),
            )
            .order_by(FinancialFact.fiscal_year.desc())
            .limit(years)
        )
        result = await session.execute(stmt)
        rows = [(int(r[0]), float(r[1])) for r in result.all()]
        if rows:
            return rows
    return []


async def _get_latest_risk_free_rate(session: AsyncSession) -> float | None:
    """Latest DGS10 (10-year treasury yield) from macro_indicators."""
    stmt = (
        select(MacroIndicator.value)
        .where(MacroIndicator.series_id == "DGS10")
        .order_by(MacroIndicator.observation_date.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    val = result.scalar_one_or_none()
    if val is not None:
        return float(val) / 100  # Convert from percentage to decimal
    return None


def _compute_dcf(
    fcf_history: list[float],
    shares: float,
    beta: float,
    risk_free_rate: float,
    growth_adj: float = 0.0,
    discount_adj: float = 0.0,
) -> DCFScenario | None:
    """Pure DCF computation. Returns a scenario or None if inputs are insufficient.

    Args:
        fcf_history: FCF values ordered most-recent-first.
        shares: Shares outstanding.
        beta: Company beta for WACC calculation.
        risk_free_rate: Risk-free rate (decimal, e.g. 0.04).
        growth_adj: Adjustment to historical growth rate.
        discount_adj: Adjustment to WACC.
    """
    if not fcf_history or shares <= 0:
        return None

    latest_fcf = fcf_history[0]
    if latest_fcf <= 0:
        return None

    # Calculate historical FCF growth rate
    if len(fcf_history) >= 2:
        positive_fcfs = [f for f in fcf_history if f > 0]
        if len(positive_fcfs) >= 2:
            oldest = positive_fcfs[-1]
            newest = positive_fcfs[0]
            n_years = len(positive_fcfs) - 1
            if oldest > 0 and n_years > 0:
                growth_rate = (newest / oldest) ** (1 / n_years) - 1
            else:
                growth_rate = 0.05  # Default 5%
        else:
            growth_rate = 0.05
    else:
        growth_rate = 0.05

    # Clamp growth rate to reasonable range
    growth_rate = max(min(growth_rate + growth_adj, 0.30), -0.10)

    # WACC = risk_free + beta * equity_risk_premium
    wacc = risk_free_rate + beta * EQUITY_RISK_PREMIUM + discount_adj
    wacc = max(wacc, 0.04)  # Floor at 4%

    # Project FCFs
    projected_fcfs = []
    fcf = latest_fcf
    for _ in range(DCF_PROJECTION_YEARS):
        fcf = fcf * (1 + growth_rate)
        projected_fcfs.append(round(fcf, 2))

    # Terminal value (Gordon growth model)
    terminal_growth = min(TERMINAL_GROWTH_RATE, wacc - 0.01)  # Must be < WACC
    if wacc <= terminal_growth:
        return None
    terminal_value = projected_fcfs[-1] * (1 + terminal_growth) / (wacc - terminal_growth)

    # Discount to present value
    pv_fcfs = sum(fcf / (1 + wacc) ** (i + 1) for i, fcf in enumerate(projected_fcfs))
    pv_terminal = terminal_value / (1 + wacc) ** DCF_PROJECTION_YEARS
    enterprise_value = pv_fcfs + pv_terminal

    intrinsic_per_share = enterprise_value / shares

    return DCFScenario(
        label="",  # Set by caller
        growth_rate=round(growth_rate, 4),
        discount_rate=round(wacc, 4),
        intrinsic_value_per_share=round(intrinsic_per_share, 2),
        projected_fcfs=projected_fcfs,
        terminal_value=round(terminal_value, 2),
    )


async def compute_dcf_valuation(
    session: AsyncSession,
    company_id: int,
    ticker: str,
) -> DCFResponse:
    """Compute DCF valuation with 3 scenarios (bear/base/bull)."""
    missing: list[str] = []

    # Get FCF history (OCF - CapEx)
    ocf_series = await _get_fact_series(session, company_id, OCF_CONCEPTS, years=6)
    capex_series = await _get_fact_series(session, company_id, CAPEX_CONCEPTS, years=6)

    fcf_history: list[float] = []
    if ocf_series:
        capex_by_year = dict(capex_series) if capex_series else {}
        for year, ocf in ocf_series:
            capex = capex_by_year.get(year, 0)
            fcf_history.append(ocf - abs(capex))
    else:
        missing.append("operating_cash_flow")

    # Shares outstanding
    shares_series = await _get_fact_series(session, company_id, SHARES_CONCEPTS, years=1)
    shares = shares_series[0][1] if shares_series else None
    if not shares:
        missing.append("shares_outstanding")

    # Beta
    company = await session.get(Company, company_id)
    beta = float(company.beta) if company and company.beta else None
    if beta is None:
        missing.append("beta")

    # Risk-free rate
    risk_free_rate = await _get_latest_risk_free_rate(session)
    if risk_free_rate is None:
        missing.append("risk_free_rate")

    # Current price
    price_stmt = (
        select(StockPrice.close)
        .where(StockPrice.company_id == company_id)
        .order_by(StockPrice.price_date.desc())
        .limit(1)
    )
    price_result = await session.execute(price_stmt)
    current_price_dec = price_result.scalar_one_or_none()
    current_price = float(current_price_dec) if current_price_dec else None

    # Determine data quality
    if not fcf_history or not shares:
        data_quality = "insufficient"
    elif len(fcf_history) < 3 or not beta or not risk_free_rate:
        data_quality = "limited"
    else:
        data_quality = "good"

    # Use defaults for missing values
    effective_beta = beta if beta is not None else 1.0
    effective_rf = risk_free_rate if risk_free_rate is not None else 0.04
    effective_shares = shares if shares else 1.0

    scenarios: list[DCFScenario] = []

    if fcf_history and effective_shares > 0:
        # Bear scenario: lower growth, higher discount
        bear = _compute_dcf(
            fcf_history,
            effective_shares,
            effective_beta,
            effective_rf,
            growth_adj=-0.02,
            discount_adj=0.02,
        )
        if bear:
            bear.label = "bear"
            if current_price:
                bear.upside_pct = round(
                    (bear.intrinsic_value_per_share - current_price) / current_price * 100, 2
                )
            scenarios.append(bear)

        # Base scenario
        base = _compute_dcf(
            fcf_history,
            effective_shares,
            effective_beta,
            effective_rf,
        )
        if base:
            base.label = "base"
            if current_price:
                base.upside_pct = round(
                    (base.intrinsic_value_per_share - current_price) / current_price * 100, 2
                )
            scenarios.append(base)

        # Bull scenario: higher growth, lower discount
        bull = _compute_dcf(
            fcf_history,
            effective_shares,
            effective_beta,
            effective_rf,
            growth_adj=0.02,
            discount_adj=-0.02,
        )
        if bull:
            bull.label = "bull"
            if current_price:
                bull.upside_pct = round(
                    (bull.intrinsic_value_per_share - current_price) / current_price * 100, 2
                )
            scenarios.append(bull)

    # Compute historical FCF growth for response
    hist_growth: float | None = None
    positive_fcfs = [f for f in fcf_history if f > 0]
    if len(positive_fcfs) >= 2:
        oldest = positive_fcfs[-1]
        newest = positive_fcfs[0]
        n = len(positive_fcfs) - 1
        if oldest > 0 and n > 0:
            hist_growth = round((newest / oldest) ** (1 / n) - 1, 4)

    wacc: float | None = None
    if beta is not None and risk_free_rate is not None:
        wacc = round(effective_rf + effective_beta * EQUITY_RISK_PREMIUM, 4)

    return DCFResponse(
        ticker=ticker,
        current_price=current_price,
        shares_outstanding=shares,
        latest_fcf=fcf_history[0] if fcf_history else None,
        historical_fcf_growth=hist_growth,
        risk_free_rate=risk_free_rate,
        beta=beta if beta is not None else None,
        wacc=wacc,
        scenarios=scenarios,
        data_quality=data_quality,
        missing_inputs=missing,
        computed_at=utcnow(),
    )


async def _get_sector_peer_metrics(
    session: AsyncSession,
    sector: str,
) -> list[MarketMetric]:
    """Get latest TTM metrics for all companies in a sector (single efficient query)."""
    # DISTINCT ON subquery for latest TTM per company
    latest_sub = (
        select(MarketMetric)
        .where(MarketMetric.period == "TTM")
        .distinct(MarketMetric.company_id)
        .order_by(MarketMetric.company_id, MarketMetric.period_date.desc())
        .subquery()
    )
    stmt = (
        select(latest_sub)
        .join(Company, Company.id == latest_sub.c.company_id)
        .where(Company.sector == sector)
    )
    result = await session.execute(stmt)
    return [MarketMetric(**dict(row._mapping)) for row in result.all()]


async def compute_relative_valuation(
    session: AsyncSession,
    company_id: int,
    ticker: str,
) -> RelativeValuationResponse:
    """Compare company multiples vs sector peers."""
    company = await session.get(Company, company_id)
    sector = company.sector if company else None

    if not sector:
        return RelativeValuationResponse(ticker=ticker, computed_at=utcnow())

    # Get company's latest TTM metrics
    company_metric_stmt = (
        select(MarketMetric)
        .where(MarketMetric.company_id == company_id, MarketMetric.period == "TTM")
        .order_by(MarketMetric.period_date.desc())
        .limit(1)
    )
    result = await session.execute(company_metric_stmt)
    company_metrics = result.scalar_one_or_none()

    if not company_metrics:
        return RelativeValuationResponse(ticker=ticker, sector=sector, computed_at=utcnow())

    # Get all sector peers' latest TTM metrics
    peer_metrics = await _get_sector_peer_metrics(session, sector)

    # Exclude self from peers
    peers = [p for p in peer_metrics if p.company_id != company_id]
    if not peers:
        return RelativeValuationResponse(
            ticker=ticker, sector=sector, peer_count=0, computed_at=utcnow()
        )

    multiples: list[MultipleBenchmark] = []
    premium_pcts: list[float] = []

    for attr, label in RELATIVE_MULTIPLES:
        company_val = getattr(company_metrics, attr, None)
        if company_val is None:
            multiples.append(MultipleBenchmark(metric_name=label))
            continue

        peer_vals = [
            float(getattr(p, attr))
            for p in peers
            if getattr(p, attr, None) is not None and float(getattr(p, attr)) > 0
        ]

        if not peer_vals:
            multiples.append(MultipleBenchmark(metric_name=label, company_value=float(company_val)))
            continue

        median = statistics.median(peer_vals)
        mean = statistics.mean(peer_vals)
        premium = ((float(company_val) / median) - 1) * 100 if median > 0 else None

        assessment = "unavailable"
        if premium is not None:
            if premium < -15:
                assessment = "discount"
            elif premium > 15:
                assessment = "premium"
            else:
                assessment = "fair"

        multiples.append(
            MultipleBenchmark(
                metric_name=label,
                company_value=round(float(company_val), 4),
                sector_median=round(median, 4),
                sector_mean=round(mean, 4),
                peer_count=len(peer_vals),
                premium_pct=round(premium, 2) if premium is not None else None,
                assessment=assessment,
            )
        )
        if premium is not None:
            premium_pcts.append(premium)

    composite_premium = round(statistics.mean(premium_pcts), 2) if premium_pcts else None

    assessment = "unavailable"
    if composite_premium is not None:
        if composite_premium < -15:
            assessment = "undervalued"
        elif composite_premium > 15:
            assessment = "overvalued"
        else:
            assessment = "fairly_valued"

    return RelativeValuationResponse(
        ticker=ticker,
        sector=sector,
        peer_count=len(peers),
        multiples=multiples,
        composite_premium_pct=composite_premium,
        assessment=assessment,
        computed_at=utcnow(),
    )


async def compute_analyst_valuation(
    session: AsyncSession,
    company_id: int,
    ticker: str,
) -> AnalystValuationResponse:
    """Price target consensus vs current price."""
    # Get price target
    pt_stmt = select(PriceTarget).where(PriceTarget.company_id == company_id).limit(1)
    pt_result = await session.execute(pt_stmt)
    pt = pt_result.scalar_one_or_none()

    # Get current price
    price_stmt = (
        select(StockPrice.close)
        .where(StockPrice.company_id == company_id)
        .order_by(StockPrice.price_date.desc())
        .limit(1)
    )
    price_result = await session.execute(price_stmt)
    current_price_dec = price_result.scalar_one_or_none()
    current_price = float(current_price_dec) if current_price_dec else None

    if not pt or not pt.target_consensus:
        return AnalystValuationResponse(
            ticker=ticker, current_price=current_price, computed_at=utcnow()
        )

    consensus = float(pt.target_consensus)
    high = float(pt.target_high) if pt.target_high else None
    low = float(pt.target_low) if pt.target_low else None

    upside_pct: float | None = None
    downside_risk_pct: float | None = None
    upside_potential_pct: float | None = None

    if current_price and current_price > 0:
        upside_pct = round((consensus - current_price) / current_price * 100, 2)
        if low is not None:
            downside_risk_pct = round((low - current_price) / current_price * 100, 2)
        if high is not None:
            upside_potential_pct = round((high - current_price) / current_price * 100, 2)

    # Count distinct grading companies as proxy for analyst count
    analyst_count_stmt = select(func.count(func.distinct(PriceTarget.id))).where(
        PriceTarget.company_id == company_id
    )
    analyst_result = await session.execute(analyst_count_stmt)
    analyst_count = analyst_result.scalar() or 0

    return AnalystValuationResponse(
        ticker=ticker,
        current_price=current_price,
        target_consensus=consensus,
        target_high=high,
        target_low=low,
        upside_pct=upside_pct,
        downside_risk_pct=downside_risk_pct,
        upside_potential_pct=upside_potential_pct,
        analyst_count=analyst_count if analyst_count > 0 else None,
        computed_at=utcnow(),
    )


async def compute_full_valuation(
    session: AsyncSession,
    company_id: int,
    ticker: str,
) -> FullValuationResponse:
    """Combine all 3 valuation models."""
    dcf = await compute_dcf_valuation(session, company_id, ticker)
    relative = await compute_relative_valuation(session, company_id, ticker)
    analyst = await compute_analyst_valuation(session, company_id, ticker)

    # Composite assessment from available models
    signals: list[str] = []
    if dcf.scenarios:
        base = next((s for s in dcf.scenarios if s.label == "base"), None)
        if base and base.upside_pct is not None:
            if base.upside_pct > 20:
                signals.append("undervalued")
            elif base.upside_pct < -20:
                signals.append("overvalued")
            else:
                signals.append("fairly_valued")

    if relative.assessment != "unavailable":
        signals.append(relative.assessment)

    if analyst.upside_pct is not None:
        if analyst.upside_pct > 15:
            signals.append("undervalued")
        elif analyst.upside_pct < -15:
            signals.append("overvalued")
        else:
            signals.append("fairly_valued")

    composite = "unavailable"
    if signals:
        # Majority vote
        undervalued = signals.count("undervalued")
        overvalued = signals.count("overvalued")
        if undervalued > overvalued:
            composite = "undervalued"
        elif overvalued > undervalued:
            composite = "overvalued"
        else:
            composite = "fairly_valued"

    return FullValuationResponse(
        ticker=ticker,
        dcf=dcf,
        relative=relative,
        analyst=analyst,
        composite_assessment=composite,
        computed_at=utcnow(),
    )


async def compute_full_valuation_cached(
    session: AsyncSession,
    company_id: int,
    ticker: str,
) -> FullValuationResponse:
    """Cached full valuation."""
    result = await read_cache.get_or_set(
        f"valuation:{company_id}",
        VALUATION_CACHE_TTL,
        lambda: compute_full_valuation(session, company_id, ticker),
    )
    # Result could be a dict (from cache deepcopy) or FullValuationResponse
    if isinstance(result, dict):
        return FullValuationResponse(**result)
    return result
