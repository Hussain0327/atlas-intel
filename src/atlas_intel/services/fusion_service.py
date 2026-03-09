"""Multi-source fusion signal computations.

Each signal computes with whatever data is available. Missing components get
weight 0 and remaining weights are renormalized. A confidence field (0-1)
indicates how many input signals had data.
"""

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.ingestion.utils import utcnow
from atlas_intel.models.analyst_estimate import AnalystEstimate
from atlas_intel.models.analyst_grade import AnalystGrade
from atlas_intel.models.congress_trade import CongressTrade
from atlas_intel.models.earnings_transcript import EarningsTranscript
from atlas_intel.models.insider_trade import InsiderTrade
from atlas_intel.models.institutional_holding import InstitutionalHolding
from atlas_intel.models.macro_indicator import MacroIndicator
from atlas_intel.models.material_event import MaterialEvent
from atlas_intel.models.news_article import NewsArticle
from atlas_intel.models.patent import Patent
from atlas_intel.schemas.fusion import SignalComponent, SignalResponse


def _weighted_composite(
    components: list[SignalComponent],
    weights: dict[str, float],
) -> tuple[float | None, float]:
    """Compute weighted composite score with graceful degradation.

    Returns (score, confidence). Missing components are excluded and weights
    are renormalized across available components.
    """
    available = [c for c in components if c.has_data and c.score is not None]
    if not available:
        return None, 0.0

    total_weight = sum(weights.get(c.name, 0.0) for c in available)
    if total_weight == 0:
        return None, 0.0

    score = sum((c.score or 0.0) * weights.get(c.name, 0.0) / total_weight for c in available)
    confidence = len(available) / len(components)

    # Update component weights to reflect renormalized values
    for c in components:
        if c.has_data and c.score is not None:
            c.weight = weights.get(c.name, 0.0) / total_weight
        else:
            c.weight = 0.0

    return score, confidence


async def compute_sentiment_signal(session: AsyncSession, company_id: int) -> SignalResponse:
    """Composite Sentiment: transcript + insider ratio + analyst grades + news volume."""
    today = date.today()
    cutoff_90d = today - timedelta(days=90)
    cutoff_30d = today - timedelta(days=30)
    components: list[SignalComponent] = []

    # 1. Transcript sentiment: avg(positive - negative) from transcripts
    transcript_score: float | None = None
    sent_result = await session.execute(
        select(
            func.avg(EarningsTranscript.sentiment_positive - EarningsTranscript.sentiment_negative)
        ).where(EarningsTranscript.company_id == company_id)
    )
    avg_sent = sent_result.scalar_one_or_none()
    if avg_sent is not None:
        transcript_score = float(avg_sent)
    components.append(
        SignalComponent(
            name="transcript",
            score=transcript_score,
            has_data=transcript_score is not None,
        )
    )

    # 2. Insider score: buy_count / total_trades (last 90d), mapped to [-1, 1]
    insider_score: float | None = None
    buy_count = (
        await session.execute(
            select(func.count(InsiderTrade.id)).where(
                InsiderTrade.company_id == company_id,
                InsiderTrade.filing_date >= cutoff_90d,
                InsiderTrade.transaction_type.in_(["P-Purchase", "P"]),
            )
        )
    ).scalar() or 0
    total_insider = (
        await session.execute(
            select(func.count(InsiderTrade.id)).where(
                InsiderTrade.company_id == company_id,
                InsiderTrade.filing_date >= cutoff_90d,
            )
        )
    ).scalar() or 0
    if total_insider > 0:
        insider_score = (buy_count / total_insider) * 2 - 1  # Map [0,1] to [-1,1]
    components.append(
        SignalComponent(name="insider", score=insider_score, has_data=total_insider > 0)
    )

    # 3. Analyst score: upgrades / (upgrades + downgrades), mapped to [-1, 1]
    analyst_score: float | None = None
    upgrades = (
        await session.execute(
            select(func.count(AnalystGrade.id)).where(
                AnalystGrade.company_id == company_id,
                AnalystGrade.grade_date >= cutoff_90d,
                AnalystGrade.action == "upgrade",
            )
        )
    ).scalar() or 0
    downgrades = (
        await session.execute(
            select(func.count(AnalystGrade.id)).where(
                AnalystGrade.company_id == company_id,
                AnalystGrade.grade_date >= cutoff_90d,
                AnalystGrade.action == "downgrade",
            )
        )
    ).scalar() or 0
    total_grades = upgrades + downgrades
    if total_grades > 0:
        analyst_score = (upgrades / total_grades) * 2 - 1
    components.append(
        SignalComponent(name="analyst", score=analyst_score, has_data=total_grades > 0)
    )

    # 4. News score: 30d count / 90d avg — surge detection
    news_score: float | None = None
    news_30d = (
        await session.execute(
            select(func.count(NewsArticle.id)).where(
                NewsArticle.company_id == company_id,
                NewsArticle.published_at >= cutoff_30d,
            )
        )
    ).scalar() or 0
    news_90d = (
        await session.execute(
            select(func.count(NewsArticle.id)).where(
                NewsArticle.company_id == company_id,
                NewsArticle.published_at >= cutoff_90d,
            )
        )
    ).scalar() or 0
    if news_90d > 0:
        avg_30d = news_90d / 3  # 90d / 3 = expected 30d count
        if avg_30d > 0:
            ratio = news_30d / avg_30d
            news_score = min(max((ratio - 1) * 0.5, -1), 1)  # Normalize around 1.0
    components.append(SignalComponent(name="news", score=news_score, has_data=news_90d > 0))

    weights = {"transcript": 0.35, "analyst": 0.25, "insider": 0.25, "news": 0.15}
    score, confidence = _weighted_composite(components, weights)

    label = "neutral"
    if score is not None:
        if score > 0.2:
            label = "bullish"
        elif score < -0.2:
            label = "bearish"

    return SignalResponse(
        signal_type="sentiment",
        score=round(score, 4) if score is not None else None,
        label=label,
        confidence=round(confidence, 2),
        components=components,
        computed_at=utcnow(),
    )


