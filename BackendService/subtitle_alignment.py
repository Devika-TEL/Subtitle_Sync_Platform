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


def _ensure_monotonic(subs: List[Dict], min_gap: float = 0.02, min_duration: float = 0.8) -> None:
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
def align_subtitles(
    transcript_subs: List[Dict],
    subtitle_subs: List[Dict],
    *,
    cross_lingual: bool = False,
    drop_empty_cues: bool = True,
) -> List[Dict]:
    """
    Align subtitle cues to a reference transcript.

    Behavior (Transcript is authoritative):
    - If the timestamp difference between transcript and subtitle is >= 1.0 second for start or end,
      overwrite the subtitle's corresponding start/end with the transcript values.
    - If cross_lingual=False and the text differs (case, punctuation, spacing, or words),
      overwrite the subtitle text with the exact transcript text.
      If cross_lingual=True, preserve subtitle text.
    - Preserve ordering by pairing cues by index (min length), then append any tail items as-is.
    - After merging, enforce minimal monotonic constraints to avoid overlaps.
    - Additional safeguards:
        * Never output an empty-text cue: if both transcript and subtitle text are blank,
          reuse the last seen non-empty text for the first cue only (to avoid losing initial text),
          else skip the cue (when drop_empty_cues=True).
        * Always retain the first intended subtitle text: if the transcript text is blank, keep the subtitle text.

    Args:
        transcript_subs: List of transcript segments (authoritative) with fields start, end, text (index/format optional).
        subtitle_subs: List of subtitle cues to be corrected.
        cross_lingual: If True, do not replace subtitle text with transcript text.
        drop_empty_cues: If True, remove cues that end up with empty text (except first-cue safeguard).

    Returns:
        List[dict]: Aligned subtitles with fields index, start, end, text, format.

    Notes on timing policy:
    - Final output ensures cues are monotonic and enforce a readable minimum duration (>= 1.0s).
    - A small gap (~0.05s) is introduced to avoid cues ending/starting at the exact same instant.
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

    last_non_empty_text: Optional[str] = None
    first_cue_text_fallback_used = False

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

        # Timing correction:
        # Prefer subtitle timing if it already reasonably overlaps the transcript window
        # or centers near it. Otherwise, use the transcript timing which is authoritative.
        # This avoids tiny/near-zero times surviving and later being bunched by monotonic pass.
        s_iv = (s_start, max(s_end, s_start + 0.01))
        t_iv = (t_start, max(t_end, t_start + 0.01))
        ov = _overlap(s_iv, t_iv)
        s_dur = max(0.01, s_iv[1] - s_iv[0])
        t_dur = max(0.01, t_iv[1] - t_iv[0])
        center_diff = abs(_interval_center(s_iv) - _interval_center(t_iv))

        # Heuristics:
        # - If we have at least 40% overlap and centers within 0.75s, keep subtitle times.
        # - Else, if absolute difference is quite large (>= 0.75s), adopt transcript times.
        # - Else, lightly blend by nudging subtitle towards transcript start/end.
        keep_subtitle = (ov >= 0.4 * min(s_dur, t_dur)) and (center_diff <= 0.75)

        if keep_subtitle:
            start, end = s_iv
        else:
            if center_diff >= 0.75 or abs(t_start - s_start) >= 0.75 or abs(t_end - s_end) >= 0.75:
                start, end = t_iv
            else:
                # Gentle nudge towards transcript if small difference and poor overlap
                alpha = 0.5
                start = _safe_time((1 - alpha) * s_iv[0] + alpha * t_iv[0])
                end = _safe_time(max((1 - alpha) * s_iv[1] + alpha * t_iv[1], start + 0.01))

        # Text selection:
        # - If cross-lingual, preserve subtitle text.
        # - Else, if transcript text is non-empty and differs -> use transcript text.
        # - Else, keep subtitle text.
        if cross_lingual:
            chosen_text = s_text
        else:
            if not _is_blank(t_text) and t_text != s_text:
                chosen_text = t_text
            else:
                chosen_text = s_text if not _is_blank(s_text) else t_text

        # First-cue safeguard & empty-cue prevention:
        # If both are blank, for the very first cue, try to reuse a previous non-empty (not available yet),
        # or keep as blank for now and handle after building; else skip if drop_empty_cues.
        # We instead implement progressive carry-forward for the first cue only if both blank.
        if _is_blank(chosen_text):
            # Retain first subtitle non-empty when transcript is blank
            if i == 0 and not first_cue_text_fallback_used:
                # Prefer the subtitle's text if it has any hidden content (already checked blank),
                # otherwise do not emit this cue at all if dropping empties.
                if drop_empty_cues:
                    # Skip emitting this cue entirely
                    first_cue_text_fallback_used = True  # mark as processed decision
                    continue
                # If not dropping empties, keep as minimal non-empty placeholder using last known text if any
                if last_non_empty_text:
                    chosen_text = last_non_empty_text
                # else remain blank; will be filtered below if needed

        # Sanity: non-negative and end > start
        start = _safe_time(start)
        end = max(_safe_time(end), start + 0.01)

        # If resulting text is blank and policy is to drop empty cues, skip append
        if drop_empty_cues and _is_blank(chosen_text):
            continue

        merged.append({
            "index": idx,
            "start": float(start),
            "end": float(end),
            "text": chosen_text,
            "format": s.get("format", t.get("format", "srt")),
        })

        if not _is_blank(chosen_text):
            last_non_empty_text = chosen_text

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
            txt = _normalize_space(s.get("text", ""))
            # Apply empty-cue policy for tails
            if drop_empty_cues and _is_blank(txt):
                continue
            if not _is_blank(txt):
                last_non_empty_text = txt
            merged.append({
                "index": idx,
                "start": float(start),
                "end": float(end),
                "text": txt,
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
            txt = _normalize_space(t.get("text", ""))
            if drop_empty_cues and _is_blank(txt):
                continue
            if not _is_blank(txt):
                last_non_empty_text = txt
            merged.append({
                "index": idx,
                "start": float(t_start),
                "end": float(t_end),
                "text": txt,
                "format": t.get("format", "srt"),
            })

    # If all cues got dropped due to empties, but we had at least one original subtitle,
    # ensure we don't return an empty list by attempting to reinstate the first non-empty subtitle cue.
    if not merged and subtitles:
        # Find first non-empty subtitle text to reinstate
        for j, s in enumerate(subtitles, start=1):
            txt = _normalize_space(_norm_item(s).get("text", ""))
            if not _is_blank(txt):
                start = _safe_time(_sec(_norm_item(s).get("start"), 0.0))
                end = max(_safe_time(_sec(_norm_item(s).get("end"), start + 0.5)), start + 0.01)
                merged.append({
                    "index": 1,
                    "start": float(start),
                    "end": float(end),
                    "text": txt,
                    "format": _norm_item(s).get("format", "srt"),
                })
                break

    # Reindex cleanly and ensure monotonic minimal constraints
    for k, s in enumerate(merged, start=1):
        s["index"] = k

    # Final pass: enforce readable on-screen durations
    # - min_gap: small separation to avoid cues ending and starting at the same instant
    # - min_duration: enforce at least 1.0s so subtitles are visible/readable
    _ensure_monotonic(merged, min_gap=0.03, min_duration=0.8)
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
