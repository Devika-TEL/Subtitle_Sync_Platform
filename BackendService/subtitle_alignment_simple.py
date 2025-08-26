"""
Subtitle alignment utility (pure Python, no web framework).

This module provides a single public function `align_subtitles_to_transcript` that realigns a list of subtitle
cues to a given reference transcript with timestamps. The alignment uses a lightweight, structure-first approach:
- Tokenizes and normalizes text for robust matching
- Performs greedy, monotonic alignment between transcript segments and subtitle cues
- Adjusts subtitle start/end times based on matched transcript time ranges
- Preserves relative intra-cue duration and clamps to valid ranges
- Resolves overlaps and enforces minimal gaps and durations

This is intended for direct use from scripts or REPL sessions. It does not depend on any
web framework or external libraries.

Data contracts:
- transcript: List[dict] with required keys:
    - "text": str
    - "start": float (seconds)
    - "end": float (seconds)
- subtitles: List[dict] with required keys:
    - "text": str
    - "start": float (seconds)
    - "end": float (seconds)

Both lists should be ordered in time (start ascending). If not, we sort them.

Example
-------
>>> transcript = [
...   {"text": "Hello world", "start": 0.0, "end": 1.2},
...   {"text": "This is a demo", "start": 1.3, "end": 3.0},
...   {"text": "Enjoy!", "start": 3.0, "end": 4.0},
... ]
>>> subs = [
...   {"text": "Hello world", "start": 0.5, "end": 2.0},
...   {"text": "This is demo", "start": 2.2, "end": 4.2},
... ]
>>> aligned = align_subtitles_to_transcript(transcript, subs)
>>> aligned[0]["start"], aligned[0]["end"]  # approximately matches 0.0..1.2
(0.0, 1.2)
>>> aligned[1]["start"] >= 1.3 and aligned[1]["end"] <= 4.0
True

Design notes
------------
- Matching strategy:
  We normalize text (lowercase, strip punctuation/extra whitespace), then compute simple similarity via
  token-overlap Jaccard. For each subtitle, we search forward in transcript segments (monotonic constraint)
  and greedily merge one or more consecutive transcript segments to get the best similarity above a threshold.
- Timing strategy:
  If we matched a span in the transcript, we adopt the span timings, scaled by the proportion of subtitle text
  length relative to span text length to approximate duration distribution. If scaling is uncertain, we use the
  span bounds directly.
- Safety and cleanup:
  We enforce minimum duration and clamp within neighbor bounds to prevent overlaps, then apply a final overlap
  resolution pass to ensure non-decreasing start times and minimal gaps.

Limitations
-----------
This is a heuristic approach. For high-accuracy alignment, consider forced alignment on audio (e.g., WhisperX),
or word-level timestamps from ASR. This function is suitable for improving mismatched captions when the transcript
is a trustworthy reference.

"""

from typing import List, Dict, Tuple, Any
import re

_PUNCT_RE = re.compile(r"[^\w\s']", flags=re.UNICODE)
_WS_RE = re.compile(r"\s+")

def _normalize_text(s: str) -> str:
    """Lowercase, strip punctuation (keep apostrophes), squeeze whitespace."""
    s = s.lower().strip()
    s = _PUNCT_RE.sub(" ", s)
    s = _WS_RE.sub(" ", s).strip()
    return s

def _tokens(s: str) -> List[str]:
    return [t for t in _normalize_text(s).split(" ") if t]

def _jaccard(a_tokens: List[str], b_tokens: List[str]) -> float:
    if not a_tokens and not b_tokens:
        return 1.0
    if not a_tokens or not b_tokens:
        return 0.0
    a, b = set(a_tokens), set(b_tokens)
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0

def _safe_float(v, default=0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default

def _sort_by_start(items: List[Dict]) -> List[Dict]:
    # Be defensive: if items may include non-dicts (e.g., strings), coerce to dicts with text only
    normed: List[Dict] = []
    for it in items:
        if isinstance(it, dict):
            normed.append(it)
        else:
            normed.append({"text": str(it) if it is not None else "", "start": 0.0, "end": 0.0})
    return sorted(normed, key=lambda x: _safe_float(x.get("start", 0.0)))

def _duration(item: Dict) -> float:
    return max(0.0, _safe_float(item.get("end", 0.0)) - _safe_float(item.get("start", 0.0)))

def _merge_texts(items: List[Dict]) -> str:
    texts: List[str] = []
    for it in items:
        if isinstance(it, dict):
            t = str(it.get("text", "")).strip()
        else:
            t = str(it).strip()
        if t:
            texts.append(t)
    return " ".join(texts)

def _span_time(items: List[Dict]) -> Tuple[float, float]:
    if not items:
        return (0.0, 0.0)
    return (_safe_float(items[0].get("start", 0.0)), _safe_float(items[-1].get("end", 0.0)))

def _clip(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, val))

