"""KeyBERT keyword extraction for financial text."""

import logging
from decimal import Decimal
from typing import Any, cast

from keybert import KeyBERT

logger = logging.getLogger(__name__)

_kw_model: KeyBERT | None = None


def _get_kw_model() -> KeyBERT:
    """Lazy-load KeyBERT singleton with sentence-transformers backend."""
    from atlas_intel.config import settings

    if settings.disable_nlp:
        raise RuntimeError("NLP is disabled (DISABLE_NLP=true). Cannot load KeyBERT model.")
    global _kw_model
    if _kw_model is None:
        logger.info("Loading KeyBERT model (all-MiniLM-L6-v2)")
        _kw_model = KeyBERT(model="all-MiniLM-L6-v2")
    return _kw_model


def extract_keywords(text: str, top_n: int = 20) -> list[dict[str, Any]]:
    """Extract keywords using KeyBERT with MMR for diversity.

    Returns list of dicts with keys: keyword, relevance_score.
    """
    if not text or not text.strip():
        return []

    model = _get_kw_model()
    raw_keywords: Any = model.extract_keywords(
        text,
        keyphrase_ngram_range=(1, 2),
        stop_words="english",
        use_mmr=True,
        diversity=0.5,
        top_n=top_n,
    )
    keywords = cast(list[tuple[str, float]], raw_keywords)

    return [
        {
            "keyword": kw,
            "relevance_score": Decimal(str(round(score, 4))),
        }
        for kw, score in keywords
    ]
