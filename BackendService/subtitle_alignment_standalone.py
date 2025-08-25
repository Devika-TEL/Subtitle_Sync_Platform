#!/usr/bin/env python3
"""
Subtitle Alignment Standalone Utility

This script provides a self-contained function to align subtitle cues to a reference
transcript using both timing and text similarity, and interpolates timings for cues
with missing or unreliable timestamps.

It does NOT import anything from the project; all logic is contained in this file.

Enhancements (bug fix):
- More assertive timestamp correction when cues are inaccurate.
- Guaranteed interpolation to concrete times when timestamps are missing.
- Clear text replacement from transcript for empty/mismatched texts when similarity is moderate/strong.
- Final smoothing ensures non-overlap and readable durations.

Usage:
- As a script:
    python subtitle_alignment_standalone.py

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

Output:
- A list of aligned subtitle dicts that visibly reflect corrected timestamps and texts.

"""
from typing import List, Dict, Optional, Tuple
import math
import re

# PUBLIC_INTERFACE
def align_subtitles_to_transcript(
    transcript: List[Dict],
    subtitles: List[Dict],
    config: Optional[Dict] = None
) -> List[Dict]:
    """
    Align subtitle cues to a reference transcript using timing preferences and text similarity.

    PUBLIC_INTERFACE
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
        Configuration overrides:
        - max_shift_seconds: float or None. If set, limit how far we move a cue from its original time.
        - similarity_threshold: float in [0,1]. Minimum similarity to accept direct time from transcript (default 0.35).
        - time_weight: float. Weight for time proximity in composite scoring (default 0.35).
        - text_weight: float. Weight for text similarity in composite scoring (default 0.65).
        - search_window_seconds: float. How far (± seconds) around cue time to search in transcript (default 6.0).
        - min_duration: float. Minimum enforced cue duration in seconds (default 0.8).
        - max_duration: float. Maximum enforced cue duration in seconds (default 8.0).
        - avg_duration_hint: float or None. If provided, used during interpolation (default None).
        - punctuation_sensitive: bool. If False, punctuation is stripped before similarity (default False).

    Returns
    -------
    list of dict
        Aligned subtitle cues in input order, each containing:
        - index: original index
        - start: float seconds (corrected)
        - end: float seconds (corrected)
        - text: str (possibly corrected from transcript)
        - format: 'generic'
    """
    cfg = _default_config()
    if config:
        cfg.update({k: v for k, v in config.items() if v is not None})

    # Thresholds and constants
    min_similarity_for_text_correction = max(0.5, cfg["similarity_threshold"])
    min_similarity_for_time_trust = max(0.35, cfg["similarity_threshold"] * 0.9)
    intercue_gap = 0.06  # 60ms to avoid overlaps

    # Normalize
    t_segments = _normalize_segments(transcript, require_time=True, pun_sensitive=cfg["punctuation_sensitive"])
    s_cues = _normalize_segments(subtitles, require_time=False, pun_sensitive=cfg["punctuation_sensitive"])

    if not t_segments:
        # Nothing to align against; ensure outputs are concrete durations if times missing
        out = []
        for i, c in enumerate(s_cues):
            start = c.get("start")
            end = c.get("end")
            if start is None or end is None or end < start:
                start = float(start or 0.0)
                end = start + max(cfg["min_duration"], 1.0)
            out.append({
                "index": i,
                "start": float(start),
                "end": float(end),
                "text": (c.get("text") or "").strip(),
                "format": "generic",
            })
        return out

    # Precompute tokens/tf
    for seg in t_segments:
        seg["tokens"] = _tokenize(seg["text"])
        seg["tf"] = _term_freq(seg["tokens"])
        seg["_mid"] = 0.5 * (seg["start"] + seg["end"])
    for cue in s_cues:
        cue["tokens"] = _tokenize(cue["text"])
        cue["tf"] = _term_freq(cue["tokens"])

    # Sorting for time indexing
    t_sorted = sorted(enumerate(t_segments), key=lambda x: x[1]["start"])
    t_times = [seg["start"] for _, seg in t_sorted]

    aligned: List[Dict] = []
    for s_idx, cue in enumerate(s_cues):
        best_idx, best_sim, best_score = _find_best_match(
            cue, t_segments, t_sorted, t_times,
            time_weight=cfg["time_weight"], text_weight=cfg["text_weight"],
            window=cfg["search_window_seconds"]
        )

        orig_start, orig_end = cue.get("start"), cue.get("end")
        cue_mid = _mid_from_times(orig_start, orig_end)

        new_start, new_end = orig_start, orig_end
        chosen_idx = best_idx

        if chosen_idx is not None:
            t_seg = t_segments[chosen_idx]
            t_start, t_end, t_mid = t_seg["start"], t_seg["end"], t_seg["_mid"]
            # Strong text match: adopt transcript window adjusted for reading speed
            if best_sim >= min_similarity_for_text_correction:
                desired = _estimate_duration_for_text(
                    cue.get("text") or t_seg.get("text", ""),
                    min_duration=cgf(cfg, "min_duration"),
                    max_duration=cgf(cfg, "max_duration"),
                    max_cps=25.0
                )
                tw = max(t_end - t_start, 0.0)
                if desired <= tw:
                    new_start = t_start + 0.5 * (tw - desired)
                    new_end = new_start + desired
                else:
                    overflow = desired - tw
                    new_start = t_start - 0.5 * overflow
                    new_end = t_end + 0.5 * overflow
            else:
                # Moderate/weak text: nudge towards transcript midpoint assertively.
                alpha = 0.65 if best_score >= 0.55 else 0.45
                # Choose duration: prefer existing duration if valid, else transcript duration
                if orig_start is not None and orig_end is not None and orig_end > orig_start:
                    dur = clamp(orig_end - orig_start, cgf(cfg, "min_duration"), cgf(cfg, "max_duration"))
                else:
                    dur = clamp(t_end - t_start, cgf(cfg, "min_duration"), cgf(cfg, "max_duration"))
                if cue_mid is None:
                    # If no original time, adopt transcript window directly
                    new_start, new_end = t_start, t_end
                else:
                    desired_mid = cue_mid + alpha * (t_mid - cue_mid)
                    new_start = desired_mid - 0.5 * dur
                    new_end = desired_mid + 0.5 * dur

            # Limit shift if requested
            if cfg["max_shift_seconds"] is not None and orig_start is not None and new_start is not None:
                new_start, new_end = _limit_shift(orig_start, orig_end, new_start, new_end, cfg["max_shift_seconds"])
        else:
            # No textual/time match confidence:
            # Keep original if valid; interpolation will fix missing/invalid later
            new_start, new_end = orig_start, orig_end

        # Duration sanity
        if new_start is not None and new_end is not None:
            if new_end < new_start:
                new_end = new_start + cgf(cfg, "min_duration")
            dur = new_end - new_start
            if dur < cgf(cfg, "min_duration"):
                new_end = new_start + cgf(cfg, "min_duration")
            elif dur > cgf(cfg, "max_duration"):
                new_end = new_start + cgf(cfg, "max_duration")

        aligned.append({
            "start": new_start,
            "end": new_end,
            "text": cue["text"],
            "source_index": s_idx,
            "matched_transcript_index": chosen_idx,
            "similarity": float(best_sim if chosen_idx is not None else 0.0),
            "_orig_start": orig_start,
            "_orig_end": orig_end,
        })

    # Interpolation and enforcement (make sure every cue has valid, monotonic times)
    aligned = _interpolate_and_enforce(aligned, cfg)

    # Text corrections: fill from transcript for empty text or if similarity is moderate/strong
    for item in aligned:
        mi = item.get("matched_transcript_index")
        if mi is None:
            continue
        t_seg = t_segments[mi]
        # Replace text if empty OR similarity shows clear match
        if not item.get("text") or item.get("similarity", 0.0) >= max(0.55, min_similarity_for_text_correction):
            ttxt = (t_seg.get("text") or "").strip()
            if ttxt:
                item["text"] = ttxt

    # Final smoothing: avoid overlaps, respect intercue gap and duration bounds
    aligned = _final_smooth(
        aligned,
        intercue_gap=intercue_gap,
        min_duration=cgf(cfg, "min_duration"),
        max_duration=cgf(cfg, "max_duration"),
    )

    # Prepare final output with visible corrections
    out = []
    for idx, it in enumerate(aligned):
        out.append({
            "index": it.get("source_index", idx),
            "start": float(it.get("start", 0.0)) if it.get("start") is not None else 0.0,
            "end": float(it.get("end", it.get("start", 0.0) or 0.0)) if it.get("end") is not None else float(it.get("start", 0.0) or 0.0),
            "text": (it.get("text") or "").strip(),
            "format": "generic",
        })
    return out


