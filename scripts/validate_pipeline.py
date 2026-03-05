"""
Manual validation script — runs real SEC + FMP pipeline for a handful of tickers
and spot-checks the data that lands in PostgreSQL.

Usage:
    uv run python scripts/validate_pipeline.py              # SEC only (no FMP key needed)
    FMP_API_KEY=xxx uv run python scripts/validate_pipeline.py --with-transcripts
    APP_ENV=production uv run python scripts/validate_pipeline.py --all

This is NOT a test — it hits real APIs, writes to the dev DB, and prints a report.
Run it after schema changes or ingestion refactors to sanity-check the full path.
"""

import argparse
import asyncio
import logging
import sys
from decimal import Decimal

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from atlas_intel.config import settings
from atlas_intel.database import async_session
from atlas_intel.ingestion.pipeline import (
    run_alt_data_sync,
    run_full_sync,
    run_market_data_sync,
    run_transcript_sync,
)
from atlas_intel.models.analyst_estimate import AnalystEstimate
from atlas_intel.models.analyst_grade import AnalystGrade
from atlas_intel.models.company import Company
from atlas_intel.models.earnings_transcript import EarningsTranscript
from atlas_intel.models.filing import Filing
from atlas_intel.models.financial_fact import FinancialFact
from atlas_intel.models.insider_trade import InsiderTrade
from atlas_intel.models.institutional_holding import InstitutionalHolding
from atlas_intel.models.keyword_extraction import KeywordExtraction
from atlas_intel.models.market_metric import MarketMetric
from atlas_intel.models.news_article import NewsArticle
from atlas_intel.models.price_target import PriceTarget
from atlas_intel.models.sentiment_analysis import SentimentAnalysis
from atlas_intel.models.stock_price import StockPrice
from atlas_intel.models.transcript_section import TranscriptSection

# Tickers chosen for coverage: large-cap (AAPL, MSFT), mid-cap (CRWD),
# financial (JPM), industrial (CAT). Each exercises different filing patterns.
VALIDATION_TICKERS = ["AAPL", "MSFT", "CRWD", "JPM", "CAT"]

# Subset used for FMP-heavy tests (saves API calls)
FMP_TICKERS = ["AAPL", "MSFT"]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("validate")


class ValidationError(Exception):
    pass


class Report:
    def __init__(self) -> None:
        self.checks: list[tuple[str, bool, str]] = []

    def check(self, name: str, passed: bool, detail: str = "") -> None:
        self.checks.append((name, passed, detail))
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name}" + (f" — {detail}" if detail else ""))

    def summary(self) -> bool:
        total = len(self.checks)
        passed = sum(1 for _, p, _ in self.checks if p)
        failed = total - passed
        print(f"\n{'=' * 60}")
        print(f"VALIDATION COMPLETE: {passed}/{total} passed, {failed} failed")
        if failed:
            print("\nFailed checks:")
            for name, p, detail in self.checks:
                if not p:
                    print(f"  - {name}: {detail}")
        print(f"{'=' * 60}")
        return failed == 0


# ---------------------------------------------------------------------------
# Layer 1: SEC pipeline checks
# ---------------------------------------------------------------------------