def _enforce_monotonic_nonoverlap(subs: List[Dict], min_gap: float = 0.02, min_dur: float = 0.2) -> List[Dict]:
    """
    Make sure subtitle timings are monotonic and non-overlapping.
    - Ensures start[i] >= end[i-1] + min_gap
    - Ensures duration >= min_dur (expanding end if necessary within observed bounds)
    """
    result = _sort_by_start(subs)
    # First pass: enforce monotonic starts and min duration
    for i, s in enumerate(result):
        start = _safe_float(s.get("start", 0.0))
        end = _safe_float(s.get("end", 0.0))
        if i > 0:
            prev_end = _safe_float(result[i - 1].get("end", 0.0))
            start = max(start, prev_end + min_gap)
        if end <= start + min_dur:
            end = start + min_dur
        s["start"], s["end"] = start, max(end, start)
    # Second pass: ensure next starts after current with min gap; if needed, shrink current slightly
    for i in range(len(result) - 1):
        cur = result[i]
        nxt = result[i + 1]
        if _safe_float(nxt["start"]) < _safe_float(cur["end"]) + min_gap:
            # push next start forward if needed
            nxt["start"] = _safe_float(cur["end"]) + min_gap
            if _safe_float(nxt["end"]) < _safe_float(nxt["start"]) + min_dur:
                nxt["end"] = _safe_float(nxt["start"]) + min_dur
    return result

def _best_transcript_span_for_sub(
    sub_tokens: List[str],
    transcript: List[Dict],
    start_idx: int,
    max_span: int = 5,
    min_sim: float = 0.2,
) -> Tuple[int, int, float]:
    """
    Find the best contiguous span [i, j] of transcript segments starting from start_idx within max_span
    that maximizes Jaccard similarity to the subtitle tokens. Returns (i, j_inclusive, score).
    If no span exceeds min_sim, returns (start_idx, start_idx, 0.0) as a fallback.
    """
    best_i, best_j, best_score = start_idx, start_idx, 0.0
    # Explore spans up to max_span
    merged_tokens_cache = []
    accumulated_text = ""
    for i in range(start_idx, min(len(transcript), start_idx + max_span)):
        # reset span building from (i..)
        span_text = ""
        for j in range(i, min(len(transcript), i + max_span)):
            # incrementally grow span text
            if j == i:
                span_text = str(transcript[j].get("text", ""))
            else:
                span_text = (span_text + " " + str(transcript[j].get("text", ""))).strip()
            span_tokens = _tokens(span_text)
            score = _jaccard(sub_tokens, span_tokens)
            if score > best_score:
                best_i, best_j, best_score = i, j, score
    if best_score < min_sim:
        return (start_idx, start_idx, 0.0)
    return (best_i, best_j, best_score)

def _distribute_time_within_span(
    sub_text: str, span_text: str, span_start: float, span_end: float
) -> Tuple[float, float]:
    """
    Estimate a subtitle start/end within a matched transcript span,
    proportionally to text length. If texts are comparable length,
    use the full span; otherwise, shrink proportionally.
    """
    s_len = max(1, len(_normalize_text(sub_text)))
    t_len = max(1, len(_normalize_text(span_text)))
    ratio = min(1.25, max(0.5, s_len / t_len))  # avoid extreme scaling
    span_dur = max(0.0, span_end - span_start)
    new_dur = span_dur * ratio
    # center the new duration within the span
    center = span_start + span_dur / 2.0
    new_start = center - new_dur / 2.0
    new_end = center + new_dur / 2.0
    # Clamp within the span bounds
    return (_clip(new_start, span_start, span_end), _clip(new_end, span_start, span_end))