# ----------------------- Internal helpers -----------------------

def _default_config() -> Dict:
    return {
        "max_shift_seconds": None,
        "similarity_threshold": 0.35,
        "time_weight": 0.35,
        "text_weight": 0.65,
        "search_window_seconds": 6.0,
        "min_duration": 0.8,
        "max_duration": 8.0,
        "avg_duration_hint": None,
        "punctuation_sensitive": False,
    }

def _mid_from_times(start: Optional[float], end: Optional[float]) -> Optional[float]:
    if start is not None and end is not None:
        return 0.5 * (start + end)
    if start is not None:
        return start
    if end is not None:
        return end
    return None

_WORD_RE = re.compile(r"[A-Za-z0-9']+")

def _strip_punctuation(s: str) -> str:
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
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    n, m = len(a), len(b)
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

def _hybrid_text_similarity(cue: Dict, seg: Dict) -> float:
    j = _jaccard(cue["tokens"], seg["tokens"])
    c = _cosine_like(cue["tf"], seg["tf"])
    l = _lcs_ratio(cue["text"].lower(), seg["text"].lower())
    return 0.4 * c + 0.35 * l + 0.25 * j

def _time_proximity_score(cue_time: Optional[float], seg_time: float, window: float) -> float:
    if cue_time is None:
        return 0.5
    d = abs(cue_time - seg_time)
    if d >= window:
        return 0.0
    return 0.5 * (1 + math.cos(math.pi * d / window))

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

