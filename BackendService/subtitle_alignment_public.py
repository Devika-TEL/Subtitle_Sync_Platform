# -*- coding: utf-8 -*-
"""
Subtitle alignment utilities.

This module exposes a single public function `align_subtitles_to_transcript`
which aligns a list of subtitle cues (start, end, text) to a transcript (start, end, text)
using a hybrid strategy:
- Primary alignment by time proximity
- Secondary validation and correction using text similarity
- Interpolation and smoothing for unmatched or low-confidence cues
- Best-practice constraints for subtitle quality (min/max duration, no overlaps, reading speed checks)

The function returns a new list of corrected cue dictionaries and does not perform any I/O.
"""

from typing import Any, Dict, List, Optional, Tuple, Iterable
import math
import re


# PUBLIC_INTERFACE
def align_subtitles_to_transcript(
    transcript: Iterable[Dict[str, Any]],
    cues: Iterable[Dict[str, Any]],
    *,
    # Tuning parameters (safe defaults)
    max_time_gap: float = 1.5,
    # similarity thresholds
    min_similarity_for_text_correction: float = 0.55,
    min_similarity_for_time_trust: float = 0.35,
    # timing constraints
    min_duration: float = 0.9,
    max_duration: float = 7.0,
    # reading speed and length constraints
    max_cps: float = 25.0,  # characters per second
    max_lines: int = 2,
    max_chars_per_line: int = 42,
    # overlap and padding
    intercue_gap: float = 0.06,  # 60ms gap between cues to avoid overlaps
) -> List[Dict[str, Any]]:
    """
    PUBLIC_INTERFACE
    Align subtitle cues to transcript segments using time and text similarity.

    Parameters:
        transcript: iterable of segments. Each segment is a dict with:
            - start (float, seconds), end (float, seconds), text (str)
            Additional fields are preserved and passed through when helpful.
        cues: iterable of cues. Each cue is a dict with:
            - start (float), end (float), text (str or list of lines under key 'lines'/'text')
            Additional fields are preserved and passed through when helpful.

    Keyword-only parameters:
        max_time_gap: Maximum allowed time deviation (seconds) to consider two items near in time.
        min_similarity_for_text_correction: Jaccard-like token similarity threshold to override timings.
        min_similarity_for_time_trust: Similarity threshold under which we avoid aggressive text-based shifts.
        min_duration: Minimum duration (s) for a cue after correction.
        max_duration: Maximum duration (s) for a cue after correction.
        max_cps: Maximum characters per second for readability.
        max_lines: Maximum lines allowed in a cue (we will split/merge lines conservatively).
        max_chars_per_line: Maximum characters per line target (soft-wrap).
        intercue_gap: Minimum gap between consecutive cues to avoid overlaps.

    Returns:
        A list of dictionaries for corrected cues. Each dict will contain at minimum:
            - start (float), end (float), text (str)
        If the input cue contained format-specific fields (e.g., 'lines', 'style', 'position'),
        we try to preserve them where consistent with the corrected text/timing.

    Notes:
        - This function is format-agnostic and performs no file serialization.
        - Timing is clamped to ensure non-overlapping and quality constraints.
        - Text similarity is token-based and robust to punctuation/case differences.
    """
    tr_segs = _normalize_transcript(transcript)
    cues_list = _normalize_cues(cues)

    if not tr_segs or not cues_list:
        # Nothing to align; return normalized cues
        return cues_list

    # Build quick access arrays
    tr_times = [(s["start"], s["end"]) for s in tr_segs]
    tr_texts = [s["text"] for s in tr_segs]

    # Precompute token sets for transcript segs
    tr_token_sets = [_token_set(t) for t in tr_texts]

    corrected: List[Dict[str, Any]] = []
    last_end = None

    for idx, cue in enumerate(cues_list):
        cue_text = cue.get("text", "").strip()
        cue_tokens = _token_set(cue_text)

        # Find best transcript segment by time proximity
        best_time_idx, time_score = _best_time_match_index(cue, tr_times, max_time_gap=max_time_gap)

        # Find best transcript segment by text similarity
        best_text_idx, text_score = _best_text_match_index(cue_tokens, tr_token_sets)

        # Decision: choose a segment index
        chosen_idx = _decide_alignment_index(
            best_time_idx=best_time_idx,
            time_score=time_score,
            best_text_idx=best_text_idx,
            text_score=text_score,
            min_similarity_for_text_correction=min_similarity_for_text_correction,
            min_similarity_for_time_trust=min_similarity_for_time_trust,
        )

        # Derive target timing
        if chosen_idx is not None:
            t_start, t_end = tr_times[chosen_idx]
            aligned_start, aligned_end = _fit_cue_to_window(
                cue_text,
                (t_start, t_end),
                min_duration=min_duration,
                max_duration=max_duration,
                max_cps=max_cps,
            )
        else:
            # No good match; interpolate using neighbors and clamp
            aligned_start, aligned_end = _interpolate_cue_timing(
                idx,
                cues_list,
                tr_times,
                min_duration=min_duration,
                max_duration=max_duration,
            )

        # Ensure non-overlap with previous
        if last_end is not None and aligned_start < last_end + intercue_gap:
            shift = (last_end + intercue_gap) - aligned_start
            aligned_start += shift
            aligned_end += shift

        # Clamp within transcript global window
        global_start = tr_times[0][0]
        global_end = tr_times[-1][1]
        aligned_start = max(aligned_start, global_start)
        aligned_end = min(max(aligned_end, aligned_start + min_duration), global_end)

        # Update last_end
        last_end = aligned_end

        # Possibly replace cue text with transcript text if we have a strong match and text diverges
        final_text = cue_text
        if chosen_idx is not None:
            transcript_text = tr_texts[chosen_idx].strip()
            # If text similarity clearly indicates transcript is the correct content and cue is poor, replace
            if text_score >= max(min_similarity_for_text_correction, 0.7):
                final_text = _harmonize_text_to_constraints(
                    transcript_text,
                    max_lines=max_lines,
                    max_chars_per_line=max_chars_per_line,
                )
            else:
                # Still enforce wrapping on the existing cue text
                final_text = _harmonize_text_to_constraints(
                    final_text,
                    max_lines=max_lines,
                    max_chars_per_line=max_chars_per_line,
                )
        else:
            # No match; at least wrap the current cue text
            final_text = _harmonize_text_to_constraints(
                final_text,
                max_lines=max_lines,
                max_chars_per_line=max_chars_per_line,
            )

        # Preserve format-specific fields if present, updating text appropriately.
        new_cue = _preserve_and_update_fields(cue, aligned_start, aligned_end, final_text)
        corrected.append(new_cue)

    # Final pass: ensure no overlaps and spacing, mild smoothing
    corrected = _post_smooth(corrected, intercue_gap=intercue_gap, min_duration=min_duration, max_duration=max_duration)

    # Conform output: only include allowed keys per requirements
    allowed_keys = {"index", "start", "end", "text", "format"}
    filtered: List[Dict[str, Any]] = []
    for i, item in enumerate(corrected):
        # derive format if present in original cue or default to 'srt' agnostic placeholder
        fmt = item.get("format")
        # Ensure index exists
        out = {
            "index": item.get("index", i),
            "start": float(item.get("start", 0.0)),
            "end": float(item.get("end", max(float(item.get("start", 0.0)), 0.0))),
            "text": item.get("text", "") if isinstance(item.get("text", ""), str) else str(item.get("text", "")),
            "format": fmt if isinstance(fmt, str) else None,
        }
        # Remove None format if not provided to strictly keep keys but allow None? Keep key with default 'generic'
        if out["format"] is None:
            out["format"] = "generic"
        # Append filtered dict
        filtered.append({k: out[k] for k in ["index", "start", "end", "text", "format"]})

    return filtered


