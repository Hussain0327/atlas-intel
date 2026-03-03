"""add transcript tables and transcripts_synced_at

Revision ID: 003
Revises: 002
Create Date: 2026-03-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: str = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add transcripts_synced_at to companies
    op.add_column("companies", sa.Column("transcripts_synced_at", sa.DateTime(), nullable=True))

    # Earnings transcripts
    op.create_table(
        "earnings_transcripts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "company_id",
            sa.Integer(),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("quarter", sa.SmallInteger(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("transcript_date", sa.Date(), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("sentiment_positive", sa.Numeric(6, 4), nullable=True),
        sa.Column("sentiment_negative", sa.Numeric(6, 4), nullable=True),
        sa.Column("sentiment_neutral", sa.Numeric(6, 4), nullable=True),
        sa.Column("sentiment_label", sa.String(20), nullable=True),
        sa.Column("nlp_processed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("company_id", "quarter", "year", name="uq_transcript_company_quarter"),
    )
    op.create_index(
        "ix_transcript_company_date", "earnings_transcripts", ["company_id", "transcript_date"]
    )
    op.create_index(
        "ix_transcript_company_year_quarter",
        "earnings_transcripts",
        ["company_id", "year", "quarter"],
    )

    # Transcript sections
    op.create_table(
        "transcript_sections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "transcript_id",
            sa.Integer(),
            sa.ForeignKey("earnings_transcripts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("section_type", sa.String(50), nullable=False),
        sa.Column("section_order", sa.SmallInteger(), nullable=False),
        sa.Column("speaker_name", sa.String(200), nullable=True),
        sa.Column("speaker_title", sa.String(300), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("sentiment_positive", sa.Numeric(6, 4), nullable=True),
        sa.Column("sentiment_negative", sa.Numeric(6, 4), nullable=True),
        sa.Column("sentiment_neutral", sa.Numeric(6, 4), nullable=True),
        sa.Column("sentiment_label", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_section_transcript", "transcript_sections", ["transcript_id", "section_order"]
    )

    # Sentiment analyses
    op.create_table(
        "sentiment_analyses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "section_id",
            sa.Integer(),
            sa.ForeignKey("transcript_sections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sentence_index", sa.SmallInteger(), nullable=False),
        sa.Column("sentence_text", sa.Text(), nullable=False),
        sa.Column("positive", sa.Numeric(6, 4), nullable=False),
        sa.Column("negative", sa.Numeric(6, 4), nullable=False),
        sa.Column("neutral", sa.Numeric(6, 4), nullable=False),
        sa.Column("label", sa.String(20), nullable=False),
        sa.Column("confidence", sa.Numeric(6, 4), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_sentiment_section", "sentiment_analyses", ["section_id", "sentence_index"])

    # Keyword extractions
    op.create_table(
        "keyword_extractions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "transcript_id",
            sa.Integer(),
            sa.ForeignKey("earnings_transcripts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("keyword", sa.String(200), nullable=False),
        sa.Column("relevance_score", sa.Numeric(6, 4), nullable=False),
        sa.Column("frequency", sa.SmallInteger(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_keyword_transcript", "keyword_extractions", ["transcript_id"])
    op.create_index("ix_keyword_keyword", "keyword_extractions", ["keyword"])


def downgrade() -> None:
    op.drop_table("keyword_extractions")
    op.drop_table("sentiment_analyses")
    op.drop_table("transcript_sections")
    op.drop_table("earnings_transcripts")
    op.drop_column("companies", "transcripts_synced_at")