async def compute_growth_signal(session: AsyncSession, company_id: int) -> SignalResponse:
    """Growth Signal: analyst revenue trajectory + patent velocity + macro tailwind."""
    today = date.today()
    components: list[SignalComponent] = []

    # 1. Revenue trajectory: latest vs 1yr-ago estimate
    revenue_score: float | None = None
    estimates = (
        (
            await session.execute(
                select(AnalystEstimate)
                .where(AnalystEstimate.company_id == company_id)
                .order_by(AnalystEstimate.estimate_date.desc())
                .limit(2)
            )
        )
        .scalars()
        .all()
    )
    has_rev = (
        len(estimates) >= 2
        and estimates[0].estimated_revenue_avg
        and estimates[1].estimated_revenue_avg
    )
    if has_rev:
        old_rev = float(estimates[1].estimated_revenue_avg or 0)
        new_rev = float(estimates[0].estimated_revenue_avg or 0)
        if old_rev > 0:
            pct_change = (new_rev - old_rev) / old_rev
            revenue_score = min(max(pct_change, -1), 1)  # Clamp to [-1, 1]
    components.append(
        SignalComponent(
            name="revenue_trajectory", score=revenue_score, has_data=revenue_score is not None
        )
    )

    # 2. Innovation velocity: patents last 12m vs prior 12m
    innovation_score: float | None = None
    cutoff_12m = today - timedelta(days=365)
    cutoff_24m = today - timedelta(days=730)
    patents_12m = (
        await session.execute(
            select(func.count(Patent.id)).where(
                Patent.company_id == company_id,
                Patent.grant_date >= cutoff_12m,
            )
        )
    ).scalar() or 0
    patents_prior = (
        await session.execute(
            select(func.count(Patent.id)).where(
                Patent.company_id == company_id,
                Patent.grant_date >= cutoff_24m,
                Patent.grant_date < cutoff_12m,
            )
        )
    ).scalar() or 0
    if patents_prior > 0:
        pct_change = (patents_12m - patents_prior) / patents_prior
        innovation_score = min(max(pct_change, -1), 1)
    elif patents_12m > 0:
        innovation_score = 0.5  # Some patents but no prior data
    components.append(
        SignalComponent(
            name="innovation_velocity",
            score=innovation_score,
            has_data=(patents_12m + patents_prior) > 0,
        )
    )

    # 3. Macro tailwind: GDP growth + inverse interest rate trend
    macro_score: float | None = None
    gdp_result = await session.execute(
        select(MacroIndicator.value)
        .where(MacroIndicator.series_id == "GDP")
        .order_by(MacroIndicator.observation_date.desc())
        .limit(2)
    )
    gdp_values = [row[0] for row in gdp_result.all() if row[0] is not None]

    rate_result = await session.execute(
        select(MacroIndicator.value)
        .where(MacroIndicator.series_id == "DFF")
        .order_by(MacroIndicator.observation_date.desc())
        .limit(2)
    )
    rate_values = [row[0] for row in rate_result.all() if row[0] is not None]

    has_macro = False
    gdp_component = 0.0
    rate_component = 0.0

    if len(gdp_values) >= 2 and float(gdp_values[1]) > 0:
        gdp_growth = (float(gdp_values[0]) - float(gdp_values[1])) / float(gdp_values[1])
        gdp_component = min(max(gdp_growth * 10, -1), 1)  # Scale up small %
        has_macro = True

    if len(rate_values) >= 2:
        rate_change = float(rate_values[0]) - float(rate_values[1])
        rate_component = min(max(-rate_change * 0.2, -1), 1)  # Falling rates = positive
        has_macro = True

    if has_macro:
        macro_score = (gdp_component + rate_component) / 2

    components.append(SignalComponent(name="macro_tailwind", score=macro_score, has_data=has_macro))

    weights = {"revenue_trajectory": 0.5, "innovation_velocity": 0.3, "macro_tailwind": 0.2}
    score, confidence = _weighted_composite(components, weights)

    # Map to [0, 1] range for growth (shift from [-1,1])
    if score is not None:
        score = (score + 1) / 2

    label = "stable"
    if score is not None:
        if score > 0.6:
            label = "accelerating"
        elif score < 0.4:
            label = "decelerating"

    return SignalResponse(
        signal_type="growth",
        score=round(score, 4) if score is not None else None,
        label=label,
        confidence=round(confidence, 2),
        components=components,
        computed_at=utcnow(),
    )