# -------------------------- Internal helpers -------------------------- #

def _normalize_transcript(transcript: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Ensure transcript segments are sorted, valid, and normalized."""
    segs = []
    for seg in transcript:
        if seg is None:
            continue
        start = float(seg.get("start", 0.0))
        end = float(seg.get("end", start))
        text = _extract_text(seg)
        if end < start:
            start, end = end, start  # swap if out of order
        if not text:
            text = ""
        segs.append({**seg, "start": start, "end": end, "text": text})
    segs.sort(key=lambda s: (s["start"], s["end"]))
    return segs


def _normalize_cues(cues: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Ensure cues are sorted, valid, and normalized to have 'text'."""
    out = []
    for c in cues:
        if c is None:
            continue
        start = float(c.get("start", 0.0))
        end = float(c.get("end", start))
        text = _extract_text(c)
        if end < start:
            start, end = end, start
        out.append({**c, "start": start, "end": end, "text": text})
    out.sort(key=lambda x: (x["start"], x["end"]))
    return out


def _extract_text(item: Dict[str, Any]) -> str:
    """Extract text from possible fields 'text' or 'lines'."""
    if "text" in item and isinstance(item["text"], str):
        return item["text"]
    if "lines" in item and isinstance(item["lines"], (list, tuple)):
        # Join conservatively with newline
        return "\n".join([str(x) for x in item["lines"] if x is not None])
    # Sometimes items store 'content'
    if "content" in item and isinstance(item["content"], str):
        return item["content"]
    return ""


def _token_set(text: str) -> set:
    """Return a set of normalized tokens for rough text similarity."""
    if not text:
        return set()
    # Lowercase, remove punctuation except apostrophes and hyphens inside words
    cleaned = re.sub(r"[^\w\s'-]", " ", text.lower())
    tokens = [t for t in cleaned.split() if t]
    return set(tokens)


def _jaccard_like(a: set, b: set) -> float:
    """Compute Jaccard-like similarity between two token sets."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _best_text_match_index(cue_tokens: set, tr_token_sets: List[set]) -> Tuple[Optional[int], float]:
    """Find the transcript index with highest token similarity."""
    best_idx = None
    best_score = -1.0
    for i, tset in enumerate(tr_token_sets):
        sc = _jaccard_like(cue_tokens, tset)
        if sc > best_score:
            best_score = sc
            best_idx = i
    return best_idx, (best_score if best_score >= 0 else 0.0)


def _best_time_match_index(
    cue: Dict[str, Any],
    tr_times: List[Tuple[float, float]],
    *,
    max_time_gap: float,
) -> Tuple[Optional[int], float]:
    """Find transcript index closest in time to the cue window."""
    cs, ce = cue["start"], cue["end"]
    c_mid = 0.5 * (cs + ce)
    best_idx = None
    best_dist = float("inf")
    for i, (ts, te) in enumerate(tr_times):
        t_mid = 0.5 * (ts + te)
        dist = abs(t_mid - c_mid)
        if dist < best_dist:
            best_dist = dist
            best_idx = i
    if best_idx is None:
        return None, 0.0
    # map distance to a score 1.0 at 0 dist, 0.0 at max_time_gap (clamped)
    score = max(0.0, 1.0 - min(best_dist, max_time_gap) / max_time_gap)
    return best_idx, score


def _decide_alignment_index(
    *,
    best_time_idx: Optional[int],
    time_score: float,
    best_text_idx: Optional[int],
    text_score: float,
    min_similarity_for_text_correction: float,
    min_similarity_for_time_trust: float,
) -> Optional[int]:
    """
    Decide which transcript index to trust based on scores.

    Heuristics:
    - If text similarity is strong (>= min_similarity_for_text_correction), prefer text match.
    - Otherwise, if time match is reasonable or text is weak (< min_similarity_for_time_trust), prefer time match.
    - If both are weak, return None (we will interpolate).
    """
    if best_text_idx is not None and text_score >= min_similarity_for_text_correction:
        return best_text_idx
    # Trust time if we don't have strong text
    if best_time_idx is not None and (text_score < min_similarity_for_time_trust or time_score >= 0.5):
        return best_time_idx
    # If both available, pick the one with the higher normalized confidence
    if best_text_idx is not None and best_time_idx is not None:
        # simple tie-break by combining scores
        if (0.6 * text_score) >= (0.6 * time_score):
            return best_text_idx
        return best_time_idx
    return best_time_idx if best_time_idx is not None else best_text_idx


def _estimate_duration_for_text(
    text: str,
    *,
    min_duration: float,
    max_duration: float,
    max_cps: float,
) -> float:
    """Estimate optimal duration for text given cps and constraints."""
    n_chars = len(_flatten_text(text))
    if n_chars <= 0:
        return min_duration
    est = max(n_chars / max_cps, min_duration)
    return min(est, max_duration)


def _fit_cue_to_window(
    text: str,
    target_window: Tuple[float, float],
    *,
    min_duration: float,
    max_duration: float,
    max_cps: float,
) -> Tuple[float, float]:
    """
    Fit cue to a transcript time window, clamped by reading speed and min/max duration.
    If transcript window is too small, expand slightly within reasonable bounds.
    """
    ts, te = target_window
    tw = max(te - ts, 0.0)
    desired = _estimate_duration_for_text(text, min_duration=min_duration, max_duration=max_duration, max_cps=max_cps)

    if tw <= 0.0:
        # Degenerate window; create a tiny window centered on ts
        start = ts
        end = ts + desired
        return start, end

    if desired <= tw:
        # Center desired duration within window
        start = ts + 0.5 * (tw - desired)
        end = start + desired
        return start, end

    # Desired longer than window; expand around window edges if possible
    overflow = desired - tw
    expand_before = 0.5 * overflow
    expand_after = overflow - expand_before
    start = ts - expand_before
    end = te + expand_after
    # Ensure ordering
    if end <= start:
        end = start + max(min_duration, 0.5)
    return start, end


def _interpolate_cue_timing(
    idx: int,
    cues_list: List[Dict[str, Any]],
    tr_times: List[Tuple[float, float]],
    *,
    min_duration: float,
    max_duration: float,
) -> Tuple[float, float]:
    """
    When no reliable match is found, interpolate timing using neighboring cues and global transcript bounds.
    """
    global_start = tr_times[0][0]
    global_end = tr_times[-1][1]

    prev_end = cues_list[idx - 1]["end"] if idx > 0 else global_start
    next_start = cues_list[idx + 1]["start"] if idx + 1 < len(cues_list) else global_end

    # Place cue in the middle of available space with sensible duration
    available = max(next_start - prev_end, min_duration)
    duration = min(max(available * 0.6, min_duration), min(max_duration, available))
    start = prev_end + 0.2 * available
    end = start + duration

    # Clamp to global
    start = max(start, global_start)
    end = min(end, global_end)
    if end <= start:
        end = start + min_duration
    return start, end


def _flatten_text(text: str) -> str:
    """Flatten text for CPS calculation."""
    return text.replace("\n", " ").strip()


def _wrap_text_lines(text: str, max_chars_per_line: int) -> List[str]:
    """
    Simple greedy word-wrap to target line length. Keeps existing line breaks as hard hints.
    """
    if not text:
        return [""]
    hard_lines = [ln.strip() for ln in text.split("\n")]
    wrapped: List[str] = []
    for ln in hard_lines:
        words = ln.split()
        if not words:
            wrapped.append("")
            continue
        cur = words[0]
        for w in words[1:]:
            if len(cur) + 1 + len(w) <= max_chars_per_line:
                cur += " " + w
            else:
                wrapped.append(cur)
                cur = w
        wrapped.append(cur)
    return wrapped


def _harmonize_text_to_constraints(
    text: str,
    *,
    max_lines: int,
    max_chars_per_line: int,
) -> str:
    """
    Enforce basic readability constraints: wrap and cap lines.
    """
    wrapped = _wrap_text_lines(_flatten_text(text), max_chars_per_line=max_chars_per_line)
    if len(wrapped) > max_lines:
        # Merge to fit lines by rewrapping with slightly larger target to avoid harsh truncation
        target = max_chars_per_line
        merged_text = " ".join(wrapped)
        wrapped = _wrap_text_lines(merged_text, max_chars_per_line=target)
        wrapped = wrapped[:max_lines]
    return "\n".join(wrapped)


def _preserve_and_update_fields(
    cue: Dict[str, Any],
    new_start: float,
    new_end: float,
    new_text: str,
) -> Dict[str, Any]:
    """
    Return a new cue dict preserving format-specific fields when possible.
    Priority: if original had 'lines', regenerate lines from new_text;
              else keep 'text' updated.
    """
    new_cue = dict(cue)  # shallow copy; preserve other metadata like style/position
    new_cue["start"] = float(new_start)
    new_cue["end"] = float(new_end)
    if "lines" in new_cue and isinstance(new_cue["lines"], (list, tuple)):
        new_cue["lines"] = new_text.split("\n")
        new_cue["text"] = new_text  # maintain both for compatibility
    else:
        new_cue["text"] = new_text
        # Clear lines if present but invalid
        if isinstance(new_cue.get("lines"), (list, tuple)) and not new_cue["lines"]:
            new_cue.pop("lines", None)
    return new_cue


def _post_smooth(
    cues: List[Dict[str, Any]],
    *,
    intercue_gap: float,
    min_duration: float,
    max_duration: float,
) -> List[Dict[str, Any]]:
    """
    Final pass to ensure:
    - No overlaps (respecting intercue_gap)
    - Duration constraints
    - Monotonic timing
    """
    if not cues:
        return cues
    out = []
    last_end = None
    for cue in cues:
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
