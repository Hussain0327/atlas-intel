"""FinBERT sentiment analysis for financial text."""

import logging
from decimal import Decimal
from typing import Any

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from atlas_intel.config import settings

logger = logging.getLogger(__name__)

_model: Any = None
_tokenizer: Any = None

LABELS = ["positive", "negative", "neutral"]


def _get_model_and_tokenizer() -> tuple[Any, Any]:
    """Lazy-load FinBERT model singleton."""
    global _model, _tokenizer
    if _model is None or _tokenizer is None:
        model_name = settings.finbert_model
        logger.info("Loading FinBERT model: %s", model_name)
        _tokenizer = AutoTokenizer.from_pretrained(model_name)
        _model = AutoModelForSequenceClassification.from_pretrained(model_name)
        # Set model to evaluation/inference mode (disables dropout)
        _model.train(False)
    return _model, _tokenizer


def analyze_sentences(
    sentences: list[str], batch_size: int = settings.nlp_batch_size
) -> list[dict[str, Any]]:
    """Run FinBERT inference on a list of sentences.

    Returns list of dicts with keys: positive, negative, neutral, label, confidence.
    """
    if not sentences:
        return []

    model, tokenizer = _get_model_and_tokenizer()
    results: list[dict[str, Any]] = []

    for i in range(0, len(sentences), batch_size):
        batch = sentences[i : i + batch_size]
        inputs = tokenizer(
            batch, padding=True, truncation=True, max_length=512, return_tensors="pt"
        )

        with torch.no_grad():
            outputs = model(**inputs)
            probs = torch.nn.functional.softmax(outputs.logits, dim=-1)

        for prob in probs:
            scores = {LABELS[j]: float(prob[j]) for j in range(len(LABELS))}
            label = max(scores, key=lambda k: scores[k])
            results.append(
                {
                    "positive": Decimal(str(round(scores["positive"], 4))),
                    "negative": Decimal(str(round(scores["negative"], 4))),
                    "neutral": Decimal(str(round(scores["neutral"], 4))),
                    "label": label,
                    "confidence": Decimal(str(round(scores[label], 4))),
                }
            )

    return results


def aggregate_sentiment(
    sentiments: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compute weighted average sentiment across sentences.

    Weights by confidence score. Returns dict with positive, negative, neutral, label.
    """
    if not sentiments:
        return {
            "positive": Decimal("0"),
            "negative": Decimal("0"),
            "neutral": Decimal("0"),
            "label": "neutral",
        }

    total_weight = sum(float(s["confidence"]) for s in sentiments)
    if total_weight == 0:
        total_weight = 1.0

    avg = {
        key: sum(float(s[key]) * float(s["confidence"]) for s in sentiments) / total_weight
        for key in ("positive", "negative", "neutral")
    }

    label = max(avg, key=lambda k: avg[k])
    return {
        "positive": Decimal(str(round(avg["positive"], 4))),
        "negative": Decimal(str(round(avg["negative"], 4))),
        "neutral": Decimal(str(round(avg["neutral"], 4))),
        "label": label,
    }
