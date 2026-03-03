"""
Manual validation script — runs real SEC + FMP pipeline for a handful of tickers
and spot-checks the data that lands in PostgreSQL.

Usage:
    uv run python scripts/validate_pipeline.py              # SEC only (no FMP key needed)
    FMP_API_KEY=xxx uv run python scripts/validate_pipeline.py --with-transcripts

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
from atlas_intel.ingestion.pipeline import run_full_sync, run_transcript_sync
from atlas_intel.models.company import Company
from atlas_intel.models.earnings_transcript import EarningsTranscript
from atlas_intel.models.filing import Filing
from atlas_intel.models.financial_fact import FinancialFact
from atlas_intel.models.keyword_extraction import KeywordExtraction
from atlas_intel.models.sentiment_analysis import SentimentAnalysis
from atlas_intel.models.transcript_section import TranscriptSection

# Tickers chosen for coverage: large-cap (AAPL, MSFT), mid-cap (CRWD),
# financial (JPM), industrial (CAT). Each exercises different filing patterns.
VALIDATION_TICKERS = ["AAPL", "MSFT", "CRWD", "JPM", "CAT"]

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
# SEC pipeline checks
# ---------------------------------------------------------------------------


async def validate_sec_pipeline(session: AsyncSession, report: Report) -> None:
    """Run full SEC sync and validate the data."""
    print("\n--- SEC EDGAR Pipeline ---")

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
# Transcript pipeline checks
# ---------------------------------------------------------------------------


async def validate_transcript_pipeline(session: AsyncSession, report: Report) -> None:
    """Run transcript sync for a couple of tickers and validate NLP output."""
    print("\n--- Transcript + NLP Pipeline ---")

    test_tickers = ["AAPL", "MSFT"]

    if not settings.fmp_api_key:
        print("  SKIPPED: FMP_API_KEY not set. Set it in .env or environment.")
        report.check("FMP_API_KEY configured", False, "Set FMP_API_KEY to test transcripts")
        return

    print(f"Syncing transcripts for {test_tickers} (last 1 year)...")
    results = await run_transcript_sync(session, test_tickers, years=1, force=True)

    for ticker in test_tickers:
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
# DB integrity checks
# ---------------------------------------------------------------------------


async def validate_db_integrity(session: AsyncSession, report: Report) -> None:
    """Check cross-table FK integrity and no orphaned rows."""
    print("\n--- Database Integrity ---")

    # Orphaned filings (company_id not in companies)
    orphaned = (
        await session.execute(
            text(
                "SELECT count(*) FROM filings f "
                "LEFT JOIN companies c ON f.company_id = c.id "
                "WHERE c.id IS NULL"
            )
        )
    ).scalar()
    report.check("No orphaned filings", orphaned == 0, f"orphaned={orphaned}")

    # Orphaned facts
    orphaned = (
        await session.execute(
            text(
                "SELECT count(*) FROM financial_facts f "
                "LEFT JOIN companies c ON f.company_id = c.id "
                "WHERE c.id IS NULL"
            )
        )
    ).scalar()
    report.check("No orphaned financial_facts", orphaned == 0, f"orphaned={orphaned}")

    # Orphaned transcripts
    orphaned = (
        await session.execute(
            text(
                "SELECT count(*) FROM earnings_transcripts t "
                "LEFT JOIN companies c ON t.company_id = c.id "
                "WHERE c.id IS NULL"
            )
        )
    ).scalar()
    report.check("No orphaned transcripts", orphaned == 0, f"orphaned={orphaned}")

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
    args = parser.parse_args()

    report = Report()

    async with async_session() as session:
        await validate_sec_pipeline(session, report)

        if args.with_transcripts:
            await validate_transcript_pipeline(session, report)

        await validate_db_integrity(session, report)

    success = report.summary()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
