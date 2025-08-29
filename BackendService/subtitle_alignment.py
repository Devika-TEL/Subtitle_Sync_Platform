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
- If aligning translations, call align_subtitles(..., cross_lingual=True) to avoid overwriting text.
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
def align_subtitles(
    transcript: List[Dict],
    subtitles: List[Dict],
    *,
    cross_lingual: bool = False,
    preserve_subtitle_text: Optional[bool] = None,
) -> List[Dict]:
    """
    Align and correct SRT-like subtitles using a transcript while guaranteeing that all
    timing values are seconds (float) at input, during processing, and in the returned output.

    Parameter formats (STRICTLY IN SECONDS):
        transcript: List[dict] where each item contains:
            - 'start': float seconds (>= 0)
            - 'end': float seconds (> start)
            - 'text': str (optional; default '')
        subtitles: List[dict] where each item contains:
            - 'index': int (optional; will be reindexed in output)
            - 'start': float seconds (>= 0)
            - 'end': float seconds (> start)
            - 'text': str (may be empty/blank)
            - 'format': str (optional; normalized to 'srt' in output)
        cross_lingual: If True, the transcript language differs from subtitle language.
            In this mode, only timings are adjusted; text is never replaced/normalized from transcript.
        preserve_subtitle_text: If provided, overrides cross_lingual with:
            - True  => preserve original subtitle text (timings-only)
            - False => allow text normalization/fill from transcript when appropriate
            - None  => defaults to True when cross_lingual=True, else False

    Returns:
        List[dict]: corrected subtitles with:
            - 'index': consecutive ints starting from 1
            - 'start': float seconds
            - 'end': float seconds
            - 'text': str
            - 'format': 'srt'

    Guarantees and safety:
        - All 'start' and 'end' are floats in seconds and non-negative.
        - Negative or missing times are clamped/fixed forward; zero/negative durations are extended to >= MIN_DUR.
        - Overlaps and out-of-order items are corrected to ensure monotonic timing with a minimum gap.
        - If inputs appear to be in milliseconds, a TypeError is raised with a clear message.
          We DO NOT auto-convert; callers must convert to seconds before calling.

    Edge cases handled:
        - Out-of-order, overlapping, negative, or missing times
        - Empty or sparse transcript (uniform distribution fallback)
        - Blank texts are merged to reduce fragmentation
        - Malformed items are skipped with diagnostic logging

    This logic supersedes older implementations and enforces seconds-only semantics.
    """
    # Parameters for realistic timing
    MIN_DUR = 0.8   # seconds
    MAX_DUR = 6.0   # seconds
    MIN_GAP = 0.08  # seconds between captions

    # Additional conservative thresholds (bugfix)
    ALREADY_GOOD_OVL_RATIO = 0.7   # require 70% overlap
    ALREADY_GOOD_CENTER_EPS = 0.20 # tighter center tolerance baseline

    # Determine text preservation behavior
    preserve_text = preserve_subtitle_text if preserve_subtitle_text is not None else bool(cross_lingual)

    def _cap_duration(d: float) -> float:
        return max(MIN_DUR, min(MAX_DUR, d))

    # --- Input validation: ensure seconds (floats) and not milliseconds ---
    def _collect_times(items: List[Dict]) -> List[float]:
        vals: List[float] = []
        for it in items or []:
            if it is None:
                continue
            if "start" in it and it["start"] is not None:
                vals.append(float(it["start"]))
            if "end" in it and it["end"] is not None:
                vals.append(float(it["end"]))
        return vals

    # Heuristic detection of ms-like values: many large values (e.g., thousands)
    def _looks_like_milliseconds(values: List[float]) -> bool:
        if not values:
            return False
        try:
            arr = sorted(abs(float(v)) for v in values if v is not None)
            if not arr:
                return False
            median = arr[len(arr)//2]
            mn = arr[0]
            # If median > 3000 and min > 100, likely ms scale
            return (median > 3000.0) and (mn > 100.0)
        except Exception:
            return False

    sub_times = _collect_times(subtitles or [])
    trs_times = _collect_times(transcript or [])

    if _looks_like_milliseconds(sub_times) or _looks_like_milliseconds(trs_times):
        raise TypeError("align_subtitles expects times in seconds (float). "
                        "Detected values that likely are milliseconds. Convert by dividing by 1000.0 before calling.")

    # Defensive copies and normalization (seconds-only)
    subs: List[Dict] = []
    for s in subtitles or []:
        try:
            start_val = s.get("start", 0.0)
            end_val = s.get("end", None)
            start_f = _safe_time(float(start_val))
            end_f = _safe_time(float(end_val)) if end_val is not None else start_f + MIN_DUR
            if end_f <= start_f:
                end_f = start_f + MIN_DUR
            subs.append({
                **s,
                "index": int(s.get("index", 0) or 0),
                "start": float(start_f),
                "end": float(end_f),
                "text": _normalize_space(s.get("text", "")),
                "format": s.get("format", "srt"),
            })
        except (ValueError, TypeError) as e:
            print(f"[align:error] malformed subtitle entry skipped: {e} | entry={s!r}")

    # Normalize transcript segments (seconds-only)
    trans: List[Dict] = []
    for seg in transcript or []:
        try:
            seg_d = _to_seg_dict(seg)
            start = _safe_time(float(seg_d.get("start", 0.0)))
            end = _safe_time(float(seg_d.get("end", start + 0.4)))
            if end <= start:
                end = start + 0.4
            text = _normalize_space(seg_d.get("text", ""))
            trans.append({"start": float(start), "end": float(end), "text": text})
        except (ValueError, TypeError) as e:
            print(f"[align:error] malformed transcript segment skipped: {e} | seg={seg!r}")

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
        _ensure_monotonic(synthesized, min_gap=MIN_GAP, min_duration=MIN_DUR)
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

    # Anchor bookkeeping: if a cue is "already good", mark as anchor. Subsequent cues cannot pull it earlier.
    anchors: List[Tuple[float, float]] = []  # list of (start, end) for anchored cues in order

    for i, (s, idx) in enumerate(zip(subs, matches), start=1):
        original = dict(s)
        new_s = dict(s)
        if idx is not None:
            seg = trans[idx]
            print(f"[align:match] #{i:>3} matched transcript seg {idx} [{seg['start']:.2f}-{seg['end']:.2f}]")
            # In timings-only (cross-lingual) mode, do not modify subtitle text.
            # Otherwise, apply transcript text when appropriate (e.g., to fill blanks/normalize).
            if not preserve_text:
                _apply_text_from_transcript(new_s, seg)

            # Conservative skip: if current times already overlap enough and are close in center, don't refit.
            seg_start, seg_end = float(seg["start"]), float(seg["end"])
            cur_start, cur_end = float(new_s["start"]), float(new_s["end"])
            cur_dur = max(0.1, cur_end - cur_start)
            ov = _overlap((cur_start, cur_end), (seg_start, seg_end))
            ov_ratio = ov / max(0.1, cur_dur)
            center_delta = abs(_interval_center((cur_start, cur_end)) - _interval_center((seg_start, seg_end)))

            good_center_eps = max(ALREADY_GOOD_CENTER_EPS, 0.12 * (seg_end - seg_start))
            already_good = (ov_ratio >= ALREADY_GOOD_OVL_RATIO and center_delta <= good_center_eps)

            if not already_good:
                _refit_times_to_segment(new_s, seg, min_dur=max(0.4, min(MIN_DUR, 0.8)))
            # Re-cap duration within realistic bounds
            before_dur = float(new_s["end"]) - float(new_s["start"])
            dur = _cap_duration(before_dur)
            if dur != before_dur:
                print(f"[align:cap] #{i:>3} duration (after refit) {before_dur:.2f}s -> {dur:.2f}s")
                # Adjust end only to respect cap; avoid re-centering to prevent drift
                before_end_adj = float(new_s["end"])
                new_s["end"] = new_s["start"] + dur
                if before_end_adj != new_s["end"]:
                    print(f"[align:endcap] #{i:>3} end {before_end_adj:.2f} -> {new_s['end']:.2f}")
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
            # Keep text normalized only; never inject transcript-based content here.
            before_text = _normalize_space(new_s.get("text", ""))
            new_text = before_text
            # nothing to change except normalization already done on input; still log if changed
            if new_text != new_s.get("text", ""):
                print(f"[align:text] #{i:>3} normalized {new_s.get('text','')!r} -> {new_text!r}")
            new_s["text"] = new_text

        # Enforce monotonic with MIN_GAP using minimal forward shift only (no pulling earlier cues).
        # Respect last anchor end to prevent cascading bunching at start.
        anchor_end = anchors[-1][1] if anchors else last_end
        if new_s["start"] < anchor_end + MIN_GAP:
            shift = (anchor_end + MIN_GAP) - new_s["start"]
            before_start, before_end = float(new_s["start"]), float(new_s["end"])
            new_s["start"] += shift
            new_s["end"] += shift
            print(f"[align:gap] #{i:>3} shift +{shift:.2f}s to enforce gap -> {new_s['start']:.2f}-{new_s['end']:.2f} (anchor_end={anchor_end:.2f})")

        # Final cap: ensure duration in bounds
        dur_final_cap_in = float(new_s["end"]) - float(new_s["start"])
        dur_final = _cap_duration(dur_final_cap_in)
        if (new_s["end"] - new_s["start"]) != dur_final:
            before_end = float(new_s["end"])
            new_s["end"] = new_s["start"] + dur_final
            print(f"[align:cap] #{i:>3} final duration cap {dur_final_cap_in:.2f}s -> {(new_s['end']-new_s['start']):.2f}s (end {before_end:.2f} -> {new_s['end']:.2f})")

        last_end = float(new_s["end"])

        # Determine if this cue can be considered an anchor (well-aligned to matched seg or left unchanged)
        if idx is not None:
            seg = trans[idx]
            seg_start, seg_end = float(seg["start"]), float(seg["end"])
            cur_start, cur_end = float(new_s["start"]), float(new_s["end"])
            cur_dur = max(0.1, cur_end - cur_start)
            ov = _overlap((cur_start, cur_end), (seg_start, seg_end))
            ov_ratio = ov / max(0.1, cur_dur)
            center_delta = abs(_interval_center((cur_start, cur_end)) - _interval_center((seg_start, seg_end)))
            if ov_ratio >= ALREADY_GOOD_OVL_RATIO and center_delta <= max(ALREADY_GOOD_CENTER_EPS, 0.12 * (seg_end - seg_start)):
                anchors.append((cur_start, cur_end))
        else:
            # With no transcript match, do not anchor to avoid locking potentially synthetic placement.
            pass

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
    # Use a smaller gap here to avoid unnecessary shifts if the stream is already monotonic.
    _ensure_monotonic(corrected, min_gap=min(MIN_GAP, 0.05), min_duration=MIN_DUR)

    # Reindex to ensure indices are strictly increasing and consecutive
    for i, s in enumerate(corrected, start=1):
        if s.get("index") != i:
            print(f"[align:index] #{s.get('index','?')} -> #{i}")
        s["index"] = i
        s["format"] = "srt"
        # Final explicit seconds-only sanity
        try:
            s["start"] = float(s["start"])
            s["end"] = float(s["end"])
        except Exception as e:
            raise TypeError(f"align_subtitles produced a non-float time for item #{i}: {e}")

        if s["start"] < 0.0 or s["end"] < 0.0:
            raise ValueError(f"align_subtitles produced negative time for item #{i}: start={s['start']} end={s['end']}")
        if s["end"] <= s["start"]:
            # Should never happen due to enforcement; guard anyway
            s["end"] = s["start"] + MIN_DUR

    return corrected
