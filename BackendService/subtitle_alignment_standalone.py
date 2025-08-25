#!/usr/bin/env python3
"""
Subtitle Alignment Standalone Utility

This script provides a self-contained function to align subtitle cues to a reference
transcript using both timing and text similarity, and interpolates timings for cues
with missing or unreliable timestamps.

It does NOT import anything from the project; all logic is contained in this file.

Usage:
- As a script:
    python subtitle_alignment_standalone.py

  This runs a built-in example that demonstrates aligning a small set of subtitle
  cues against a transcript and prints the aligned output.

- As a module:
    from subtitle_alignment_standalone import align_subtitles_to_transcript

    aligned = align_subtitles_to_transcript(
        transcript=[{"start": 0.0, "end": 2.0, "text": "Hello there"},
                    {"start": 2.0, "end": 4.0, "text": "How are you doing"},
                    {"start": 4.0, "end": 6.0, "text": "I am fine thank you"}],
        subtitles=[{"start": 0.1, "end": 1.8, "text": "Hello there"},
                   {"start": None, "end": None, "text": "How are you doing?"},
                   {"start": 4.2, "end": 5.8, "text": "I'm fine, thank you."}],
        config={"max_shift_seconds": 1.5, "similarity_threshold": 0.35}
    )

Input formats:
- transcript: list of dicts with keys:
    - start: float (seconds)
    - end: float (seconds)
    - text: str
- subtitles: list of dicts with keys:
    - start: float or None
    - end: float or None
    - text: str

Output:
- A list of aligned subtitle dicts (in the same order as input subtitles), each with:
    - start: float
    - end: float
    - text: str
    - source_index: int (original index in input subtitles)
    - matched_transcript_index: int or None
    - similarity: float (0..1)

Algorithm overview:
1. Normalize and tokenize text for both transcript and subtitle cues.
2. Compute text similarity using a hybrid of:
   - Jaccard similarity on word sets,
   - Cosine-like similarity on term-frequency vectors,
   - Character-level longest common subsequence ratio.
3. For each subtitle cue, compute a matching score with candidate transcript
   segments that are temporally close (within a window) or textually similar.
4. The composite score balances timing and textual similarity; pick the best match.
5. Set subtitle timing using matched transcript timing when the match is strong.
6. For cues without strong matches or missing timestamps, interpolate timings:
   - Use neighbors' aligned times (forward/backward fill),
   - Maintain average durations and monotonic non-overlapping constraints.
7. Enforce global constraints:
   - Non-decreasing start times,
   - Minimum and maximum duration bounds,
   - Optional max shift limit from original times.

Configuration (optional dict):
- max_shift_seconds: float or None. If set, limit how far we move a cue from its original time.
- similarity_threshold: float in [0,1]. Minimum similarity to accept direct time from transcript.
- time_weight: float. Weight for time proximity in composite scoring (default 0.35).
- text_weight: float. Weight for text similarity in composite scoring (default 0.65).
- search_window_seconds: float. How far (± seconds) around cue time to search in transcript (default 6.0).
- min_duration: float. Minimum enforced cue duration in seconds (default 0.8).
- max_duration: float. Maximum enforced cue duration in seconds (default 8.0).
- avg_duration_hint: float or None. If provided, used during interpolation (default None).
- punctuation_sensitive: bool. If False, punctuation is stripped before similarity (default False).

Notes:
- This utility aims to be robust for common alignment tasks. For production use,
  consider more advanced language-aware tokenization and alignment models when needed.

"""

from typing import List, Dict, Optional, Tuple
import math
import re
import itertools