def _find_candidates_by_time(t_sorted, t_times, center_time: Optional[float], window: float) -> List[int]:
    if center_time is None:
        return [idx for idx, _ in t_sorted]
    left = _lower_bound(t_times, center_time - window)
    right = _upper_bound(t_times, center_time + window)
    return [t_sorted[i][0] for i in range(left, right)]

def _find_best_match(
    cue: Dict,
    t_segments: List[Dict],
    t_sorted: List[Tuple[int, Dict]],
    t_times: List[float],
    time_weight: float,
    text_weight: float,
    window: float
) -> Tuple[Optional[int], float, float]:
    cue_mid = _mid_from_times(cue.get("start"), cue.get("end"))
    candidates = _find_candidates_by_time(t_sorted, t_times, cue_mid, window)
    if not candidates:
        candidates = [idx for idx, _ in t_sorted]
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
    duration = max(0.0, new_end - new_start)
    clamped_start = orig_start + (max_shift if shift > 0 else -max_shift)
    return clamped_start, clamped_start + duration

def _estimate_duration_for_text(
    text: str,
    *,
    min_duration: float,
    max_duration: float,
    max_cps: float = 25.0,
) -> float:
    txt = (text or "").replace("\n", " ").strip()
    n_chars = len(txt)
    if n_chars <= 0:
        return min_duration
    est = max(n_chars / max_cps, min_duration)
    return min(est, max_duration)

def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

def cgf(cfg: Dict, key: str) -> float:
    return float(cfg[key])

