"""
Subtitle alignment utilities.

This module provides functionality to align and correct subtitle entries
using a Whisper model transcript as reference. It fixes missing texts,
improves timestamps, and enforces monotonic timing for SRT-like subtitles.
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


def _ensure_monotonic(subs: List[Dict], min_gap: float = 0.02) -> None:
    """
    Ensure start/end times are monotonic and non-overlapping in-place.
    - Enforces start_i >= prev_end + min_gap
    - Enforces end_i >= start_i + minimal duration
    """
    prev_end = 0.0
    min_duration = 0.3  # don't allow zero-length subs
    for s in subs:
        start = _safe_time(float(s.get("start", 0.0)))
        end = _safe_time(float(s.get("end", start + min_duration)))
        # enforce increasing start
        if start < prev_end + min_gap:
            start = prev_end + min_gap
        # enforce minimal duration
        if end < start + min_duration:
            end = start + min_duration
        s["start"] = start
        s["end"] = end
        prev_end = end


def _match_transcript_segment(
    sub_iv: Tuple[float, float],
    transcript: List[Dict],
) -> Optional[int]:
    """
    Find the best matching transcript segment index for a given subtitle interval.
    Priority:
      1) Maximum temporal overlap
      2) If ties or no overlap, minimal distance between centers
    Returns index or None if transcript empty.
    """
    if not transcript:
        return None

    best_idx = None
    best_overlap = -1.0
    best_center_dist = float("inf")
    sub_center = _interval_center(sub_iv)

    for i, seg in enumerate(transcript):
        seg_d = _to_seg_dict(seg)
        t_iv = (float(seg_d.get("start", 0.0)), float(seg_d.get("end", 0.0)))
        ov = _overlap(sub_iv, t_iv)
        if ov > best_overlap + 1e-9:
            best_idx = i
            best_overlap = ov
            best_center_dist = abs(_interval_center(t_iv) - sub_center)
        elif abs(ov - best_overlap) <= 1e-9:
            # tie-breaker: choose nearer center
            center_dist = abs(_interval_center(t_iv) - sub_center)
            if center_dist < best_center_dist:
                best_idx = i
                best_center_dist = center_dist

    return best_idx


def _closest_transcript_index_by_time(point: float, transcript: List[Dict]) -> Optional[int]:
    """
    Return index of transcript segment whose interval center is closest to 'point'.
    """
    if not transcript:
        return None
    best_idx = None
    best_dist = float("inf")
    for i, seg in enumerate(transcript):
        seg_d = _to_seg_dict(seg)
        center = _interval_center((float(seg_d.get("start", 0.0)), float(seg_d.get("end", 0.0))))
        d = abs(center - point)
        if d < best_dist:
            best_dist = d
            best_idx = i
    return best_idx


def _merge_adjacent_blanks(subs: List[Dict]) -> List[Dict]:
    """
    Merge consecutive blank-text subtitles to reduce fragmentation.
    """
    if not subs:
        return subs
    merged: List[Dict] = []
    buffer = None
    for s in subs:
        if _is_blank(s.get("text")):
            if buffer is None:
                buffer = dict(s)
            else:
                # extend buffer interval
                buffer["end"] = max(float(buffer["end"]), float(s["end"]))
        else:
            if buffer is not None:
                merged.append(buffer)
                buffer = None
            merged.append(s)
    if buffer is not None:
        merged.append(buffer)
    # reindex to keep indices consecutive after merges; keep original format and text
    for idx, s in enumerate(merged, start=1):
        s["index"] = idx
    return merged


def _apply_text_from_transcript(sub: Dict, seg: Dict) -> None:
    """Update subtitle text from transcript segment if missing or to normalize spacing."""
    sub_text = _normalize_space(sub.get("text", ""))
    seg_text = _normalize_space(seg.get("text", ""))
    if _is_blank(sub_text) and not _is_blank(seg_text):
        sub["text"] = seg_text
    else:
        # Normalize existing text spacing
        sub["text"] = sub_text or seg_text


def _refit_times_to_segment(sub: Dict, seg: Dict) -> None:
    """
    Adjust subtitle start/end to better fit transcript segment while keeping relative duration reasonable.
    Strategy:
      - Snap inside segment with slight padding.
      - Preserve original duration if it fits reasonably within segment, else clamp.
    """
    seg_start = float(seg.get("start", 0.0))
    seg_end = float(seg.get("end", seg_start + 0.4))
    seg_dur = max(0.1, seg_end - seg_start)

    orig_start = float(sub.get("start", seg_start))
    orig_end = float(sub.get("end", seg_end))
    orig_dur = max(0.1, orig_end - orig_start)

    # Preferred duration: min(original, segment duration), but not less than 0.3s
    preferred = max(0.3, min(orig_dur, seg_dur))

    # Place centered on the overlap/segment center, within segment bounds
    center = _interval_center((seg_start, seg_end))
    new_start = max(seg_start, center - preferred / 2.0)
    new_end = new_start + preferred
    if new_end > seg_end:
        new_end = seg_end
        new_start = max(seg_start, new_end - preferred)

    sub["start"] = _safe_time(new_start)
    sub["end"] = _safe_time(new_end)


# PUBLIC_INTERFACE
def align_subtitles(transcript: List[Dict], subtitles: List[Dict]) -> List[Dict]:
    """
    Align and correct SRT subtitles using a Whisper transcript.

    Parameters:
        transcript: List of dicts from Whisper with keys:
            - 'start' (float, seconds)
            - 'end' (float, seconds)
            - 'text' (str)
        subtitles: List of dicts with keys:
            - 'index' (int)
            - 'start' (float, seconds)
            - 'end' (float, seconds)
            - 'text' (str, may be empty/blank)
            - 'format' (str, 'srt')

    Returns:
        A corrected list of subtitle dicts with the same structure. The function:
        - Aligns each subtitle to the most suitable transcript segment using overlap and proximity.
        - Fills missing or blank texts with transcript text.
        - Adjusts timestamps to better match transcript segments.
        - Enforces monotonic, non-overlapping timing with minimal gaps.

    Notes:
        - Assumes English language and SRT format for now.
        - Non-destructive regarding non-text fields; fields beyond the required ones are preserved if present.
    """
    # Defensive copies and normalization
    subs = []
    for s in subtitles or []:
        subs.append({
            **s,
            "index": int(s.get("index", 0) or 0),
            "start": _safe_time(float(s.get("start", 0.0))),
            "end": _safe_time(float(s.get("end", 0.0)) if s.get("end", 0.0) is not None else float(s.get("start", 0.0)) + 0.3),
            "text": s.get("text", ""),
            "format": s.get("format", "srt"),
        })

    trans = []
    for seg in transcript or []:
        seg_d = _to_seg_dict(seg)
        start = _safe_time(float(seg_d.get("start", 0.0)))
        end = _safe_time(float(seg_d.get("end", start + 0.4)))
        text = seg_d.get("text", "")
        trans.append({"start": start, "end": max(end, start + 0.1), "text": text})

    if not subs:
        # If there are no subtitle entries, synthesize from transcript
        synthesized = []
        for i, seg in enumerate(trans, start=1):
            synthesized.append({
                "index": i,
                "start": seg["start"],
                "end": seg["end"],
                "text": _normalize_space(seg.get("text", "")),
                "format": "srt",
            })
        _ensure_monotonic(synthesized)
        return synthesized

    # Normalize space and merge adjacent blank subtitles to reduce noise
    for s in subs:
        s["text"] = _normalize_space(s.get("text", ""))

    subs = _merge_adjacent_blanks(subs)

    # First pass: match each subtitle with the best transcript segment
    matches: List[Optional[int]] = []
    for s in subs:
        sub_iv = (float(s["start"]), float(s["end"]))
        idx = _match_transcript_segment(sub_iv, trans)
        # If no overlap-based good match and transcript present, pick closest by center
        if idx is None and trans:
            idx = _closest_transcript_index_by_time(_interval_center(sub_iv), trans)
        matches.append(idx)

    # Second pass: apply text and refine timing using the matched segment
    for s, idx in zip(subs, matches):
        if idx is None:
            # No transcript available; just ensure normalized text
            s["text"] = _normalize_space(s.get("text", ""))
            continue
        seg = trans[idx]
        _apply_text_from_transcript(s, seg)
        _refit_times_to_segment(s, seg)

    # Enforce overall monotonic timing
    _ensure_monotonic(subs)

    # Reindex to ensure indices are strictly increasing and consecutive
    for i, s in enumerate(subs, start=1):
        s["index"] = i
        # ensure format as 'srt'
        s["format"] = "srt"

    return subs
