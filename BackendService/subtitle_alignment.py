"""
Subtitle alignment utilities.

This module provides functionality to align and correct subtitle entries
using a Whisper model transcript as reference. It fixes missing texts,
improves timestamps, and enforces monotonic timing for SRT-like subtitles.

Note:
- All timing values across this module are in seconds (float). Do NOT pass milliseconds.
  A defensive heuristic detects ms-like values and raises a TypeError rather than auto-converting.
- Aligned subtitles are represented with 'start' and 'end' as float seconds.
  To export these to SRT text reliably, use subtitle_time_utils.write_srt()
  which handles accurate hh:mm:ss,mmm formatting and edge cases.

Debugging and input preparation tips:
- Provide transcript segments with realistic start/end in seconds, sorted by time.
- This function assumes same-language alignment and preserves subtitle text (no transcript text injection).
- Use console logs prefixed with [align:*] to understand how each cue was matched and refit.
  Frequent [align:refit] snap-to-seg messages indicate poor initial timing or transcript mismatch.
- If you observe many [align:cap] messages shrinking durations, consider increasing MAX_DUR or check whether your transcript has very short segments.
- Ensure there are no negative times; this module clamps negatives to 0.0.

Typical failure scenarios:
- Transcript language mismatch but cross_lingual not set -> text gets normalized undesirably (set cross_lingual=True).
- Very sparse or noisy transcript (huge gaps) -> cues may be distributed or snapped unexpectedly; pre-smooth or segment transcript to speaking regions.
- Overlapping input subtitles -> module will enforce minimal gaps and durations, which can shift later cues forward; consider pre-validating input files.
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

    Note: min_duration is injected by the caller to keep consistency with top-level MIN_DUR.
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
    """Update subtitle text from transcript segment if missing or to normalize spacing. Prints change details."""
    before = _normalize_space(sub.get("text", ""))
    seg_text = _normalize_space(seg.get("text", ""))
    if _is_blank(before) and not _is_blank(seg_text):
        sub["text"] = seg_text
        print(f"[align:text] #{sub.get('index','?')} text from_blank -> {seg_text!r}")
    else:
        # Normalize existing text spacing
        new_text = before or seg_text
        sub["text"] = new_text
        if before != new_text:
            print(f"[align:text] #{sub.get('index','?')} normalized {before!r} -> {new_text!r}")


def _refit_times_to_segment(sub: Dict, seg: Dict, *, min_dur: float = 0.5) -> None:
    """
    Adjust subtitle start/end to better fit transcript segment while keeping relative duration reasonable.

    Strategy:
      - If the subtitle already fits well (good overlap and small offset), keep original times.
      - If there is effectively no overlap, snap entirely to the segment (mismatch).
      - Otherwise, preserve original duration as much as possible, clamped within [seg_start, seg_end].
        If preserving original duration is impossible within segment, use the largest possible duration inside.

    Prints change details when times are modified.
    """
    seg_start = float(seg.get("start", 0.0))
    seg_end = float(seg.get("end", seg_start + 0.4))
    seg_dur = max(min_dur, seg_end - seg_start)

    orig_start = float(sub.get("start", seg_start))
    orig_end = float(sub.get("end", seg_end))
    orig_dur = max(min_dur, orig_end - orig_start)

    # Compute overlap and center offset
    overlap = _overlap((orig_start, orig_end), (seg_start, seg_end))
    sub_center = _interval_center((orig_start, orig_end))
    seg_center = _interval_center((seg_start, seg_end))
    center_offset = abs(sub_center - seg_center)

    # Heuristics for "already good":
    # - At least 60% of the subtitle duration overlaps with the segment
    # - And center offset is small (<= 0.25s or <= 15% of seg duration)
    overlap_ratio = overlap / max(min_dur, orig_dur)
    small_offset = center_offset <= max(0.25, 0.15 * seg_dur)

    if overlap_ratio >= 0.6 and small_offset:
        # Keep original timing — considered accurate enough
        return

    # If the subtitle is far outside the segment, snap to boundaries
    if overlap <= 1e-3:
        before_start, before_end = orig_start, orig_end
        sub["start"] = _safe_time(seg_start)
        sub["end"] = _safe_time(seg_end)
        print(f"[align:refit] #{sub.get('index','?')} no-overlap -> snap to seg {before_start:.2f}-{before_end:.2f} -> {seg_start:.2f}-{seg_end:.2f}")
        return

    # Preferred duration: preserve original but cannot exceed seg duration
    preferred = max(min_dur, min(orig_dur, seg_dur))

    # Try to center near current subtitle center but clamp inside segment
    target_center = min(max(seg_start, sub_center), seg_end)
    new_start = target_center - preferred / 2.0
    new_end = target_center + preferred / 2.0

    # Clamp to segment boundaries
    if new_start < seg_start:
        shift = seg_start - new_start
        new_start += shift
        new_end += shift
    if new_end > seg_end:
        shift = new_end - seg_end
        new_start -= shift
        new_end -= shift

    # If still outside due to segment being shorter than preferred, fallback to full segment
    if new_start < seg_start or new_end > seg_end or (new_end - new_start) < min_dur:
        new_start = seg_start
        new_end = seg_end

    before_start = float(sub.get("start", new_start))
    before_end = float(sub.get("end", new_end))
    if (before_start != new_start) or (before_end != new_end):
        sub["start"] = _safe_time(new_start)
        sub["end"] = _safe_time(new_end)
        idx = sub.get("index", "?")
        print(f"[align:refit] #{idx} time {before_start:.2f}-{before_end:.2f} -> {sub['start']:.2f}-{sub['end']:.2f} (seg {seg_start:.2f}-{seg_end:.2f})")


# PUBLIC_INTERFACE
def align_subtitles(original_subs: List[Dict], proposed_subs: List[Dict]) -> List[Dict]:
    """
    Merge two subtitle lists (original and proposed) applying strict rules, robustly handling
    list/dict or arbitrary objects for items to avoid KeyError/TypeError.

    - Timestamps (start/end) are updated only if the absolute difference between
      original and proposed is >= 1.0 second.
    - Text is updated only if the words actually differ, ignoring punctuation,
      whitespace, and case.
    - The output preserves ordering by index if available, otherwise by list position.
    - Returns the merged/corrected list of subtitles (dicts with index, start, end, text, format).

    Parameters:
        original_subs: Sequence with per-item providing 'start','end','text' via dict keys or attributes.
        proposed_subs: Sequence with same assumptions. If lengths differ, pairs up to min length.

    Returns:
        List[dict]: merged subtitles.

    Notes:
        - This function defensively normalizes input items using dict(...) only when it's safe;
          otherwise it falls back to attribute access or treats unknown types as empty dicts.
    """
    # Helper: normalize text into comparable word list (ignore punctuation, whitespace and case).
    def _words(text: Optional[str]) -> List[str]:
        if text is None:
            return []
        cleaned = re.sub(r"[\\W_]+", " ", str(text).lower(), flags=re.UNICODE).strip()
        return [w for w in cleaned.split() if w]

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
        # If it's already a mapping-like object, use it as-is (copy to avoid side-effects)
        if hasattr(x, "get"):
            try:
                return dict(x)
            except Exception:
                # Fallback to extracting known fields
                pass
        # Try attribute-style access
        out: Dict[str, Any] = {}
        for k in ("index", "start", "end", "text", "format"):
            try:
                if hasattr(x, k):
                    out[k] = getattr(x, k)
            except Exception:
                continue
        # If still empty and it's a string, treat as text
        if not out and isinstance(x, str):
            out["text"] = x
        return out

    orig_list = list(original_subs or [])
    prop_list = list(proposed_subs or [])

    # Pair subtitles by position; more advanced matching by index can be added later if needed.
    n = min(len(orig_list), len(prop_list))
    merged: List[Dict] = []

    for i in range(n):
        o_raw = orig_list[i] if i < len(orig_list) else None
        p_raw = prop_list[i] if i < len(prop_list) else None
        o = _norm_item(o_raw)
        p = _norm_item(p_raw)

        # Determine index, ensuring it's an integer value and not a callable/method.
        # Some upstream data structures might have an attribute named 'index'
        # that is a method (like list.index). Guard against callables and coerce safely.
        raw_idx = o.get("index", p.get("index", i + 1))
        if callable(raw_idx):
            # Fall back to positional index if 'index' field is a method/callable
            safe_idx = i + 1
        else:
            try:
                safe_idx = int(raw_idx)
            except Exception:
                safe_idx = i + 1
        idx = safe_idx

        # Baseline values from original
        o_start = _sec(o.get("start"))
        o_end = _sec(o.get("end"), o_start)
        o_text = _normalize_space(o.get("text", ""))

        # Proposed values
        p_start = _sec(p.get("start"), o_start)
        p_end = _sec(p.get("end"), p_start)
        p_text = _normalize_space(p.get("text", ""))

        # Decide start/end updates: only if absolute diff >= 1.0s
        start = o_start if abs(p_start - o_start) < 1.0 else p_start
        end = o_end if abs(p_end - o_end) < 1.0 else p_end

        # Ensure non-negative and end > start minimally
        start = _safe_time(start)
        end = max(_safe_time(end), start + 0.01)

        # Decide text updates: only if word lists differ
        o_words = _words(o_text)
        p_words = _words(p_text)
        text = p_text if o_words != p_words else o_text

        merged.append({
            "index": int(idx),
            "start": float(start),
            "end": float(end),
            "text": text,
            "format": o.get("format", p.get("format", "srt")),
        })

    # If original has extra tail items with no proposed pair, keep as-is
    if len(orig_list) > n:
        for j in range(n, len(orig_list)):
            o = _norm_item(orig_list[j])
            # Ensure safe integer index for orphan original items as well
            o_idx_raw = o.get("index", j + 1)
            if callable(o_idx_raw):
                o_idx = j + 1
            else:
                try:
                    o_idx = int(o_idx_raw)
                except Exception:
                    o_idx = j + 1
            merged.append({
                "index": o_idx,
                "start": float(_sec(o.get("start"))),
                "end": float(_sec(o.get("end"), _sec(o.get("start")) + 0.01)),
                "text": _normalize_space(o.get("text", "")),
                "format": o.get("format", "srt"),
            })

    # If proposed has extra tail items with no original pair, append them (they're effectively new)
    if len(prop_list) > n:
        for j in range(n, len(prop_list)):
            p = _norm_item(prop_list[j])
            # Ensure safe integer index for orphan proposed items as well
            p_idx_raw = p.get("index", j + 1)
            if callable(p_idx_raw):
                p_idx = j + 1
            else:
                try:
                    p_idx = int(p_idx_raw)
                except Exception:
                    p_idx = j + 1
            merged.append({
                "index": p_idx,
                "start": float(_sec(p.get("start"))),
                "end": float(_sec(p.get("end"), _sec(p.get("start")) + 0.01)),
                "text": _normalize_space(p.get("text", "")),
                "format": p.get("format", "srt"),
            })

    # Reindex sequentially to guarantee 1..N order and sort by original order
    for k, s in enumerate(merged, start=1):
        s["index"] = k

    # Final monotonic check with minimal duration to avoid overlap issues
    _ensure_monotonic(merged, min_gap=0.0, min_duration=0.01)
    return merged