def _interpolate_and_enforce(aligned: List[Dict], cfg: Dict) -> List[Dict]:
    n = len(aligned)
    durations = [max(0.0, (x["end"] - x["start"])) for x in aligned if x.get("start") is not None and x.get("end") is not None]
    avg_dur = cfg["avg_duration_hint"] if cfg["avg_duration_hint"] else (sum(durations) / len(durations) if durations else 2.0)
    min_d, max_d = cgf(cfg, "min_duration"), cgf(cfg, "max_duration")

    last_end = None
    for i in range(n):
        s = aligned[i]
        if s.get("start") is None or s.get("end") is None or s["end"] < s["start"]:
            if last_end is None:
                s["start"] = 0.0 if s.get("start") is None else s["start"]
                s["end"] = (s["start"] + (avg_d or min_d)) if s.get("end") is None else s["end"]
            else:
                s["start"] = last_end
                s["end"] = s["start"] + (avg_d or min_d)
        dur = s["end"] - s["start"]
        if dur < min_d:
            s["end"] = s["start"] + min_d
        elif dur > max_d:
            s["end"] = s["start"] + max_d
        last_end = s["end"]

    for i in range(1, n):
        prev = aligned[i - 1]
        cur = aligned[i]
        if cur["start"] < prev["end"]:
            cur["start"] = prev["end"]
            cur_dur = cur["end"] - cur["start"]
            if cur_dur < min_d:
                cur["end"] = cur["start"] + min_d
            elif cur_dur > max_d:
                cur["end"] = cur["start"] + max_d

    for i in reversed(range(n - 1)):
        cur = aligned[i]
        nxt = aligned[i + 1]
        gap = nxt["start"] - cur["end"]
        if gap > max(0.2, 0.25 * avg_dur):
            new_end = min(cur["start"] + max_d, cur["end"] + 0.25 * gap)
            if new_end > cur["end"]:
                cur["end"] = new_end

    return aligned

def _final_smooth(
    cues: List[Dict],
    *,
    intercue_gap: float,
    min_duration: float,
    max_duration: float,
) -> List[Dict]:
    if not cues:
        return cues
    out = []
    last_end = None
    for cue in cues:
        if cue.get("start") is None or cue.get("end") is None:
            continue
        start = float(cue["start"])
        end = float(cue["end"])
        if last_end is not None and start < last_end + intercue_gap:
            shift = (last_end + intercue_gap) - start
            start += shift
            end += shift
        dur = end - start
        if dur < min_duration:
            end = start + min_duration
        elif dur > max_duration:
            end = start + max_duration
        new_cue = dict(cue)
        new_cue["start"] = start
        new_cue["end"] = end
        out.append(new_cue)
        last_end = end
    return out

# Demo entry point
def main():
    """
    Run a small demonstration with sample transcript and subtitle data.
    Prints aligned subtitle cues with visible corrections.
    """
    transcript = [
        {"start": 0.00, "end": 2.10, "text": "Hello there"},
        {"start": 2.10, "end": 4.20, "text": "How are you doing"},
        {"start": 4.20, "end": 6.40, "text": "I am fine thank you"},
        {"start": 6.40, "end": 8.50, "text": "Let's get started"},
    ]

    subtitles = [
        {"start": 0.35, "end": 2.10, "text": "Hello there..."},
        {"start": None, "end": None, "text": "How are you doing?"},
        {"start": 4.80, "end": 5.20, "text": "I'm fine, thank you."},
        {"start": None, "end": None, "text": ""},
    ]

    config = {
        "max_shift_seconds": 2.0,
        "similarity_threshold": 0.35,
        "time_weight": 0.35,
        "text_weight": 0.65,
        "search_window_seconds": 6.0,
        "min_duration": 1.0,
        "max_duration": 6.0,
        "avg_duration_hint": 2.0,
        "punctuation_sensitive": False,
    }

    print("Original Subtitles:")
    for i, s in enumerate(subtitles, 1):
        os = s.get("start")
        oe = s.get("end")
        print(f"{i:02d} | {os if os is not None else 'None'} --> {oe if oe is not None else 'None'} | text={s.get('text','')}")

    aligned = align_subtitles_to_transcript(transcript, subtitles, config)

    print("\nAligned Subtitles:")
    for i, a in enumerate(aligned, 1):
        print(f"{i:02d} | {a['start']:.2f} --> {a['end']:.2f} | text={a['text']}")

if __name__ == "__main__":
    main()