async def compute_risk_signal(session: AsyncSession, company_id: int) -> SignalResponse:
    """Risk Score: insider selling + material events + negative sentiment + macro headwinds."""
    today = date.today()
    cutoff_90d = today - timedelta(days=90)
    components: list[SignalComponent] = []

    # 1. Insider risk: sell_value / total_value over 90d
    insider_risk: float | None = None
    sell_count = (
        await session.execute(
            select(func.count(InsiderTrade.id)).where(
                InsiderTrade.company_id == company_id,
                InsiderTrade.filing_date >= cutoff_90d,
                InsiderTrade.transaction_type.in_(["S-Sale", "S"]),
            )
        )
    ).scalar() or 0
    total_insider = (
        await session.execute(
            select(func.count(InsiderTrade.id)).where(
                InsiderTrade.company_id == company_id,
                InsiderTrade.filing_date >= cutoff_90d,
            )
        )
    ).scalar() or 0
    if total_insider > 0:
        insider_risk = sell_count / total_insider
    components.append(
        SignalComponent(name="insider_risk", score=insider_risk, has_data=total_insider > 0)
    )

    # 2. Event risk: negative 8-K events in 90d
    negative_types = {
        "officer_change",
        "impairment",
        "cost_restructuring",
        "bankruptcy",
        "delisting",
    }
    event_count = (
        await session.execute(
            select(func.count(MaterialEvent.id)).where(
                MaterialEvent.company_id == company_id,
                MaterialEvent.event_date >= cutoff_90d,
                MaterialEvent.event_type.in_(negative_types),
            )
        )
    ).scalar() or 0
    total_events = (
        await session.execute(
            select(func.count(MaterialEvent.id)).where(
                MaterialEvent.company_id == company_id,
                MaterialEvent.event_date >= cutoff_90d,
            )
        )
    ).scalar() or 0
    event_risk: float | None = None
    if total_events > 0:
        event_risk = min(event_count / max(total_events, 1), 1.0)
    components.append(
        SignalComponent(name="event_risk", score=event_risk, has_data=total_events > 0)
    )

    # 3. Sentiment risk: negative transcript sentiment
    sentiment_risk: float | None = None
    neg_result = await session.execute(
        select(func.avg(EarningsTranscript.sentiment_negative)).where(
            EarningsTranscript.company_id == company_id
        )
    )
    avg_neg = neg_result.scalar_one_or_none()
    if avg_neg is not None:
        sentiment_risk = float(avg_neg)
    components.append(
        SignalComponent(
            name="sentiment_risk", score=sentiment_risk, has_data=sentiment_risk is not None
        )
    )

    # 4. Macro risk: rising rates + falling GDP
    macro_risk: float | None = None
    rate_result = await session.execute(
        select(MacroIndicator.value)
        .where(MacroIndicator.series_id == "DFF")
        .order_by(MacroIndicator.observation_date.desc())
        .limit(2)
    )
    rate_values = [row[0] for row in rate_result.all() if row[0] is not None]

    gdp_result = await session.execute(
        select(MacroIndicator.value)
        .where(MacroIndicator.series_id == "GDP")
        .order_by(MacroIndicator.observation_date.desc())
        .limit(2)
    )
    gdp_values = [row[0] for row in gdp_result.all() if row[0] is not None]

    has_macro = False
    rate_risk = 0.0
    gdp_risk = 0.0

    if len(rate_values) >= 2:
        rate_change = float(rate_values[0]) - float(rate_values[1])
        rate_risk = min(max(rate_change * 0.2, 0), 1)  # Rising rates = risk
        has_macro = True

    if len(gdp_values) >= 2 and float(gdp_values[1]) > 0:
        gdp_change = (float(gdp_values[0]) - float(gdp_values[1])) / float(gdp_values[1])
        gdp_risk = min(max(-gdp_change * 10, 0), 1)  # Falling GDP = risk
        has_macro = True

    if has_macro:
        macro_risk = (rate_risk + gdp_risk) / 2

    components.append(SignalComponent(name="macro_risk", score=macro_risk, has_data=has_macro))

    weights = {
        "insider_risk": 0.3,
        "event_risk": 0.25,
        "sentiment_risk": 0.25,
        "macro_risk": 0.2,
    }
    score, confidence = _weighted_composite(components, weights)

    label = "low"
    if score is not None:
        if score > 0.7:
            label = "high"
        elif score > 0.5:
            label = "elevated"
        elif score > 0.3:
            label = "moderate"

    return SignalResponse(
        signal_type="risk",
        score=round(score, 4) if score is not None else None,
        label=label,
        confidence=round(confidence, 2),
        components=components,
        computed_at=utcnow(),
    )