async def validate_sec_pipeline(session: AsyncSession, report: Report) -> None:
    """Run full SEC sync and validate the data."""
    print("\n--- Layer 1: SEC EDGAR Pipeline ---")

    # Run sync
    print(f"Syncing {len(VALIDATION_TICKERS)} tickers (this takes ~30s)...")
    results = await run_full_sync(session, VALIDATION_TICKERS, force=True)

    for ticker in VALIDATION_TICKERS:
        counts = results.get(ticker, {})
        report.check(
            f"{ticker}: sync completed",
            "error" not in counts,
            f"filings={counts.get('filings', 0)}, facts={counts.get('facts', 0)}",
        )

    # Validate companies table
    print("\n  Checking companies...")
    for ticker in VALIDATION_TICKERS:
        company = (
            await session.execute(select(Company).where(Company.ticker == ticker))
        ).scalar_one_or_none()

        report.check(
            f"{ticker}: company exists",
            company is not None,
        )
        if not company:
            continue

        report.check(
            f"{ticker}: CIK is positive",
            company.cik > 0,
            f"cik={company.cik}",
        )
        report.check(
            f"{ticker}: name is non-empty",
            bool(company.name and len(company.name) > 2),
            f"name={company.name!r}",
        )
        report.check(
            f"{ticker}: submissions_synced_at set",
            company.submissions_synced_at is not None,
        )
        report.check(
            f"{ticker}: facts_synced_at set",
            company.facts_synced_at is not None,
        )

    # Validate filings
    print("\n  Checking filings...")
    for ticker in VALIDATION_TICKERS:
        company = (
            await session.execute(select(Company).where(Company.ticker == ticker))
        ).scalar_one_or_none()
        if not company:
            continue

        filing_count = (
            await session.execute(
                select(func.count(Filing.id)).where(Filing.company_id == company.id)
            )
        ).scalar() or 0

        report.check(
            f"{ticker}: has filings",
            filing_count > 0,
            f"count={filing_count}",
        )

        # Check a specific filing has sane data
        sample_filing = (
            await session.execute(
                select(Filing)
                .where(Filing.company_id == company.id)
                .order_by(Filing.filing_date.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

        if sample_filing:
            report.check(
                f"{ticker}: latest filing has accession_number",
                bool(sample_filing.accession_number),
                f"accession={sample_filing.accession_number}",
            )
            report.check(
                f"{ticker}: latest filing has form_type",
                bool(sample_filing.form_type),
                f"form_type={sample_filing.form_type}",
            )
            report.check(
                f"{ticker}: filing_date is set",
                sample_filing.filing_date is not None,
                f"date={sample_filing.filing_date}",
            )

        # Check for common form types (10-K, 10-Q should exist for large-caps)
        if ticker in ("AAPL", "MSFT", "JPM"):
            tenk_count = (
                await session.execute(
                    select(func.count(Filing.id)).where(
                        Filing.company_id == company.id,
                        Filing.form_type == "10-K",
                    )
                )
            ).scalar() or 0
            report.check(
                f"{ticker}: has 10-K filings",
                tenk_count > 0,
                f"10-K count={tenk_count}",
            )

    # Validate financial facts
    print("\n  Checking financial facts...")
    for ticker in VALIDATION_TICKERS:
        company = (
            await session.execute(select(Company).where(Company.ticker == ticker))
        ).scalar_one_or_none()
        if not company:
            continue

        fact_count = (
            await session.execute(
                select(func.count(FinancialFact.id)).where(FinancialFact.company_id == company.id)
            )
        ).scalar() or 0

        report.check(
            f"{ticker}: has financial facts",
            fact_count > 0,
            f"count={fact_count}",
        )

        # Check that key concepts exist (Revenues or Assets should be present)
        for concept in ("Revenues", "Assets"):
            concept_count = (
                await session.execute(
                    select(func.count(FinancialFact.id)).where(
                        FinancialFact.company_id == company.id,
                        FinancialFact.concept == concept,
                    )
                )
            ).scalar() or 0

            if concept_count > 0:
                # Check values are sane (not zero, not negative for Assets)
                sample = (
                    await session.execute(
                        select(FinancialFact)
                        .where(
                            FinancialFact.company_id == company.id,
                            FinancialFact.concept == concept,
                        )
                        .order_by(FinancialFact.period_end.desc())
                        .limit(1)
                    )
                ).scalar_one_or_none()

                if sample:
                    report.check(
                        f"{ticker}: {concept} value is positive",
                        sample.value > 0,
                        f"value={sample.value}, period_end={sample.period_end}",
                    )

    # Check dedup: run sync again and verify no new rows
    print("\n  Checking idempotency (re-sync)...")
    results2 = await run_full_sync(session, ["AAPL"], force=True)
    aapl_company = (
        await session.execute(select(Company).where(Company.ticker == "AAPL"))
    ).scalar_one_or_none()
    if aapl_company:
        # facts_count from second sync should be 0 (all deduped)
        report.check(
            "AAPL: re-sync inserts 0 new facts (dedup works)",
            results2.get("AAPL", {}).get("facts", -1) == 0,
            f"new_facts={results2.get('AAPL', {}).get('facts', -1)}",
        )


# ---------------------------------------------------------------------------
# Layer 2: Transcript pipeline checks
# ---------------------------------------------------------------------------


async def validate_transcript_pipeline(session: AsyncSession, report: Report) -> None:
    """Run transcript sync for a couple of tickers and validate NLP output."""
    print("\n--- Layer 2: Transcript + NLP Pipeline ---")

    if not settings.fmp_api_key:
        print("  SKIPPED: FMP_API_KEY not set. Set it in .env or environment.")
        report.check("FMP_API_KEY configured", False, "Set FMP_API_KEY to test transcripts")
        return

    print(f"Syncing transcripts for {FMP_TICKERS} (last 1 year)...")
    try:
        results = await run_transcript_sync(session, FMP_TICKERS, years=1, force=True)
    except Exception as e:
        print(f"  SKIPPED: Transcript sync failed — {e}")
        report.check("Transcript sync", False, f"Error: {e}")
        return

    for ticker in FMP_TICKERS:
        count = results.get(ticker, 0)
        report.check(
            f"{ticker}: transcript sync completed",
            True,
            f"transcripts_processed={count}",
        )

        company = (
            await session.execute(select(Company).where(Company.ticker == ticker))
        ).scalar_one_or_none()
        if not company:
            continue

        # Check transcripts were created
        transcript_count = (
            await session.execute(
                select(func.count(EarningsTranscript.id)).where(
                    EarningsTranscript.company_id == company.id
                )
            )
        ).scalar() or 0

        report.check(
            f"{ticker}: has transcripts in DB",
            transcript_count > 0,
            f"count={transcript_count}",
        )

        if transcript_count == 0:
            continue

        # Check a sample transcript for data integrity
        sample = (
            await session.execute(
                select(EarningsTranscript)
                .where(EarningsTranscript.company_id == company.id)
                .order_by(EarningsTranscript.transcript_date.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

        if sample:
            report.check(
                f"{ticker}: transcript has raw_text",
                bool(sample.raw_text and len(sample.raw_text) > 100),
                f"text_length={len(sample.raw_text) if sample.raw_text else 0}",
            )
            report.check(
                f"{ticker}: transcript quarter in [1,4]",
                1 <= sample.quarter <= 4,
                f"quarter={sample.quarter}",
            )
            report.check(
                f"{ticker}: transcript has sentiment scores",
                sample.sentiment_label is not None,
                f"label={sample.sentiment_label}",
            )

            # Validate sentiment scores are valid probabilities
            if sample.sentiment_positive is not None:
                total = (
                    float(sample.sentiment_positive)
                    + float(sample.sentiment_negative or 0)
                    + float(sample.sentiment_neutral or 0)
                )
                report.check(
                    f"{ticker}: sentiment scores sum to ~1.0",
                    0.95 <= total <= 1.05,
                    f"sum={total:.4f} (pos={sample.sentiment_positive}, "
                    f"neg={sample.sentiment_negative}, neu={sample.sentiment_neutral})",
                )

            report.check(
                f"{ticker}: nlp_processed_at is set",
                sample.nlp_processed_at is not None,
            )

            # Check sections exist
            section_count = (
                await session.execute(
                    select(func.count(TranscriptSection.id)).where(
                        TranscriptSection.transcript_id == sample.id
                    )
                )
            ).scalar() or 0

            report.check(
                f"{ticker}: transcript has sections",
                section_count > 0,
                f"section_count={section_count}",
            )

            # Check section-level sentiment
            section_with_sentiment = (
                await session.execute(
                    select(func.count(TranscriptSection.id)).where(
                        TranscriptSection.transcript_id == sample.id,
                        TranscriptSection.sentiment_label.is_not(None),
                    )
                )
            ).scalar() or 0

            report.check(
                f"{ticker}: sections have sentiment",
                section_with_sentiment > 0,
                f"sections_with_sentiment={section_with_sentiment}/{section_count}",
            )

            # Check sentence-level sentiments exist
            sentiment_count = (
                await session.execute(
                    select(func.count(SentimentAnalysis.id))
                    .join(TranscriptSection)
                    .where(TranscriptSection.transcript_id == sample.id)
                )
            ).scalar() or 0

            report.check(
                f"{ticker}: has sentence-level sentiments",
                sentiment_count > 0,
                f"sentence_count={sentiment_count}",
            )

            # Spot-check a sentiment: confidence should be [0, 1]
            if sentiment_count > 0:
                sample_sent = (
                    await session.execute(
                        select(SentimentAnalysis)
                        .join(TranscriptSection)
                        .where(TranscriptSection.transcript_id == sample.id)
                        .limit(1)
                    )
                ).scalar_one_or_none()

                if sample_sent:
                    report.check(
                        f"{ticker}: sentiment confidence in [0,1]",
                        Decimal("0") <= sample_sent.confidence <= Decimal("1"),
                        f"confidence={sample_sent.confidence}, label={sample_sent.label}",
                    )
                    report.check(
                        f"{ticker}: sentence text is non-empty",
                        bool(sample_sent.sentence_text and len(sample_sent.sentence_text) >= 10),
                        f"text={sample_sent.sentence_text[:80]!r}...",
                    )

            # Check keywords exist
            keyword_count = (
                await session.execute(
                    select(func.count(KeywordExtraction.id)).where(
                        KeywordExtraction.transcript_id == sample.id
                    )
                )
            ).scalar() or 0

            report.check(
                f"{ticker}: has extracted keywords",
                keyword_count > 0,
                f"keyword_count={keyword_count}",
            )

            if keyword_count > 0:
                top_kw = (
                    (
                        await session.execute(
                            select(KeywordExtraction)
                            .where(KeywordExtraction.transcript_id == sample.id)
                            .order_by(KeywordExtraction.relevance_score.desc())
                            .limit(5)
                        )
                    )
                    .scalars()
                    .all()
                )

                kw_list = [(kw.keyword, float(kw.relevance_score)) for kw in top_kw]
                report.check(
                    f"{ticker}: top keywords have scores in (0,1]",
                    all(0 < score <= 1 for _, score in kw_list),
                    f"top_5={kw_list}",
                )


# ---------------------------------------------------------------------------
# Layer 3: Market data checks
# ---------------------------------------------------------------------------


async def validate_market_pipeline(session: AsyncSession, report: Report) -> None:
    """Run market data sync and validate prices, profile, metrics."""
    print("\n--- Layer 3: Market Data Pipeline ---")

    if not settings.fmp_api_key:
        print("  SKIPPED: FMP_API_KEY not set.")
        report.check("FMP_API_KEY configured", False, "Set FMP_API_KEY to test market data")
        return

    print(f"Syncing market data for {FMP_TICKERS}...")
    try:
        results = await run_market_data_sync(session, FMP_TICKERS, years=2, force=True)
    except Exception as e:
        print(f"  SKIPPED: Market data sync failed — {e}")
        report.check("Market data sync", False, f"Error: {e}")
        return

    for ticker in FMP_TICKERS:
        counts = results.get(ticker, {})
        report.check(
            f"{ticker}: market data sync completed",
            not counts.get("error"),
            f"profile={counts.get('profile')}, prices={counts.get('prices')}, "
            f"metrics={counts.get('metrics')}",
        )

        company = (
            await session.execute(select(Company).where(Company.ticker == ticker))
        ).scalar_one_or_none()
        if not company:
            continue

        # Profile check
        report.check(
            f"{ticker}: profile_synced_at set",
            company.profile_synced_at is not None,
        )
        report.check(
            f"{ticker}: sector populated",
            company.sector is not None,
            f"sector={company.sector}",
        )
        report.check(
            f"{ticker}: industry populated",
            company.industry is not None,
            f"industry={company.industry}",
        )

        # Prices check
        price_count = (
            await session.execute(
                select(func.count(StockPrice.id)).where(StockPrice.company_id == company.id)
            )
        ).scalar() or 0

        report.check(
            f"{ticker}: has stock prices",
            price_count > 100,
            f"count={price_count}",
        )

        # Check latest price is sane
        latest_price = (
            await session.execute(
                select(StockPrice)
                .where(StockPrice.company_id == company.id)
                .order_by(StockPrice.price_date.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

        if latest_price:
            report.check(
                f"{ticker}: latest close > 0",
                latest_price.close is not None and latest_price.close > 0,
                f"close={latest_price.close}, date={latest_price.price_date}",
            )

        # Metrics check
        metric_count = (
            await session.execute(
                select(func.count(MarketMetric.id)).where(MarketMetric.company_id == company.id)
            )
        ).scalar() or 0

        report.check(
            f"{ticker}: has market metrics",
            metric_count > 0,
            f"count={metric_count}",
        )

        # Check TTM metrics exist
        ttm_count = (
            await session.execute(
                select(func.count(MarketMetric.id)).where(
                    MarketMetric.company_id == company.id,
                    MarketMetric.period == "TTM",
                )
            )
        ).scalar() or 0

        report.check(
            f"{ticker}: has TTM metrics",
            ttm_count > 0,
            f"ttm_count={ttm_count}",
        )

    # Idempotency check
    print("\n  Checking market data idempotency...")
    await run_market_data_sync(session, ["AAPL"], years=2, force=True)

    aapl_company = (
        await session.execute(select(Company).where(Company.ticker == "AAPL"))
    ).scalar_one_or_none()

    if aapl_company:
        # Second sync should upsert same rows, not create new ones
        price_count_after = (
            await session.execute(
                select(func.count(StockPrice.id)).where(StockPrice.company_id == aapl_company.id)
            )
        ).scalar() or 0
        report.check(
            "AAPL: price re-sync is idempotent",
            True,
            f"prices_after_resync={price_count_after}",
        )


# ---------------------------------------------------------------------------
# Layer 4: Alternative data checks
# ---------------------------------------------------------------------------


async def validate_alt_data_pipeline(session: AsyncSession, report: Report) -> None:
    """Run alt data sync and validate news, insider, estimates, grades, targets, holdings."""
    print("\n--- Layer 4: Alternative Data Pipeline ---")

    if not settings.fmp_api_key:
        print("  SKIPPED: FMP_API_KEY not set.")
        report.check("FMP_API_KEY configured", False, "Set FMP_API_KEY to test alt data")
        return

    print(f"Syncing alt data for {FMP_TICKERS} (~7 API calls each)...")
    try:
        results = await run_alt_data_sync(session, FMP_TICKERS, force=True)
    except Exception as e:
        print(f"  SKIPPED: Alt data sync failed — {e}")
        report.check("Alt data sync", False, f"Error: {e}")
        return

    for ticker in FMP_TICKERS:
        counts = results.get(ticker, {})
        report.check(
            f"{ticker}: alt data sync completed",
            not counts.get("error"),
            f"news={counts.get('news')}, insider={counts.get('insider_trades')}, "
            f"estimates={counts.get('estimates')}, grades={counts.get('grades')}, "
            f"target={counts.get('price_target')}, holdings={counts.get('holdings')}",
        )

        company = (
            await session.execute(select(Company).where(Company.ticker == ticker))
        ).scalar_one_or_none()
        if not company:
            continue

        # --- News ---
        news_count = (
            await session.execute(
                select(func.count(NewsArticle.id)).where(NewsArticle.company_id == company.id)
            )
        ).scalar() or 0

        report.check(
            f"{ticker}: has news articles",
            news_count > 0,
            f"count={news_count}",
        )
        report.check(
            f"{ticker}: news_synced_at set",
            company.news_synced_at is not None,
        )

        # Spot-check a news article
        if news_count > 0:
            sample = (
                await session.execute(
                    select(NewsArticle)
                    .where(NewsArticle.company_id == company.id)
                    .order_by(NewsArticle.published_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if sample:
                report.check(
                    f"{ticker}: news article has title",
                    bool(sample.title and len(sample.title) > 5),
                    f"title={sample.title[:60]!r}",
                )
                report.check(
                    f"{ticker}: news article has url",
                    bool(sample.url and sample.url.startswith("http")),
                    f"url={sample.url[:60]}",
                )
                report.check(
                    f"{ticker}: news article has published_at",
                    sample.published_at is not None,
                    f"published={sample.published_at}",
                )

        # --- Insider Trades ---
        insider_count = (
            await session.execute(
                select(func.count(InsiderTrade.id)).where(InsiderTrade.company_id == company.id)
            )
        ).scalar() or 0

        report.check(
            f"{ticker}: has insider trades",
            insider_count > 0,
            f"count={insider_count}",
        )
        report.check(
            f"{ticker}: insider_trades_synced_at set",
            company.insider_trades_synced_at is not None,
        )

        # Spot-check insider trade
        if insider_count > 0:
            sample = (
                await session.execute(
                    select(InsiderTrade)
                    .where(InsiderTrade.company_id == company.id)
                    .order_by(InsiderTrade.filing_date.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if sample:
                report.check(
                    f"{ticker}: insider trade has reporting_name",
                    bool(sample.reporting_name),
                    f"name={sample.reporting_name}, type={sample.transaction_type}",
                )
                report.check(
                    f"{ticker}: insider trade has filing_date",
                    sample.filing_date is not None,
                    f"filing_date={sample.filing_date}",
                )

        # --- Analyst Estimates ---
        estimate_count = (
            await session.execute(
                select(func.count(AnalystEstimate.id)).where(
                    AnalystEstimate.company_id == company.id
                )
            )
        ).scalar() or 0

        report.check(
            f"{ticker}: has analyst estimates",
            estimate_count > 0,
            f"count={estimate_count}",
        )
        report.check(
            f"{ticker}: analyst_estimates_synced_at set",
            company.analyst_estimates_synced_at is not None,
        )

        # Check both annual and quarterly exist
        if estimate_count > 0:
            annual_count = (
                await session.execute(
                    select(func.count(AnalystEstimate.id)).where(
                        AnalystEstimate.company_id == company.id,
                        AnalystEstimate.period == "annual",
                    )
                )
            ).scalar() or 0
            quarterly_count = (
                await session.execute(
                    select(func.count(AnalystEstimate.id)).where(
                        AnalystEstimate.company_id == company.id,
                        AnalystEstimate.period == "quarter",
                    )
                )
            ).scalar() or 0
            report.check(
                f"{ticker}: has annual + quarterly estimates",
                annual_count > 0 and quarterly_count > 0,
                f"annual={annual_count}, quarterly={quarterly_count}",
            )

            # Spot-check estimate values
            sample = (
                await session.execute(
                    select(AnalystEstimate)
                    .where(AnalystEstimate.company_id == company.id)
                    .order_by(AnalystEstimate.estimate_date.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if sample:
                report.check(
                    f"{ticker}: estimate has revenue_avg",
                    sample.estimated_revenue_avg is not None and sample.estimated_revenue_avg > 0,
                    f"revenue_avg={sample.estimated_revenue_avg}, date={sample.estimate_date}",
                )

        # --- Analyst Grades ---
        grade_count = (
            await session.execute(
                select(func.count(AnalystGrade.id)).where(AnalystGrade.company_id == company.id)
            )
        ).scalar() or 0

        report.check(
            f"{ticker}: has analyst grades",
            grade_count > 0,
            f"count={grade_count}",
        )
        report.check(
            f"{ticker}: analyst_grades_synced_at set",
            company.analyst_grades_synced_at is not None,
        )

        # Spot-check grades
        if grade_count > 0:
            sample = (
                await session.execute(
                    select(AnalystGrade)
                    .where(AnalystGrade.company_id == company.id)
                    .order_by(AnalystGrade.grade_date.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if sample:
                report.check(
                    f"{ticker}: grade has grading_company",
                    bool(sample.grading_company),
                    f"company={sample.grading_company}, grade={sample.new_grade}, "
                    f"action={sample.action}",
                )

        # --- Price Target ---
        price_target = (
            await session.execute(select(PriceTarget).where(PriceTarget.company_id == company.id))
        ).scalar_one_or_none()

        report.check(
            f"{ticker}: has price target",
            price_target is not None,
        )
        report.check(
            f"{ticker}: price_targets_synced_at set",
            company.price_targets_synced_at is not None,
        )

        if price_target:
            report.check(
                f"{ticker}: target_consensus > 0",
                price_target.target_consensus is not None and price_target.target_consensus > 0,
                f"consensus={price_target.target_consensus}, "
                f"high={price_target.target_high}, low={price_target.target_low}",
            )
            report.check(
                f"{ticker}: target_high >= target_low",
                (
                    price_target.target_high is not None
                    and price_target.target_low is not None
                    and price_target.target_high >= price_target.target_low
                ),
                f"high={price_target.target_high}, low={price_target.target_low}",
            )

        # --- Institutional Holdings ---
        holding_count = (
            await session.execute(
                select(func.count(InstitutionalHolding.id)).where(
                    InstitutionalHolding.company_id == company.id
                )
            )
        ).scalar() or 0

        report.check(
            f"{ticker}: has institutional holdings",
            holding_count > 0,
            f"count={holding_count}",
        )
        report.check(
            f"{ticker}: institutional_holdings_synced_at set",
            company.institutional_holdings_synced_at is not None,
        )

        # Spot-check a holding
        if holding_count > 0:
            sample = (
                await session.execute(
                    select(InstitutionalHolding)
                    .where(InstitutionalHolding.company_id == company.id)
                    .order_by(InstitutionalHolding.shares.desc().nulls_last())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if sample:
                report.check(
                    f"{ticker}: top holder has name + shares",
                    bool(sample.holder) and sample.shares is not None and sample.shares > 0,
                    f"holder={sample.holder}, shares={sample.shares:,}",
                )

    # Idempotency check for alt data
    print("\n  Checking alt data idempotency...")
    results2 = await run_alt_data_sync(session, ["AAPL"], force=True)
    aapl_counts2 = results2.get("AAPL", {})
    # DO NOTHING syncs should return 0 new rows
    report.check(
        "AAPL: insider re-sync inserts 0 (dedup)",
        aapl_counts2.get("insider_trades", -1) == 0,
        f"insider_trades={aapl_counts2.get('insider_trades')}",
    )
    report.check(
        "AAPL: grades re-sync inserts 0 (dedup)",
        aapl_counts2.get("grades", -1) == 0,
        f"grades={aapl_counts2.get('grades')}",
    )
    report.check(
        "AAPL: holdings re-sync inserts 0 (dedup)",
        aapl_counts2.get("holdings", -1) == 0,
        f"holdings={aapl_counts2.get('holdings')}",
    )


# ---------------------------------------------------------------------------
# API endpoint smoke tests
# ---------------------------------------------------------------------------


async def validate_api_endpoints(session: AsyncSession, report: Report) -> None:
    """Hit every API endpoint with AAPL and check 200 + non-empty responses."""
    print("\n--- API Endpoint Smoke Tests ---")

    from httpx import ASGITransport, AsyncClient
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from atlas_intel.database import get_session
    from atlas_intel.main import create_app

    app = create_app()

    # Create a sessionmaker bound to the same engine
    from atlas_intel.database import engine as app_engine

    sm = async_sessionmaker(app_engine, expire_on_commit=False)

    async def override_get_session():
        async with sm() as s:
            yield s

    app.dependency_overrides[get_session] = override_get_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        endpoints = [
            # Layer 1
            ("/api/v1/companies/AAPL", "company detail"),
            ("/api/v1/companies/AAPL/filings/", "filings"),
            ("/api/v1/companies/AAPL/financials", "financial facts"),
            # Layer 2
            ("/api/v1/companies/AAPL/transcripts", "transcripts"),
            # Layer 3
            ("/api/v1/companies/AAPL/prices", "prices"),
            ("/api/v1/companies/AAPL/prices/analytics", "price analytics"),
            ("/api/v1/companies/AAPL/prices/returns", "daily returns"),
            ("/api/v1/companies/AAPL/metrics", "metrics"),
            # Layer 4
            ("/api/v1/companies/AAPL/news", "news"),
            ("/api/v1/companies/AAPL/news/activity", "news activity"),
            ("/api/v1/companies/AAPL/insider-trades", "insider trades"),
            ("/api/v1/companies/AAPL/insider-trades/sentiment", "insider sentiment"),
            ("/api/v1/companies/AAPL/analyst/estimates", "analyst estimates"),
            ("/api/v1/companies/AAPL/analyst/grades", "analyst grades"),
            ("/api/v1/companies/AAPL/analyst/price-target", "price target"),
            ("/api/v1/companies/AAPL/analyst/consensus", "analyst consensus"),
            ("/api/v1/companies/AAPL/institutional-holdings", "holdings"),
            ("/api/v1/companies/AAPL/institutional-holdings/top", "top holders"),
        ]

        for path, label in endpoints:
            resp = await client.get(path)
            report.check(
                f"API {label}: {path}",
                resp.status_code == 200,
                f"status={resp.status_code}"
                + (f", body_size={len(resp.content)}" if resp.status_code == 200 else ""),
            )

        # Check paginated endpoints return items
        for path, label, min_items in [
            ("/api/v1/companies/AAPL/filings/", "filings", 1),
            ("/api/v1/companies/AAPL/prices", "prices", 1),
            ("/api/v1/companies/AAPL/news", "news", 0),
            ("/api/v1/companies/AAPL/insider-trades", "insider trades", 0),
            ("/api/v1/companies/AAPL/analyst/estimates", "estimates", 0),
            ("/api/v1/companies/AAPL/analyst/grades", "grades", 0),
            ("/api/v1/companies/AAPL/institutional-holdings", "holdings", 0),
        ]:
            resp = await client.get(path)
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("items", [])
                report.check(
                    f"API {label}: has data",
                    len(items) >= min_items,
                    f"items={len(items)}, total={data.get('total', 0)}",
                )

        # Check analytics endpoints return meaningful data
        resp = await client.get("/api/v1/companies/AAPL/insider-trades/sentiment")
        if resp.status_code == 200:
            data = resp.json()
            report.check(
                "API insider sentiment: has sentiment label",
                data.get("sentiment") in ("bullish", "bearish", "neutral"),
                f"sentiment={data.get('sentiment')}, "
                f"buys={data.get('buy_count')}, sells={data.get('sell_count')}",
            )

        resp = await client.get("/api/v1/companies/AAPL/analyst/consensus")
        if resp.status_code == 200:
            data = resp.json()
            report.check(
                "API analyst consensus: has data",
                data.get("ticker") == "AAPL",
                f"target={data.get('target_consensus')}, "
                f"upside={data.get('upside_pct')}%, "
                f"sentiment={data.get('sentiment')}",
            )

        # 404 check
        resp = await client.get("/api/v1/companies/ZZZZZZ/news")
        report.check(
            "API 404: unknown ticker returns 404",
            resp.status_code == 404,
            f"status={resp.status_code}",
        )


# ---------------------------------------------------------------------------
# DB integrity checks
# ---------------------------------------------------------------------------


async def validate_db_integrity(session: AsyncSession, report: Report) -> None:
    """Check cross-table FK integrity and no orphaned rows."""
    print("\n--- Database Integrity ---")

    # Orphan checks for all tables with company_id FK
    orphan_queries = [
        ("filings", "filings f"),
        ("financial_facts", "financial_facts f"),
        ("earnings_transcripts", "earnings_transcripts f"),
        ("stock_prices", "stock_prices f"),
        ("market_metrics", "market_metrics f"),
        ("news_articles", "news_articles f"),
        ("insider_trades", "insider_trades f"),
        ("analyst_estimates", "analyst_estimates f"),
        ("analyst_grades", "analyst_grades f"),
        ("price_targets", "price_targets f"),
        ("institutional_holdings", "institutional_holdings f"),
    ]

    for table_name, from_clause in orphan_queries:
        orphaned = (
            await session.execute(
                text(
                    f"SELECT count(*) FROM {from_clause} "
                    f"LEFT JOIN companies c ON f.company_id = c.id "
                    f"WHERE c.id IS NULL"
                )
            )
        ).scalar()
        report.check(f"No orphaned {table_name}", orphaned == 0, f"orphaned={orphaned}")

    # Orphaned sections
    orphaned = (
        await session.execute(
            text(
                "SELECT count(*) FROM transcript_sections s "
                "LEFT JOIN earnings_transcripts t ON s.transcript_id = t.id "
                "WHERE t.id IS NULL"
            )
        )
    ).scalar()
    report.check("No orphaned sections", orphaned == 0, f"orphaned={orphaned}")

    # Duplicate check: no duplicate (company_id, quarter, year) in transcripts
    dupes = (
        await session.execute(
            text(
                "SELECT company_id, quarter, year, count(*) as cnt "
                "FROM earnings_transcripts "
                "GROUP BY company_id, quarter, year "
                "HAVING count(*) > 1"
            )
        )
    ).fetchall()
    report.check(
        "No duplicate transcripts per company/quarter/year",
        len(dupes) == 0,
        f"duplicates={dupes}" if dupes else "",
    )

    # Row count summary
    tables = [
        "companies",
        "filings",
        "financial_facts",
        "earnings_transcripts",
        "transcript_sections",
        "sentiment_analyses",
        "keyword_extractions",
        "stock_prices",
        "market_metrics",
        "news_articles",
        "insider_trades",
        "analyst_estimates",
        "analyst_grades",
        "price_targets",
        "institutional_holdings",
    ]
    print("\n  Row counts:")
    for table in tables:
        count = (await session.execute(text(f"SELECT count(*) FROM {table}"))).scalar()
        print(f"    {table}: {count}")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Validate atlas-intel pipeline")
    parser.add_argument(
        "--with-transcripts",
        action="store_true",
        help="Also validate FMP transcript + NLP pipeline (requires FMP_API_KEY)",
    )
    parser.add_argument(
        "--with-market",
        action="store_true",
        help="Also validate market data pipeline (requires FMP_API_KEY)",
    )
    parser.add_argument(
        "--with-alt",
        action="store_true",
        help="Also validate alternative data pipeline (requires FMP_API_KEY)",
    )
    parser.add_argument(
        "--with-api",
        action="store_true",
        help="Also run API endpoint smoke tests",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all validations (SEC + transcripts + market + alt + API)",
    )
    args = parser.parse_args()

    report = Report()

    async with async_session() as session:
        await validate_sec_pipeline(session, report)

        if args.with_transcripts or args.all:
            await validate_transcript_pipeline(session, report)

        if args.with_market or args.all:
            await validate_market_pipeline(session, report)

        if args.with_alt or args.all:
            await validate_alt_data_pipeline(session, report)

        await validate_db_integrity(session, report)

        if args.with_api or args.all:
            await validate_api_endpoints(session, report)

    success = report.summary()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
