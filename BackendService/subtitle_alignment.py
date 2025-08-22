"""
Subtitle alignment and correction utilities.

This module provides correct_subtitles(transcript, subtitles) which:
1) Compares each subtitle line's text with the corresponding segment in the transcript,
2) Identifies and corrects text mismatches (substitute transcript text for deviation),
3) Detects missing or extra subtitle lines and fixes accordingly,
4) Adjusts time spans (start/end) for subtitle segments if they deviate substantially,
5) Produces output subtitles in the same structure and format as input,
6) Maintains auxiliary metadata and structure as per the original format field.

Notes:
- This is a deterministic, dependency-free implementation aimed at CI stability.
- The transcript is assumed to be Whisper-like: a dict with key "segments", where each segment has:
    { 'start': float_seconds, 'end': float_seconds, 'text': str }
- The subtitles parameter is a list of cue dictionaries in a normalized structure used by this project:
    {
        'index': int (optional),
        'start': float_seconds,
        'end': float_seconds,
        'text': str | List[str],
        'format': 'srt' | 'vtt' | 'ass' | 'ssa' | 'sbv' | 'plain' | ...,
        'raw': Optional[dict]  # format-specific metadata to preserve
    }

The function returns a new list of subtitle dictionaries in the same format as provided,
preserving 'raw' and other auxiliary fields if present.
"""
from __future__ import annotations

from typing import List, Dict, Any, Tuple, Optional
import math
import re

# Backward compatibility alias to keep external imports stable if previously used
SubtitleCue = Dict[str, Any]
Transcript = Dict[str, Any]


def _norm_text(t: str) -> str:
    """Normalize text for comparison: lowercase, single spaces, strip punctuation +- basic."""
    t = t.lower().strip()
    # Remove repeated whitespace, normalize punctuation spaces
    t = re.sub(r"\s+", " ", t)
    # Light punctuation trim on ends
    t = t.strip(" .,!?:;\"'“”‘’()[]{}")
    return t


def _duration(cue: Dict[str, Any]) -> float:
    return max(0.0, float(cue.get("end", 0.0)) - float(cue.get("start", 0.0)))


def _merge_text_lines(text: Any) -> str:
    if isinstance(text, list):
        return " ".join([ln.strip() for ln in text if str(ln).strip() != ""]).strip()
    return str(text or "").strip()


def _split_text_for_format(text: str, fmt: str, original: Any) -> Any:
    """
    Split or shape text according to the given format and original structure:
    - For SRT/VTT: retain multi-line if original had it; otherwise single line.
    - For ASS/SSA: return single line (dialogue lines usually single).
    - For SBV/plain: single line.
    """
    if fmt in ("srt", "vtt"):
        # Preserve number of lines if original was a list
        if isinstance(original, list):
            # naive split into len lines by balancing words
            n = len(original)
            words = text.split()
            if n <= 1 or len(words) <= 4:
                return [text]
            # split words across n lines
            lines: List[str] = []
            per = max(1, math.ceil(len(words) / n))
            for i in range(0, len(words), per):
                lines.append(" ".join(words[i : i + per]))
            return lines[:n] if len(lines) >= n else lines
        # else keep single line
        return text
    if fmt in ("ass", "ssa", "sbv", "plain", "srt-txt", "unknown"):
        return text
    return text


def _shape_time_for_format(start: float, end: float, fmt: str, raw: Optional[dict]) -> Tuple[float, float]:
    """
    Placeholder to adjust time shape per format if needed.
    This function keeps seconds floats; formatting to string happens elsewhere in I/O.
    """
    start = max(0.0, float(start))
    end = max(start, float(end))
    return start, end