# PUBLIC_INTERFACE
def align_subtitles_to_transcript(
    transcript: List[Dict],
    subtitles: List[Dict],
    config: Optional[Dict] = None
) -> List[Dict]:
    """
    Align subtitle cues to a reference transcript using timing preferences and text similarity.

    Parameters
    ----------
    transcript : list of dict
        Reference transcript segments; each dict must have:
        - start: float seconds
        - end: float seconds
        - text: str
    subtitles : list of dict
        Subtitle cues to align; each dict should have:
        - start: float seconds or None
        - end: float seconds or None
        - text: str
    config : dict, optional
        Configuration overrides. See module docstring for available keys.

    Returns
    -------
    list of dict
        Aligned subtitle cues where each item contains:
        - start: float seconds
        - end: float seconds
        - text: str
        - source_index: int (index from input subtitles)
        - matched_transcript_index: int or None
        - similarity: float (0..1)
    """
    cfg = _default_config()
    if config:
        cfg.update({k: v for k, v in config.items() if v is not None})

    # Preprocess and validate inputs
    t_segments = _normalize_segments(transcript, require_time=True, pun_sensitive=cfg["punctuation_sensitive"])
    s_cues = _normalize_segments(subtitles, require_time=False, pun_sensitive=cfg["punctuation_sensitive"])

    # Precompute term frequencies for similarity
    for seg in t_segments:
        seg["tokens"] = _tokenize(seg["text"])
        seg["tf"] = _term_freq(seg["tokens"])
    for cue in s_cues:
        cue["tokens"] = _tokenize(cue["text"])
        cue["tf"] = _term_freq(cue["tokens"])

    # Build search index by time (sorted transcript)
    t_sorted = sorted(enumerate(t_segments), key=lambda x: x[1]["start"])
    t_index = [i for i, _ in t_sorted]
    t_times = [seg["start"] for _, seg in t_sorted]

    aligned = []
    for s_idx, cue in enumerate(s_cues):
        best_idx, best_sim, best_score = _find_best_match(
            cue,
            t_segments,
            t_sorted,
            t_times,
            time_weight=cfg["time_weight"],
            text_weight=cfg["text_weight"],
            window=cfg["search_window_seconds"]
        )

        # Decide final times
        orig_start, orig_end = cue.get("start"), cue.get("end")

        if best_idx is not None and best_sim >= cfg["similarity_threshold"]:
            t_seg = t_segments[best_idx]
            new_start, new_end = t_seg["start"], t_seg["end"]
            # Respect max shift if configured and original time exists
            if cfg["max_shift_seconds"] is not None and orig_start is not None:
                new_start, new_end = _limit_shift(
                    orig_start, orig_end, new_start, new_end, cfg["max_shift_seconds"]
                )
        else:
            # Keep original if present; interpolation to be done later for missing times
            new_start, new_end = orig_start, orig_end

        aligned.append({
            "start": new_start,
            "end": new_end,
            "text": cue["text"],
            "source_index": s_idx,
            "matched_transcript_index": best_idx,
            "similarity": float(best_sim if best_idx is not None else 0.0),
            "_orig_start": orig_start,
            "_orig_end": orig_end,
        })

    # Interpolate any missing or invalid times
    aligned = _interpolate_and_enforce(aligned, cfg)

    # Remove helper fields
    for item in aligned:
        item.pop("_orig_start", None)
        item.pop("_orig_end", None)

    # Conform output: only index, start, end, text, format
    filtered = []
    for idx, it in enumerate(aligned):
        filtered.append({
            "index": it.get("source_index", idx),
            "start": float(it.get("start", 0.0)) if it.get("start") is not None else 0.0,
            "end": float(it.get("end", max(0.0, float(it.get("start", 0.0))))) if it.get("end") is not None else float(it.get("start", 0.0) or 0.0),
            "text": (it.get("text") or "").strip(),
            "format": "generic",
        })

    return filtered


# -----------------------
# Internal helpers
# -----------------------

def _default_config() -> Dict:
    return {
        "max_shift_seconds": None,            # or a float like 2.0
        "similarity_threshold": 0.35,
        "time_weight": 0.35,
        "text_weight": 0.65,
        "search_window_seconds": 6.0,
        "min_duration": 0.8,
        "max_duration": 8.0,
        "avg_duration_hint": None,
        "punctuation_sensitive": False,
    }


def _normalize_segments(items: List[Dict], require_time: bool, pun_sensitive: bool) -> List[Dict]:
    normalized = []
    for i, it in enumerate(items):
        text = it.get("text", "")
        if not pun_sensitive:
            text = _strip_punctuation(text)
        seg = {
            "start": float(it["start"]) if (it.get("start") is not None) else (None if not require_time else float(it["start"])),
            "end": float(it["end"]) if (it.get("end") is not None) else (None if not require_time else float(it["end"])),
            "text": text.strip(),
        }
        if require_time:
            if seg["start"] is None or seg["end"] is None:
                raise ValueError(f"Transcript segment at index {i} missing start/end")
            if seg["end"] < seg["start"]:
                seg["end"] = seg["start"]  # guard
        normalized.append(seg)
    return normalized


_WORD_RE = re.compile(r"[A-Za-z0-9']+")


def _strip_punctuation(s: str) -> str:
    # Keep alphanumerics and whitespace, replace other with space
    return re.sub(r"[^\w\s']", " ", s)


def _tokenize(s: str) -> List[str]:
    return [m.group(0).lower() for m in _WORD_RE.finditer(s.lower())]


