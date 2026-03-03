"""Data parsing and normalization for FMP earnings call transcripts."""

import re
from datetime import date, datetime
from typing import Any


def parse_transcript_date(value: str | None) -> date | None:
    """Parse FMP date format ('2024-01-25 17:00:00') into a date object."""
    if not value:
        return None
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d %H:%M:%S").date()
    except (ValueError, TypeError):
        # Try plain date format as fallback
        try:
            return datetime.strptime(value.strip(), "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return None


def split_into_sentences(text: str) -> list[str]:
    """Split text into sentences, filtering out fragments < 10 chars."""
    if not text:
        return []
    # Split on sentence-ending punctuation followed by whitespace or end
    raw = re.split(r"(?<=[.!?])\s+", text.strip())
    return [s.strip() for s in raw if len(s.strip()) >= 10]


def parse_transcript_sections(content: str) -> list[dict[str, Any]]:
    """Extract speaker blocks from transcript content.

    Detects speakers in format "Speaker Name - Title:" or "Speaker Name:"
    and classifies sections as prepared_remarks or q_and_a.
    """
    if not content:
        return []

    sections: list[dict[str, Any]] = []
    # Match lines like "John Doe - CEO:" or "Operator:"
    speaker_pattern = re.compile(
        r"^([A-Z][A-Za-z '.,-]+?)(?:\s*[-\u2013\u2014]\s*(.+?))?\s*:\s*$",
        re.MULTILINE,
    )
    matches = list(speaker_pattern.finditer(content))

    if not matches:
        # No speakers detected — treat entire content as single section
        sections.append(
            {
                "section_type": "prepared_remarks",
                "section_order": 0,
                "speaker_name": None,
                "speaker_title": None,
                "content": content.strip(),
            }
        )
        return sections

    in_qa = False
    for i, match in enumerate(matches):
        speaker_name = match.group(1).strip()
        speaker_title = match.group(2).strip() if match.group(2) else None

        # Determine section end
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        block_content = content[start:end].strip()

        if not block_content:
            continue

        # Detect Q&A transition
        if not in_qa and _is_qa_indicator(speaker_name, block_content):
            in_qa = True

        section_type = "q_and_a" if in_qa else "prepared_remarks"
        if speaker_name.lower() == "operator":
            section_type = "operator"

        sections.append(
            {
                "section_type": section_type,
                "section_order": len(sections),
                "speaker_name": speaker_name,
                "speaker_title": speaker_title,
                "content": block_content,
            }
        )

    return sections


def _is_qa_indicator(speaker_name: str, content: str) -> bool:
    """Check if a section marks the beginning of Q&A."""
    lower_name = speaker_name.lower()
    lower_content = content[:200].lower()
    qa_phrases = ["question-and-answer", "question and answer", "q&a session", "q & a"]
    if lower_name == "operator":
        for phrase in qa_phrases:
            if phrase in lower_content:
                return True
    return False


def parse_fmp_transcript(data: dict[str, Any]) -> dict[str, Any] | None:
    """Normalize a single FMP transcript response into standard format.

    Returns dict with: quarter, year, transcript_date, raw_text, title.
    Returns None if data is invalid.
    """
    content = data.get("content", "")
    if not content or not content.strip():
        return None

    quarter = data.get("quarter")
    year = data.get("year")
    if not quarter or not year:
        return None

    transcript_date = parse_transcript_date(data.get("date"))
    if not transcript_date:
        return None

    title = data.get("title", f"Q{quarter} {year} Earnings Call")

    return {
        "quarter": int(quarter),
        "year": int(year),
        "transcript_date": transcript_date,
        "raw_text": content.strip(),
        "title": title,
    }
