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
    Also prints corrections for each affected subtitle.
    """
    prev_end = 0.0
    min_duration = 0.3  # don't allow zero-length subs
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
            print(f"[align:monotonic] #{idx} time {before_start:.2f}-{before_end:.2f} -> {start:.2f}-{end:.2f} (min_gap={min_gap:.2f})")
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


def _refit_times_to_segment(sub: Dict, seg: Dict) -> None:
    """
    Adjust subtitle start/end to better fit transcript segment while keeping relative duration reasonable.
    Strategy:
      - Snap inside segment with slight padding.
      - Preserve original duration if it fits reasonably within segment, else clamp.
    Prints change details.
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

    before_start = float(sub.get("start", new_start))
    before_end = float(sub.get("end", new_end))
    sub["start"] = _safe_time(new_start)
    sub["end"] = _safe_time(new_end)
    if (before_start != sub["start"]) or (before_end != sub["end"]):
        idx = sub.get("index", "?")
        print(f"[align:refit] #{idx} time {before_start:.2f}-{before_end:.2f} -> {sub['start']:.2f}-{sub['end']:.2f} (seg {seg_start:.2f}-{seg_end:.2f})")


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
        - Prints alignment corrections to console for observability.

    Notes:
        - If transcript is missing or very short, a placeholder distribution spreads subtitles across
          an inferred timeline to avoid clustering at t=0.
        - Non-destructive regarding non-text fields; fields beyond the required ones are preserved if present.
    """
    # Parameters for realistic timing
    MIN_DUR = 0.8   # seconds
    MAX_DUR = 6.0   # seconds
    MIN_GAP = 0.08  # seconds between captions

    def _cap_duration(d: float) -> float:
        return max(MIN_DUR, min(MAX_DUR, d))

    # Defensive copies and normalization
    subs: List[Dict] = []
    for s in subtitles or []:
        subs.append({
            **s,
            "index": int(s.get("index", 0) or 0),
            "start": _safe_time(float(s.get("start", 0.0))),
            "end": _safe_time(float(s.get("end", 0.0)) if s.get("end", 0.0) is not None else float(s.get("start", 0.0)) + MIN_DUR),
            "text": _normalize_space(s.get("text", "")),
            "format": s.get("format", "srt"),
        })

    # Normalize transcript segments
    trans: List[Dict] = []
    for seg in transcript or []:
        seg_d = _to_seg_dict(seg)
        start = _safe_time(float(seg_d.get("start", 0.0)))
        end = _safe_time(float(seg_d.get("end", start + 0.4)))
        if end <= start:
            end = start + 0.4
        text = _normalize_space(seg_d.get("text", ""))
        trans.append({"start": start, "end": end, "text": text})

    # If there are no subtitles, synthesize from transcript directly
    if not subs:
        synthesized: List[Dict] = []
        for i, seg in enumerate(trans, start=1):
            seg_len = float(seg["end"]) - float(seg["start"])
            dur = _cap_duration(seg_len)
            start = float(seg["start"])
            end = start + dur
            text = _normalize_space(seg.get("text", ""))
            synthesized.append({
                "index": i,
                "start": start,
                "end": end,
                "text": text,
                "format": "srt",
            })
            print(f"[align:synthesize] #{i:>3} from transcript seg {seg['start']:.2f}-{seg['end']:.2f} len={seg_len:.2f} -> {start:.2f}-{end:.2f} | text={text!r}")
        _ensure_monotonic(synthesized, min_gap=MIN_GAP)
        return synthesized

    # Merge adjacent blanks and normalize text
    before_count = len(subs)
    subs = _merge_adjacent_blanks(subs)
    after_count = len(subs)
    if after_count != before_count:
        print(f"[align:merge] merged adjacent blank captions: {before_count} -> {after_count}")

    # Duration cap for incoming subs
    for s in subs:
        start = float(s["start"])
        end = float(s["end"])
        if end <= start:
            old_end = end
            end = start + MIN_DUR
            print(f"[align:fix] #{s.get('index','?')} end<=start {start:.2f}-{old_end:.2f} -> {start:.2f}-{end:.2f}")
        before_dur = end - start
        capped_end = start + _cap_duration(before_dur)
        if capped_end != end:
            print(f"[align:cap] #{s.get('index','?')} duration cap {before_dur:.2f}s -> {(capped_end-start):.2f}s")
        s["start"] = start
        s["end"] = capped_end

    # Compute transcript duration; if absent, infer a fake horizon based on number of subs
    if trans:
        t_start = min(seg["start"] for seg in trans)
        t_end = max(seg["end"] for seg in trans)
        transcript_span = max(t_end - t_start, float(len(subs)) * (MIN_DUR + MIN_GAP))
    else:
        # Placeholder horizon: spread subs uniformly over a conservative length
        transcript_span = float(max(10.0, len(subs) * (MIN_DUR + 0.5)))  # avoid clustering at start
        t_start = 0.0

    # First pass: match to transcript if available
    matches: List[Optional[int]] = []
    for s in subs:
        sub_iv = (float(s["start"]), float(s["end"]))
        idx = _match_transcript_segment(sub_iv, trans) if trans else None
        if idx is None and trans:
            idx = _closest_transcript_index_by_time(_interval_center(sub_iv), trans)
        matches.append(idx)

    # Prepare corrected list
    corrected: List[Dict] = []
    # Track last end to ensure monotonicity with MIN_GAP
    last_end = 0.0

    for i, (s, idx) in enumerate(zip(subs, matches), start=1):
        original = dict(s)
        new_s = dict(s)
        if idx is not None:
            seg = trans[idx]
            print(f"[align:match] #{i:>3} matched transcript seg {idx} [{seg['start']:.2f}-{seg['end']:.2f}]")
            # Apply text and refit times against segment, but enforce realistic duration
            _apply_text_from_transcript(new_s, seg)
            _refit_times_to_segment(new_s, seg)
            # Re-cap duration within realistic bounds
            before_dur = float(new_s["end"]) - float(new_s["start"])
            dur = _cap_duration(before_dur)
            if dur != before_dur:
                print(f"[align:cap] #{i:>3} duration (after refit) {before_dur:.2f}s -> {dur:.2f}s")
            center = _interval_center((float(new_s["start"]), float(new_s["end"])))
            before_start, before_end = float(new_s["start"]), float(new_s["end"])
            new_s["start"] = max(0.0, center - dur / 2.0)
            new_s["end"] = new_s["start"] + dur
            if (before_start != new_s['start']) or (before_end != new_s['end']):
                print(f"[align:center] #{i:>3} centered {before_start:.2f}-{before_end:.2f} -> {new_s['start']:.2f}-{new_s['end']:.2f}")
        else:
            # No transcript: distribute uniformly across transcript_span to avoid clustering
            # Place this caption at a fraction along the horizon based on its order.
            frac = (i - 0.5) / max(1.0, float(len(subs)))
            target_center = t_start + frac * transcript_span
            dur = _cap_duration(float(s["end"]) - float(s["start"]))
            before_start, before_end = float(s["start"]), float(s["end"])
            new_s["start"] = max(0.0, target_center - dur / 2.0)
            new_s["end"] = new_s["start"] + dur
            print(f"[align:distribute] #{i:>3} {before_start:.2f}-{before_end:.2f} -> {new_s['start']:.2f}-{new_s['end']:.2f} (uniform over {transcript_span:.2f}s)")
            # Keep text normalized
            before_text = _normalize_space(new_s.get("text", ""))
            new_text = before_text
            # nothing to change except normalization already done on input; still log if changed
            if new_text != new_s.get("text", ""):
                print(f"[align:text] #{i:>3} normalized {new_s.get('text','')!r} -> {new_text!r}")
            new_s["text"] = new_text

        # Enforce monotonic with MIN_GAP
        if new_s["start"] < last_end + MIN_GAP:
            shift = (last_end + MIN_GAP) - new_s["start"]
            before_start, before_end = float(new_s["start"]), float(new_s["end"])
            new_s["start"] += shift
            new_s["end"] += shift
            print(f"[align:gap] #{i:>3} shift +{shift:.2f}s to enforce gap -> {new_s['start']:.2f}-{new_s['end']:.2f} (prev_end={last_end:.2f})")

        # Final cap: ensure duration in bounds
        dur_final_cap_in = float(new_s["end"]) - float(new_s["start"])
        dur_final = _cap_duration(dur_final_cap_in)
        if (new_s["end"] - new_s["start"]) != dur_final:
            before_end = float(new_s["end"])
            new_s["end"] = new_s["start"] + dur_final
            print(f"[align:cap] #{i:>3} final duration cap {dur_final_cap_in:.2f}s -> {(new_s['end']-new_s['start']):.2f}s (end {before_end:.2f} -> {new_s['end']:.2f})")

        last_end = float(new_s["end"])

        # Field-wise change logging
        if original.get("format", "srt") != "srt":
            print(f"[align:format] #{i:>3} format {original.get('format')} -> 'srt'")
        new_s["index"] = i
        new_s["format"] = "srt"
        corrected.append(new_s)

        # Print consolidated correction summary for this subtitle
        changed_text = (_normalize_space(original.get("text","")) != new_s.get("text",""))
        changed_time = (float(original.get("start", 0.0)) != float(new_s["start"])) or (float(original.get("end", 0.0)) != float(new_s["end"]))
        if changed_time or changed_text:
            print(
                f"[align:summary] #{i:>3} "
                f"time {float(original.get('start',0.0)):.2f}-{float(original.get('end',0.0)):.2f} -> {new_s['start']:.2f}-{new_s['end']:.2f} | "
                f"text {(_normalize_space(original.get('text','')))!r} -> {new_s.get('text','')!r}"
            )

    # Enforce overall monotonic timing again (in-place) and minimal gap
    _ensure_monotonic(corrected, min_gap=MIN_GAP)

    # Reindex to ensure indices are strictly increasing and consecutive
    for i, s in enumerate(corrected, start=1):
        if s.get("index") != i:
            print(f"[align:index] #{s.get('index','?')} -> #{i}")
        s["index"] = i
        s["format"] = "srt"

    return corrected