def _term_freq(tokens: List[str]) -> Dict[str, float]:
    tf = {}
    for t in tokens:
        tf[t] = tf.get(t, 0.0) + 1.0
    n = float(len(tokens)) if tokens else 1.0
    return {k: v / n for k, v in tf.items()}


def _jaccard(a: List[str], b: List[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    inter = len(sa & sb)
    union = len(sa | sb)
    return inter / union if union else 0.0


def _cosine_like(tf_a: Dict[str, float], tf_b: Dict[str, float]) -> float:
    # Cosine-like without IDF to keep this file self-contained
    keys = set(tf_a.keys()) | set(tf_b.keys())
    if not keys:
        return 1.0
    dot = sum(tf_a.get(k, 0.0) * tf_b.get(k, 0.0) for k in keys)
    na = math.sqrt(sum((tf_a.get(k, 0.0))**2 for k in keys))
    nb = math.sqrt(sum((tf_b.get(k, 0.0))**2 for k in keys))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _lcs_ratio(a: str, b: str) -> float:
    # Character-level LCS ratio; O(n*m) dynamic programming
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    n, m = len(a), len(b)
    # Optimize memory by keeping only two rows
    prev = [0] * (m + 1)
    for i in range(1, n + 1):
        curr = [0] * (m + 1)
        ca = a[i - 1]
        for j in range(1, m + 1):
            if ca == b[j - 1]:
                curr[j] = prev[j - 1] + 1
            else:
                curr[j] = max(prev[j], curr[j - 1])
        prev = curr
    lcs_len = prev[m]
    return (2.0 * lcs_len) / (n + m)


def _hybrid_text_similarity(cue: Dict, seg: Dict]) -> float:
    # Aggregate multiple similarity measures
    j = _jaccard(cue["tokens"], seg["tokens"])
    c = _cosine_like(cue["tf"], seg["tf"])
    l = _lcs_ratio(cue["text"].lower(), seg["text"].lower())
    # Weighted average; emphasize semantic similarity slightly more
    return 0.4 * c + 0.35 * l + 0.25 * j


def _time_proximity_score(cue_time: Optional[float], seg_time: float, window: float) -> float:
    if cue_time is None:
        # No time -> neutral score
        return 0.5
    d = abs(cue_time - seg_time)
    if d >= window:
        return 0.0
    # Smoothly decay within window (cosine taper)
    return 0.5 * (1 + math.cos(math.pi * d / window))


def _find_candidates_by_time(t_sorted, t_times, center_time: Optional[float], window: float) -> List[int]:
    if center_time is None:
        # If no center time, consider all
        return [idx for idx, _ in t_sorted]
    # Binary search for left/right bounds
    left = _lower_bound(t_times, center_time - window)
    right = _upper_bound(t_times, center_time + window)
    return [t_sorted[i][0] for i in range(left, right)]


def _lower_bound(a: List[float], x: float) -> int:
    lo, hi = 0, len(a)
    while lo < hi:
        mid = (lo + hi) // 2
        if a[mid] < x:
            lo = mid + 1
        else:
            hi = mid
    return lo


def _upper_bound(a: List[float], x: float) -> int:
    lo, hi = 0, len(a)
    while lo < hi:
        mid = (lo + hi) // 2
        if a[mid] <= x:
            lo = mid + 1
        else:
            hi = mid
    return lo


def _find_best_match(
    cue: Dict,
    t_segments: List[Dict],
    t_sorted: List[Tuple[int, Dict]],
    t_times: List[float],
    time_weight: float,
    text_weight: float,
    window: float
) -> Tuple[Optional[int], float, float]:
    # Choose center time as cue midpoint if available
    cue_mid = None
    if cue.get("start") is not None and cue.get("end") is not None:
        cue_mid = 0.5 * (cue["start"] + cue["end"])
    elif cue.get("start") is not None:
        cue_mid = cue["start"]
    elif cue.get("end") is not None:
        cue_mid = cue["end"]

    candidates = _find_candidates_by_time(t_sorted, t_times, cue_mid, window)
    if not candidates:
        candidates = [idx for idx, _ in t_sorted]  # fallback

    best_idx, best_sim, best_score = None, 0.0, -1.0
    for idx in candidates:
        seg = t_segments[idx]
        text_sim = _hybrid_text_similarity(cue, seg)
        time_score = _time_proximity_score(cue_mid, 0.5 * (seg["start"] + seg["end"]), window)
        score = text_weight * text_sim + time_weight * time_score
        if score > best_score:
            best_score = score
            best_sim = text_sim
            best_idx = idx
    return best_idx, float(best_sim), float(best_score)


def _limit_shift(orig_start: Optional[float], orig_end: Optional[float],
                 new_start: float, new_end: float, max_shift: float) -> Tuple[float, float]:
    if orig_start is None:
        return new_start, new_end
    shift = new_start - orig_start
    if abs(shift) <= max_shift:
        return new_start, new_end
    # Clamp start to within max_shift, keep duration same as new
    duration = max(0.0, new_end - new_start)
    clamped_start = orig_start + (max_shift if shift > 0 else -max_shift)
    return clamped_start, clamped_start + duration


def _interpolate_and_enforce(aligned: List[Dict], cfg: Dict) -> List[Dict]:
    n = len(aligned)
    # Compute a reasonable average duration
    durations = [max(0.0, (x["end"] - x["start"])) for x in aligned if x.get("start") is not None and x.get("end") is not None]
    avg_dur = cfg["avg_duration_hint"] if cfg["avg_duration_hint"] else (sum(durations) / len(durations) if durations else 2.0)
    min_d, max_d = cfg["min_duration"], cfg["max_duration"]

    # First pass: fill missing times using nearby known times or transcript matches
    # Forward fill using previous known end + avg_dur
    last_end = None
    for i in range(n):
        s = aligned[i]
        if s.get("start") is None or s.get("end") is None or s["end"] < s["start"]:
            # Try derivative from matched transcript if available via similarity (already set)
            if s.get("start") is None or s.get("end") is None:
                if last_end is None:
                    # Start from zero
                    s["start"] = 0.0 if s.get("start") is None else s["start"]
                    s["end"] = s["start"] + avg_dur if s.get("end") is None else s["end"]
                else:
                    s["start"] = last_end
                    s["end"] = s["start"] + avg_dur
            elif s["end"] < s["start"]:
                s["end"] = s["start"] + avg_dur
        # Enforce duration bounds immediately
        dur = s["end"] - s["start"]
        if dur < min_d:
            s["end"] = s["start"] + min_d
        elif dur > max_d:
            s["end"] = s["start"] + max_d
        last_end = s["end"]

    # Second pass: ensure monotonic non-overlapping and smooth durations
    for i in range(1, n):
        prev = aligned[i - 1]
        cur = aligned[i]
        if cur["start"] < prev["end"]:
            cur["start"] = prev["end"]
            # Refit duration within bounds
            cur_dur = cur["end"] - cur["start"]
            if cur_dur < min_d:
                cur["end"] = cur["start"] + min_d
            elif cur_dur > max_d:
                cur["end"] = cur["start"] + max_d

    # Optional: backward pass to reduce excessive gaps
    for i in reversed(range(n - 1)):
        cur = aligned[i]
        nxt = aligned[i + 1]
        # If excessive gap, gently expand current end up to max_d
        gap = nxt["start"] - cur["end"]
        if gap > max(0.0, 0.25 * avg_dur):
            new_end = min(cur["start"] + max_d, cur["end"] + 0.25 * gap)
            if new_end > cur["end"]:
                cur["end"] = new_end

    return aligned


# -----------------------
# Example / CLI
# -----------------------

def main():
    """
    Run a small demonstration with sample transcript and subtitle data.
    Prints aligned subtitle cues.
    """
    transcript = [
        {"start": 0.00, "end": 2.10, "text": "Hello there"},
        {"start": 2.10, "end": 4.20, "text": "How are you doing"},
        {"start": 4.20, "end": 6.40, "text": "I am fine thank you"},
        {"start": 6.40, "end": 8.50, "text": "Let's get started"},
    ]

    subtitles = [
        {"start": 0.05, "end": 1.90, "text": "Hello there"},
        {"start": None, "end": None, "text": "How are you doing?"},
        {"start": 4.30, "end": 5.70, "text": "I'm fine, thank you."},
        {"start": None, "end": None, "text": "Let's get started!"},
    ]

    config = {
        "max_shift_seconds": 1.5,
        "similarity_threshold": 0.30,
        "time_weight": 0.35,
        "text_weight": 0.65,
        "search_window_seconds": 5.0,
        "min_duration": 1.0,
        "max_duration": 6.0,
        "avg_duration_hint": 2.0,
        "punctuation_sensitive": False,
    }

    aligned = align_subtitles_to_transcript(transcript, subtitles, config)

    print("Aligned Subtitles:")
    for i, a in enumerate(aligned, 1):
        print(f"{i:02d} | {a['start']:.2f} --> {a['end']:.2f} | sim={a['similarity']:.2f} | text={a['text']}")


# Entry point
if __name__ == "__main__":
    main()