def _greedy_align(trans_segments: List[Dict[str, Any]], cues: List[Dict[str, Any]]) -> List[Tuple[int, int]]:
    """
    Greedy alignment between whisper transcript segments and subtitle cues based on time overlap primarily,
    with fallback to text similarity.

    Returns a list of (seg_idx, cue_idx) pairs in monotonically increasing order.
    """
    # Precompute intervals
    seg_intervals = [(float(s.get("start", 0.0)), float(s.get("end", 0.0))) for s in trans_segments]
    cue_intervals = [(float(c.get("start", 0.0)), float(c.get("end", 0.0))) for c in cues]
    seg_texts = [_norm_text(str(s.get("text", ""))) for s in trans_segments]
    cue_texts = [_norm_text(_merge_text_lines(c.get("text"))) for c in cues]

    def overlap(a: Tuple[float, float], b: Tuple[float, float]) -> float:
        s1, e1 = a
        s2, e2 = b
        inter = max(0.0, min(e1, e2) - max(s1, s2))
        dur = max(1e-6, (e1 - s1) + (e2 - s2) - inter)
        return inter / dur  # Jaccard-like

    pairs: List[Tuple[int, int]] = []
    ci = 0
    for si in range(len(trans_segments)):
        best_c = -1
        best_score = -1.0
        for cj in range(ci, len(cues)):
            o = overlap(seg_intervals[si], cue_intervals[cj])
            score = o
            # Slight text bonus if words overlap
            if seg_texts[si] and cue_texts[cj]:
                # simple token overlap ratio
                sg = set(seg_texts[si].split())
                cg = set(cue_texts[cj].split())
                if sg and cg:
                    score += 0.2 * (len(sg & cg) / len(sg | cg))
            if score > best_score:
                best_score = score
                best_c = cj
            # Early stop if strong overlap
            if best_score >= 0.9:
                break
        if best_c >= 0:
            pairs.append((si, best_c))
            ci = best_c + 1
    return pairs


def _build_index_map(pairs: List[Tuple[int, int]], n_segs: int, n_cues: int) -> Tuple[Dict[int, int], Dict[int, int]]:
    seg_to_cue = {}
    cue_to_seg = {}
    for si, ci in pairs:
        if si not in seg_to_cue and ci not in cue_to_seg:
            seg_to_cue[si] = ci
            cue_to_seg[ci] = si
    return seg_to_cue, cue_to_seg


def _interpolate_time(prev_end: float, next_start: float, default_dur: float = 1.5) -> Tuple[float, float]:
    """Create a reasonable time window between neighbors when inserting a missing cue."""
    if math.isfinite(prev_end) and math.isfinite(next_start) and next_start > prev_end:
        # Use the mid segment
        mid = (prev_end + next_start) / 2.0
        dur = min(default_dur, max(0.6, (next_start - prev_end) * 0.8))
        return max(prev_end, mid - dur / 2.0), min(next_start, mid + dur / 2.0)
    # Fallback: extend after prev_end
    start = prev_end if math.isfinite(prev_end) else 0.0
    return start, start + default_dur


