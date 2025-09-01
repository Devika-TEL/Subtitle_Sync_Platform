"""
Subtitle alignment utilities.

This module provides functionality to align and correct subtitle entries
using a transcript as the authoritative reference. It fixes misrecognitions,
corrects timestamps when off by >= 1 second, and enforces monotonic timing
for SRT-like subtitles.

Note:
- All timing values across this module are in seconds (float). Do NOT pass milliseconds.
  A defensive heuristic clamps negatives to 0.0; we do not auto-convert from ms.
- Aligned subtitles are represented with 'start' and 'end' as float seconds.
  To export these to SRT text reliably, use subtitle_time_utils.write_srt()
  which handles accurate hh:mm:ss,mmm formatting and edge cases.
"""

from typing import List, Dict, Tuple, Optional, Any
import re


def _is_blank(text: Optional[str]) -> bool:
    """Return True if text is None or only whitespace."""
    return text is None or str(text).strip() == ""


def _normalize_space(text: str) -> str:
    """Collapse multiple spaces and trim."""
    return re.sub(r"\s+", " ", text or "").strip()


def _overlap(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    """
    Return overlap duration between intervals a and b.
    Intervals are (start, end) in seconds.
    """
    s = max(a[0], b[0])
    e = min(a[1], b[1])
    return max(0.0, e - s)


def _interval_center(iv: Tuple[float, float]) -> float:
    """Return center point of the interval."""
    return (iv[0] + iv[1]) / 2.0


def _safe_time(t: float) -> float:
    """Clamp negative timestamps to 0."""
    return max(0.0, float(t))


def _get_seg_value(seg: Any, key: str, default: Any = None) -> Any:
    """
    Safely get a value from a transcript segment which may be:
      - a dict-like object with .get
      - an object with attributes
      - or even an unexpected type (string, etc.)

    Returns default if the key is unavailable or conversion fails.
    """
    try:
        # dict-like
        if hasattr(seg, "get"):
            return seg.get(key, default)
        # object-like attribute
        if hasattr(seg, key):
            return getattr(seg, key, default)
    except Exception:
        pass
    return default


def _to_seg_dict(seg: Any) -> Dict[str, Any]:
    """
    Normalize an arbitrary transcript segment into a dict with start/end/text keys.
    If seg is a string, treat it as text with unknown times defaulting to 0 and small duration.
    """
    text = ""
    if isinstance(seg, str):
        text = seg
    else:
        # Try to extract text field
        txt = _get_seg_value(seg, "text", "")
        text = txt if isinstance(txt, str) else str(txt) if txt is not None else ""

    start_val = _get_seg_value(seg, "start", 0.0)
    end_val = _get_seg_value(seg, "end", None)

    try:
        start = _safe_time(float(start_val))
    except Exception:
        start = 0.0

    if end_val is None:
        # assume short duration if end not provided
        end = start + 0.4
    else:
        try:
            end = _safe_time(float(end_val))
        except Exception:
            end = start + 0.4

    if end <= start:
        end = start + 0.1

    return {"start": start, "end": end, "text": text}


def _ensure_monotonic(subs: List[Dict], min_gap: float = 0.02, min_duration: float = 0.3) -> None:
    """
    Ensure start/end times are monotonic and non-overlapping in-place.
    - Enforces start_i >= prev_end + min_gap
    - Enforces end_i >= start_i + min_duration
    Also prints corrections for each affected subtitle.
    """
    prev_end = 0.0
    for s in subs:
        before_start = float(s.get("start", 0.0))
        before_end = float(s.get("end", before_start + min_duration))
        start = _safe_time(before_start)
        end = _safe_time(before_end)
        # enforce increasing start
        if start < prev_end + min_gap:
            start = prev_end + min_gap
        # enforce minimal duration
        if end < start + min_duration:
            end = start + min_duration
        s["start"] = start
        s["end"] = end
        if (before_start != start) or (before_end != end):
            idx = s.get("index", "?")
            print(f"[align:monotonic] #{idx} time {before_start:.2f}-{before_end:.2f} -> {start:.2f}-{end:.2f} (min_gap={min_gap:.2f}, min_dur={min_duration:.2f})")
        prev_end = end


# PUBLIC_INTERFACE
def align_subtitles(transcript_subs: List[Dict], subtitle_subs: List[Dict]) -> List[Dict]:
    """
    Align subtitle cues to a reference transcript.

    Behavior (Transcript is authoritative):
    - If the timestamp difference between transcript and subtitle is >= 1.0 second for start or end,
      overwrite the subtitle's corresponding start/end with the transcript values.
    - If the text differs in any way (case, punctuation, spacing, or words), overwrite the subtitle text
      with the exact transcript text.
    - Preserve ordering by pairing cues by index (min length), then append any tail items as-is.
    - After merging, enforce minimal monotonic constraints to avoid overlaps.

    Args:
        transcript_subs: List of transcript segments (authoritative) with fields start, end, text (index/format optional).
        subtitle_subs: List of subtitle cues to be corrected.

    Returns:
        List[dict]: Aligned subtitles with fields index, start, end, text, format.
    """
    # Helper: safely coerce to float seconds.
    def _sec(val, default=0.0) -> float:
        try:
            return float(val)
        except Exception:
            return float(default)

    # Helper: normalize any item (dict/object/None/etc.) into a simple dict.
    def _norm_item(x: Any) -> Dict[str, Any]:
        if x is None:
            return {}
        if hasattr(x, "get"):
            try:
                return dict(x)
            except Exception:
                pass
        out: Dict[str, Any] = {}
        for k in ("index", "start", "end", "text", "format"):
            try:
                if hasattr(x, k):
                    out[k] = getattr(x, k)
            except Exception:
                continue
        if not out and isinstance(x, str):
            out["text"] = x
        return out

    transcript = list(transcript_subs or [])
    subtitles = list(subtitle_subs or [])

    n = min(len(transcript), len(subtitles))
    merged: List[Dict] = []

    for i in range(n):
        t = _norm_item(transcript[i])
        s = _norm_item(subtitles[i])

        # Determine safe integer index (prefer subtitle's index if present for stability)
        raw_idx = s.get("index", t.get("index", i + 1))
        if callable(raw_idx):
            idx = i + 1
        else:
            try:
                idx = int(raw_idx)
            except Exception:
                idx = i + 1

        # Coerce times and texts
        t_start = _sec(t.get("start"))
        t_end = _sec(t.get("end"), t_start + 0.01)
        t_text = _normalize_space(t.get("text", ""))

        s_start = _sec(s.get("start"), t_start)
        s_end = _sec(s.get("end"), s_start + 0.01)
        s_text = _normalize_space(s.get("text", ""))

        # Timing correction: if abs diff >= 1.0s, take transcript's
        start = t_start if abs(t_start - s_start) >= 1.0 else s_start
        end = t_end if abs(t_end - s_end) >= 1.0 else s_end

        # Text correction: any difference -> use transcript text
        text = t_text if t_text != s_text else s_text

        # Sanity: non-negative and end > start
        start = _safe_time(start)
        end = max(_safe_time(end), start + 0.01)

        merged.append({
            "index": idx,
            "start": float(start),
            "end": float(end),
            "text": text,
            "format": s.get("format", t.get("format", "srt")),
        })

    # Handle tails if lists differ in length: append remaining subtitles as-is,
    # since we don't have corresponding transcript segments for authoritative overwrite.
    if len(subtitles) > n:
        for j in range(n, len(subtitles)):
            s = _norm_item(subtitles[j])
            raw = s.get("index", j + 1)
            try:
                idx = int(raw) if not callable(raw) else j + 1
            except Exception:
                idx = j + 1
            start = _safe_time(_sec(s.get("start")))
            end = max(_safe_time(_sec(s.get("end"), start + 0.01)), start + 0.01)
            merged.append({
                "index": idx,
                "start": float(start),
                "end": float(end),
                "text": _normalize_space(s.get("text", "")),
                "format": s.get("format", "srt"),
            })

    if len(transcript) > n:
        # If transcript has extra items, include them directly (they are authoritative).
        for j in range(n, len(transcript)):
            t = _norm_item(transcript[j])
            raw = t.get("index", j + 1)
            try:
                idx = int(raw) if not callable(raw) else j + 1
            except Exception:
                idx = j + 1
            t_start = _safe_time(_sec(t.get("start")))
            t_end = max(_safe_time(_sec(t.get("end"), t_start + 0.01)), t_start + 0.01)
            merged.append({
                "index": idx,
                "start": float(t_start),
                "end": float(t_end),
                "text": _normalize_space(t.get("text", "")),
                "format": t.get("format", "srt"),
            })

    # Reindex cleanly and ensure monotonic minimal constraints
    for k, s in enumerate(merged, start=1):
        s["index"] = k

    _ensure_monotonic(merged, min_gap=0.0, min_duration=0.01)
    return merged


if __name__ == "__main__":
    """
    Demo harness: after aligning, print ONLY the subtitles that required modification
    compared to the original subtitles, based on:
      - timing change (start or end) of >= 1.0 second, or
      - any text change (case/punctuation/spacing/words).
    Unchanged subtitles are omitted from output.
    """
    # Sample inputs: transcript is authoritative
    transcript = [
        {"start": 0, "end": 2, "text": "Hello world!"},
        {"start": 2.9, "end": 5, "text": "This is a test."},
        {"start": 6, "end": 8, "text": "Another line here."},
    ]
    # Keep a copy of the original subtitles for comparison
    original_subtitles = [
        {"start": 5, "end": 7, "text": "Hello Would"},
        {"start": 3, "end": 4.3, "text": "This is a test!"},
        {"start": 6, "end": 7.9, "text": "Another Lion here."},
    ]
    # Work copy for processing
    subtitles = [dict(item) for item in original_subtitles]

    merged = align_subtitles(transcript, subtitles)

    # Determine and print only modified subtitles
    print("Modified subtitles (index start->end | text):")
    # We compare by position (index-based pairing prior to reindexing), using min length
    n = min(len(original_subtitles), len(merged))
    any_printed = False
    for i in range(n):
        orig = original_subtitles[i]
        new = merged[i]

        # Compare text with normalization similar to align_subtitles
        def _norm(txt: str) -> str:
            return re.sub(r"\s+", " ", (txt or "")).strip()

        text_changed = _norm(orig.get("text", "")) != _norm(new.get("text", ""))

        # Timing difference threshold comparison
        orig_start = float(orig.get("start", 0.0))
        orig_end = float(orig.get("end", orig_start + 0.01))
        new_start = float(new.get("start", 0.0))
        new_end = float(new.get("end", new_start + 0.01))

        timing_changed = (abs(orig_start - new_start) >= 1.0) or (abs(orig_end - new_end) >= 1.0)

        if text_changed or timing_changed:
            any_printed = True
            print(f"{new['index']:>3}  {new_start:.2f} -> {new_end:.2f} | {new['text']}")

    # If there are extra items (either transcript or subtitles longer), they are considered "added/changed"
    if len(merged) > n:
        any_printed = True
        for j in range(n, len(merged)):
            s = merged[j]
            print(f"{s['index']:>3}  {s['start']:.2f} -> {s['end']:.2f} | {s['text']}")

    if not any_printed:
        print("(no modifications)")
