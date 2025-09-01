"""
Additional correction and compliance helpers.

This module provides utilities to post-process or normalize subtitle entries.
New logic (per task requirement):
- Do not update a subtitle timestamp unless the change is at least one second.
- Update the subtitle text only when there is a change in words (ignore punctuation, whitespace, and capitalization).

All timing values are in seconds (float).
"""

from pathlib import Path
from typing import Optional, List, Dict, Tuple
import re
import uuid


# PUBLIC_INTERFACE
def apply_additional_compliance_fixes(path: str, processed_dir: str) -> str:
    """Apply post-processing corrections; for now, return a copy to a new file."""
    src = Path(path)
    content = src.read_text(encoding="utf-8", errors="ignore")
    # Placeholder: could adjust reading speeds, spacing, punctuation etc.
    out = Path(processed_dir) / f"temp_{uuid.uuid4()}_postfix.srt"
    out.write_text(content, encoding="utf-8")
    return str(out)


_word_re = re.compile(r"[A-Za-z0-9]+", re.UNICODE)


def _extract_words(text: str) -> List[str]:
    """
    Extract word tokens (alphanumeric sequences) from text, lowercased.
    Punctuation, whitespace, and casing are ignored by design.
    """
    return [w.lower() for w in _word_re.findall(text or "")]


def _should_update_text(old: str, new: str) -> bool:
    """
    Decide if subtitle text should be updated based on word content only.
    Returns True only if the sequence of words has changed.

    Examples (all return False):
      - "Hello, world!" vs "hello world"
      - "  Hello  world " vs "hello   world"
      - "HELLO." vs "hello"

    Returns True if at least one word differs, appears, or disappears.
    """
    return _extract_words(old) != _extract_words(new)


def _time_change_is_significant(old_start: float, old_end: float, new_start: float, new_end: float) -> bool:
    """
    Return True if either start or end would change by at least 1.0s.
    """
    start_diff = abs(float(new_start) - float(old_start))
    end_diff = abs(float(new_end) - float(old_end))
    return (start_diff >= 1.0) or (end_diff >= 1.0)


# PUBLIC_INTERFACE
def conservative_merge_subtitle_update(
    original: Dict,
    proposal: Dict,
) -> Dict:
    """
    Merge a proposed subtitle correction into the original using conservative rules:
    - Timestamps are only applied if the change in start or end is >= 1.0 second.
    - Text is only updated if word content changes (ignoring punctuation, whitespace, casing).

    Args:
        original: dict with keys: 'start' (float), 'end' (float), 'text' (str), optional meta (index/format)
        proposal: dict with potentially updated 'start', 'end', 'text'

    Returns:
        A new dict with merged values, preserving original when changes are not significant.
    """
    merged = dict(original)

    # Handle timestamps
    old_start = float(original.get("start", 0.0))
    old_end = float(original.get("end", old_start))
    new_start = float(proposal.get("start", old_start))
    new_end = float(proposal.get("end", old_end))

    if _time_change_is_significant(old_start, old_end, new_start, new_end):
        merged["start"] = float(new_start)
        merged["end"] = float(new_end)
    else:
        # keep originals
        merged["start"] = float(old_start)
        merged["end"] = float(old_end)

    # Handle text
    old_text = str(original.get("text", "") or "")
    new_text = str(proposal.get("text", old_text) or "")

    if _should_update_text(old_text, new_text):
        # Only accept the new text if it actually has word content,
        # or if the old text had no word content (so we are improving it).
        old_words = _extract_words(old_text)
        new_words = _extract_words(new_text)
        if new_words or not old_words:
            merged["text"] = new_text
        else:
            # Prevent losing meaningful original text
            merged["text"] = old_text
    else:
        merged["text"] = old_text

    # Preserve known fields
    if "index" in original:
        merged["index"] = original["index"]
    if "format" in original:
        merged["format"] = original["format"]

    return merged