# PUBLIC_INTERFACE
def correct_subtitles(transcript: Dict[str, Any], subtitles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Correct subtitle cues based on the provided Whisper transcript.

    PUBLIC_INTERFACE
    Args:
        transcript: Whisper-like transcript dict with 'segments' list entries:
            { 'start': float_seconds, 'end': float_seconds, 'text': str }
        subtitles: A list of normalized subtitle cue dicts with fields:
            - 'start', 'end': floats in seconds
            - 'text': string or list of strings (for multi-line)
            - 'format': original format label (e.g., 'srt', 'vtt', 'ass', 'ssa', 'sbv', ...)
            - 'index': optional numeric index
            - 'raw': optional dict with format-specific metadata

    Returns:
        A new list of cue dictionaries corrected to match transcript text and timing, preserving
        original format labels and metadata structure ('raw', multi-line structure) as feasible.
    """
    # Validate minimal structure
    if not isinstance(transcript, dict):
        raise TypeError("transcript must be a dict with a 'segments' list")
    if not isinstance(subtitles, list):
        raise TypeError("subtitles must be a list of cue dicts")

    segments = list((transcript.get("segments") or []))
    cues = list(subtitles or [])

    # Safety: if either is empty, return cues unmodified.
    if not segments or not cues:
        return cues

    # Greedy monotonic time-based alignment
    pairs = _greedy_align(segments, cues)
    seg_to_cue, cue_to_seg = _build_index_map(pairs, len(segments), len(cues))

    fmt = str(cues[0].get("format", "srt")).lower()

    corrected: List[Dict[str, Any]] = []
    # First, iterate through aligned pairs to correct text and timing deviations.
    # We'll also record which cues are consumed.
    used_cues = set()

    # helper thresholds
    max_time_shift = 0.35  # seconds allowed deviation before adjusting
    min_duration = 0.6
    max_duration = 12.0

    for si, seg in enumerate(segments):
        seg_text = _merge_text_lines(seg.get("text", ""))
        seg_start = float(seg.get("start", 0.0))
        seg_end = float(seg.get("end", seg_start + 1.5))

        if si in seg_to_cue:
            ci = seg_to_cue[si]
            cue = cues[ci]
            used_cues.add(ci)

            # Text correction
            cue_text_raw = cue.get("text")
            cue_text = _merge_text_lines(cue_text_raw)
            if _norm_text(cue_text) != _norm_text(seg_text):
                new_text = _split_text_for_format(seg_text, fmt, cue_text_raw)
            else:
                new_text = cue_text_raw

            # Timing correction
            cue_start = float(cue.get("start", seg_start))
            cue_end = float(cue.get("end", seg_end))
            start = cue_start
            end = cue_end

            # If cue timing deviates notably, adjust towards transcript times
            if abs(cue_start - seg_start) > max_time_shift:
                start = seg_start
            if abs(cue_end - seg_end) > max_time_shift:
                end = seg_end

            # Fix pathological durations
            dur = max(min_duration, min(max_duration, end - start if end > start else min_duration))
            if end - start != dur:
                # Keep end anchored if it's closer to seg_end, else adjust start
                end = start + dur

            start, end = _shape_time_for_format(start, end, fmt, cue.get("raw"))

            # Preserve metadata
            new_cue = dict(cue)
            new_cue["text"] = new_text
            new_cue["start"] = start
            new_cue["end"] = end
            corrected.append(new_cue)
        else:
            # Missing cue for this transcript segment: synthesize a new cue
            # Determine placement around neighboring aligned cues
            prev_ci = seg_to_cue.get(si - 1, None)
            next_ci = seg_to_cue.get(si + 1, None)
            prev_end = float(cues[prev_ci]["end"]) if prev_ci is not None else float("nan")
            next_start = float(cues[next_ci]["start"]) if next_ci is not None else float("nan")
            start, end = _interpolate_time(prev_end, next_start, default_dur=max(min_duration, seg_end - seg_start or 1.2))

            # Clamp within transcript times if reasonable overlap
            if not math.isnan(prev_end):
                start = max(min(seg_start, start), min(seg_end, start))
            if not math.isnan(next_start):
                end = min(max(seg_end, end), max(seg_start, end))

            start, end = _shape_time_for_format(start, end, fmt, None)
            text_shaped = _split_text_for_format(seg_text, fmt, [])

            # Create a new cue preserving structural fields
            new_index = (cues[-1].get("index") or len(cues)) + 1 if cues else len(corrected) + 1
            new_cue = {
                "index": new_index,
                "start": start,
                "end": end,
                "text": text_shaped,
                "format": fmt,
                "raw": None,  # no format-specific extras known for synthetic cue
            }
            corrected.append(new_cue)

    # Handle extra cues (those without corresponding transcript segments):
    # We keep them but attenuate by snapping their text to nearest transcript segment if overlap is decent,
    # otherwise we can drop or mark them. We'll keep and correct text if nearest overlap >= 0.2.
    def _nearest_seg_for_interval(a: Tuple[float, float]) -> Optional[int]:
        best_si = None
        best_score = -1.0
        for si, s in enumerate(segments):
            b = (float(s.get("start", 0.0)), float(s.get("end", 0.0)))
            inter = max(0.0, min(a[1], b[1]) - max(a[0], b[0]))
            dur = max(1e-6, (a[1] - a[0]) + (b[1] - b[0]) - inter)
            score = inter / dur
            if score > best_score:
                best_score = score
                best_si = si
        return best_si if best_score >= 0.2 else None

    for ci, cue in enumerate(cues):
        if ci in used_cues:
            continue
        # Unaligned cue: adjust or keep
        a = (float(cue.get("start", 0.0)), float(cue.get("end", 0.0)))
        si = _nearest_seg_for_interval(a)
        if si is None:
            # Keep as-is to preserve overall structure/metadata
            corrected.append(cue)
        else:
            seg = segments[si]
            seg_text = _merge_text_lines(seg.get("text", ""))
            cue_text_raw = cue.get("text")
            new_text = _split_text_for_format(seg_text, fmt, cue_text_raw)
            start, end = _shape_time_for_format(float(seg.get("start", a[0])), float(seg.get("end", a[1])), fmt, cue.get("raw"))

            new_cue = dict(cue)
            new_cue["text"] = new_text
            new_cue["start"] = start
            new_cue["end"] = end
            corrected.append(new_cue)

    # Re-sort by start time to ensure proper order, then reindex if 'index' exists
    corrected.sort(key=lambda c: (float(c.get("start", 0.0)), float(c.get("end", 0.0))))
    # Maintain original indices if present; else assign sequential for SRT-like formats
    has_any_index = any("index" in c for c in corrected)
    if has_any_index and fmt in ("srt", "srt-txt", "vtt"):
        for i, c in enumerate(corrected, start=1):
            c["index"] = i

    return corrected