async def compute_smart_money_signal(session: AsyncSession, company_id: int) -> SignalResponse:
    """Smart Money: institutional flow + insider conviction + congress flow."""
    today = date.today()
    cutoff_90d = today - timedelta(days=90)
    cutoff_180d = today - timedelta(days=180)
    components: list[SignalComponent] = []

    # 1. Institutional flow: net share change across top holders
    inst_score: float | None = None
    inst_result = await session.execute(
        select(func.sum(InstitutionalHolding.change)).where(
            InstitutionalHolding.company_id == company_id,
            InstitutionalHolding.date_reported >= cutoff_90d,
        )
    )
    net_change = inst_result.scalar_one_or_none()
    total_shares = (
        await session.execute(
            select(func.sum(InstitutionalHolding.shares)).where(
                InstitutionalHolding.company_id == company_id
            )
        )
    ).scalar_one_or_none()

    if net_change is not None and total_shares and int(total_shares) > 0:
        ratio = int(net_change) / int(total_shares)
        inst_score = min(max(ratio * 100, -1), 1)  # Scale up
    components.append(
        SignalComponent(
            name="institutional_flow",
            score=inst_score,
            has_data=net_change is not None and total_shares is not None,
        )
    )

    # 2. Insider conviction: buy count in last 90d
    insider_buys = (
        await session.execute(
            select(func.count(InsiderTrade.id)).where(
                InsiderTrade.company_id == company_id,
                InsiderTrade.filing_date >= cutoff_90d,
                InsiderTrade.transaction_type.in_(["P-Purchase", "P"]),
            )
        )
    ).scalar() or 0
    insider_sells = (
        await session.execute(
            select(func.count(InsiderTrade.id)).where(
                InsiderTrade.company_id == company_id,
                InsiderTrade.filing_date >= cutoff_90d,
                InsiderTrade.transaction_type.in_(["S-Sale", "S"]),
            )
        )
    ).scalar() or 0
    total_insider = insider_buys + insider_sells
    insider_score: float | None = None
    if total_insider > 0:
        insider_score = (insider_buys / total_insider) * 2 - 1
    components.append(
        SignalComponent(name="insider_conviction", score=insider_score, has_data=total_insider > 0)
    )

    # 3. Congress flow: net buy vs sell (last 180d)
    congress_buys = (
        await session.execute(
            select(func.count(CongressTrade.id)).where(
                CongressTrade.company_id == company_id,
                CongressTrade.transaction_date >= cutoff_180d,
                CongressTrade.transaction_type == "purchase",
            )
        )
    ).scalar() or 0
    congress_sells = (
        await session.execute(
            select(func.count(CongressTrade.id)).where(
                CongressTrade.company_id == company_id,
                CongressTrade.transaction_date >= cutoff_180d,
                CongressTrade.transaction_type == "sale",
            )
        )
    ).scalar() or 0
    total_congress = congress_buys + congress_sells
    congress_score: float | None = None
    if total_congress > 0:
        congress_score = (congress_buys / total_congress) * 2 - 1
    components.append(
        SignalComponent(name="congress_flow", score=congress_score, has_data=total_congress > 0)
    )

    weights = {
        "institutional_flow": 0.4,
        "insider_conviction": 0.35,
        "congress_flow": 0.25,
    }
    score, confidence = _weighted_composite(components, weights)

    label = "neutral"
    if score is not None:
        if score > 0.5:
            label = "strong_buy"
        elif score > 0.2:
            label = "buy"
        elif score < -0.5:
            label = "strong_sell"
        elif score < -0.2:
            label = "sell"

    return SignalResponse(
        signal_type="smart_money",
        score=round(score, 4) if score is not None else None,
        label=label,
        confidence=round(confidence, 2),
        components=components,
        computed_at=utcnow(),
    )