# PUBLIC_INTERFACE
def align_subtitles_to_transcript(
    transcript: List[Dict],
    subtitles: List[Dict],
    *,
    max_span: int = 5,
    min_similarity: float = 0.2,
    min_duration: float = 0.4,
    min_gap: float = 0.02,
) -> List[Dict]:
    """Align subtitles' start/end timings to a reference transcript as much as possible.

    This function is resilient to inputs that may contain strings instead of dicts by coercing
    each element into a dictionary with at least the 'text' field and default start/end values.

    Parameters
    ----------
    transcript : List[Dict]
        List of dicts with keys:
        - text: str
        - start: float (seconds)
        - end: float (seconds)
        May contain strings; they will be coerced to dicts.
        Must be roughly chronological. Will be sorted by start.
    subtitles : List[Dict]
        List of dicts with keys:
        - text: str
        - start: float (seconds)
        - end: float (seconds)
        May contain strings; they will be coerced to dicts.
        Will be aligned to the transcript. Will be sorted by start.
    max_span : int, optional
        Maximum number of transcript segments to consider as a contiguous match span for a single subtitle.
    min_similarity : float, optional
        Minimum Jaccard similarity for accepting a transcript span; if not met, falls back to original times
        but still participates in overlap cleanup.
    min_duration : float, optional
        Minimum duration for any subtitle (seconds).
    min_gap : float, optional
        Minimum gap enforced between consecutive subtitles (seconds).

    Returns
    -------
    List[Dict]
        A new list of subtitle dicts with adjusted "start"/"end" timings.
        The "text" and any extra fields from inputs are preserved where possible.

    Examples
    --------
    >>> transcript = [
    ...     {"text": "Good morning", "start": 0.0, "end": 1.0},
    ...     {"text": "and welcome to the show", "start": 1.0, "end": 2.5},
    ... ]
    >>> subtitles = [
    ...     {"text": "Good morning", "start": 0.4, "end": 1.4},
    ...     {"text": "Welcome to the show", "start": 2.0, "end": 3.2},
    ... ]
    >>> aligned = align_subtitles_to_transcript(transcript, subtitles)
    >>> round(aligned[0]["start"], 2), round(aligned[0]["end"], 2)
    (0.0, 1.0)
    """
    if not isinstance(transcript, list) or not isinstance(subtitles, list):
        raise TypeError("transcript and subtitles must be lists (elements may be dicts or strings)")

    # Coerce items to dicts if strings are present to avoid .get on str
    t_coerced = []
    for seg in transcript:
        if seg is None:
            continue
        if isinstance(seg, dict):
            text = str(seg.get("text", ""))
            start = _safe_float(seg.get("start", 0.0))
            end = _safe_float(seg.get("end", 0.0))
        else:
            text = str(seg)
            start = 0.0
            end = 0.0
        t_coerced.append({"text": text, "start": start, "end": end})
    t_segments = _sort_by_start(t_coerced)

    s_coerced = []
    for c in subtitles:
        if c is None:
            continue
        if isinstance(c, dict):
            s_coerced.append(dict(c))
        else:
            s_coerced.append({"text": str(c), "start": 0.0, "end": 0.0})
    s_cues = _sort_by_start(s_coerced)

    if not t_segments or not s_cues:
        # Nothing to align
        return s_cues

    # Precompute transcript tokens
    t_tokens = [_tokens(seg["text"]) for seg in t_segments]

    aligned: List[Dict] = []
    t_idx = 0  # monotonic pointer into transcript

    for cue in s_cues:
        sub_text = str(cue.get("text", ""))
        sub_tokens = _tokens(sub_text)
        # Find best span in transcript starting from t_idx
        i, j, score = _best_transcript_span_for_sub(
            sub_tokens=sub_tokens,
            transcript=t_segments,
            start_idx=t_idx,
            max_span=max_span,
            min_sim=min_similarity,
        )

        # Prepare the new cue dict
        new_cue = dict(cue)  # copy extra fields

        if score >= min_similarity:
            span = t_segments[i : j + 1]
            span_text = _merge_texts(span)
            span_start, span_end = _span_time(span)

            # Estimate start/end within the matched span
            est_start, est_end = _distribute_time_within_span(
                sub_text=sub_text, span_text=span_text, span_start=span_start, span_end=span_end
            )

            # Ensure minimal duration
            if est_end - est_start < min_duration:
                est_end = est_start + min_duration
                # Clamp to span if we exceeded
                if est_end > span_end:
                    # If can't expand, shift backward
                    shift = est_end - span_end
                    est_end = span_end
                    est_start = max(span_start, est_start - shift)

            new_cue["start"] = float(est_start)
            new_cue["end"] = float(est_end)

            # Advance transcript pointer past j, but don't skip too aggressively
            t_idx = max(t_idx, j)
        else:
            # Fallback: preserve original times, will be cleaned up later
            start_o = _safe_float(cue.get("start", 0.0))
            end_o = _safe_float(cue.get("end", start_o + min_duration))
            if end_o - start_o < min_duration:
                end_o = start_o + min_duration
            new_cue["start"] = float(start_o)
            new_cue["end"] = float(end_o)

        aligned.append(new_cue)

    # Final non-overlap enforcement and minimal gap/duration
    aligned = _enforce_monotonic_nonoverlap(aligned, min_gap=min_gap, min_dur=min_duration)

    # Normalize output: ensure each item has only keys: index, start, end, text, format.
    normalized: List[Dict] = []
    for idx, item in enumerate(aligned, start=1):
        # Extract with defaults
        start_v = _safe_float(item.get("start", 0.0))
        end_v = _safe_float(item.get("end", 0.0))
        text_v = str(item.get("text", "") if isinstance(item, dict) else "")
        fmt_v = ""
        # Some upstream paths might provide a format field; coerce to string if present
        if isinstance(item, dict) and "format" in item and item["format"] is not None:
            try:
                fmt_v = str(item["format"])
            except Exception:
                fmt_v = ""

        normalized.append({
            "index": int(idx),
            "start": float(start_v),
            "end": float(end_v),
            "text": text_v,
            "format": fmt_v,
        })

    return normalized


if __name__ == "__main__":
    # Simple manual demo for quick testing when running this file directly.
    demo_transcript = [
        {"text": "Hello world", "start": 0.0, "end": 1.0},
        {"text": "This is a demo", "start": 1.05, "end": 2.5},
        {"text": "Enjoy!", "start": 2.6, "end": 3.2},
    ]
    demo_subs = [
        {"text": "hello world", "start": 0.4, "end": 1.6},
        {"text": "this is demo", "start": 2.1, "end": 3.5},
    ]
    out = align_subtitles_to_transcript(demo_transcript, demo_subs)
    for i, c in enumerate(out, 1):
        print(f"{i}\n{c['start']:.2f} --> {c['end']:.2f}\n{c['text']}\n")
