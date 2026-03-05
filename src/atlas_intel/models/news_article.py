"""News article model."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from atlas_intel.models.base import Base, TimestampMixin


class NewsArticle(TimestampMixin, Base):
    __tablename__ = "news_articles"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(1000))
    snippet: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)
    source_name: Mapped[str | None] = mapped_column(String(200))
    image_url: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime] = mapped_column(DateTime)

    company: Mapped["Company"] = relationship(back_populates="news_articles")  # type: ignore[name-defined] # noqa: F821

    __table_args__ = (
        UniqueConstraint("company_id", "url", name="uq_news_article_company_url"),
        Index("ix_news_articles_company_published", "company_id", "published_at"),
        Index("ix_news_articles_published", "published_at"),
    )

    def __repr__(self) -> str:
        return f"<NewsArticle {self.published_at} {self.title[:50]}>"
