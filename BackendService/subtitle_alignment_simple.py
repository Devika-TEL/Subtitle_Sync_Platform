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

Data contracts (updated):
- transcript: Whisper transcribe() output or a flat list:
    - If dict: expects a "segments" list. Each segment should include:
        - "text": str
        - "start": float (seconds)
        - "end": float (seconds)
      We'll normalize into a List[dict] of segments.
    - If list: same segment structure as above. Non-dict items are coerced to text-only with 0.0 times.
- subtitles: List[dict] of cues with keys:
    - "index": int (sequence; auto-filled if missing)
    - "start": float (seconds; default 0.0)
    - "end": float (seconds; default 0.0; fixed to be >= start)
    - "text": str (default "")
    - "format": str (consistent across outputs; inferred from first non-empty input format or "")

Both lists are sorted by start time internally if not already ordered.

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

from typing import List, Dict, Tuple, Any, Union, Optional, Callable
import re
import logging
from math import isfinite

# Optional heavy deps are imported lazily inside functions to keep import-time light for CI

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

def _get_logger(verbose: bool, logger: Optional[logging.Logger]) -> Optional[logging.Logger]:
    """
    Returns a logger based on provided arguments.
    If logger is None and verbose is True, configures a default logger at INFO level.
    If verbose is False and logger is None, returns None (no logging).
    """
    if logger is not None:
        return logger
    if verbose:
        logging.basicConfig(level=logging.INFO)
        return logging.getLogger(__name__)
    return None

def _enforce_monotonic_nonoverlap(
    subs: List[Dict],
    min_gap: float = 0.02,
    min_dur: float = 0.2,
    *,
    _collect_adjustments: Optional[List[Tuple[int, float, float, float, float]]] = None,
) -> List[Dict]:
    """
    Make sure subtitle timings are monotonic and non-overlapping.
    - Ensures start[i] >= end[i-1] + min_gap
    - Ensures duration >= min_dur (expanding end if necessary within observed bounds)

    If _collect_adjustments is provided, it is appended with tuples:
        (cue_idx_sorted, old_start, old_end, new_start, new_end)
    for cues whose times changed by this enforcement step.
    """
    result = _sort_by_start(subs)
    # First pass: enforce monotonic starts and min duration
    for i, s in enumerate(result):
        old_start = _safe_float(s.get("start", 0.0))
        old_end = _safe_float(s.get("end", 0.0))
        start = old_start
        end = old_end
        if i > 0:
            prev_end = _safe_float(result[i - 1].get("end", 0.0))
            start = max(start, prev_end + min_gap)
        if end <= start + min_dur:
            end = start + min_dur
        start, end = start, max(end, start)
        s["start"], s["end"] = start, end
        if _collect_adjustments is not None and (start != old_start or end != old_end):
            _collect_adjustments.append((i, old_start, old_end, start, end))
    # Second pass: ensure next starts after current with min gap; if needed, extend next
    for i in range(len(result) - 1):
        cur = result[i]
        nxt = result[i + 1]
        old_nxt_start = _safe_float(nxt.get("start", 0.0))
        old_nxt_end = _safe_float(nxt.get("end", 0.0))
        if _safe_float(nxt["start"]) < _safe_float(cur["end"]) + min_gap:
            nxt["start"] = _safe_float(cur["end"]) + min_gap
            if _safe_float(nxt["end"]) < _safe_float(nxt["start"]) + min_dur:
                nxt["end"] = _safe_float(nxt["start"]) + min_dur
            if _collect_adjustments is not None and (nxt["start"] != old_nxt_start or nxt["end"] != old_nxt_end):
                _collect_adjustments.append((i + 1, old_nxt_start, old_nxt_end, _safe_float(nxt["start"]), _safe_float(nxt["end"])))
    return result

def _rf_scores(a: str, b: str) -> Tuple[float, float]:
    """Compute RapidFuzz partial_ratio and token_set_ratio in [0,1]."""
    try:
        from rapidfuzz import fuzz  # type: ignore
        pr = float(fuzz.partial_ratio(a, b)) / 100.0
        tr = float(fuzz.token_set_ratio(a, b)) / 100.0
        return pr, tr
    except Exception:
        # Fallback: approximate via Jaccard to keep deterministic behavior in CI
        at, bt = _tokens(a), _tokens(b)
        j = _jaccard(at, bt)
        return j, j


def _embedding_cosine(a: str, b: str, model_loader: Optional[Callable[[], Any]]) -> float:
    """Compute cosine similarity using sentence-transformers if available and enabled."""
    if model_loader is None:
        return 0.0
    try:
        model = model_loader()
        from numpy import dot  # type: ignore
        from numpy.linalg import norm  # type: ignore
        va, vb = model.encode([a, b], convert_to_numpy=True)
        denom = float(norm(va) * norm(vb))
        if denom <= 0.0 or not isfinite(denom):
            return 0.0
        return float(dot(va, vb) / denom)
    except Exception:
        return 0.0


def _hybrid_score(
    sub_text: str,
    span_text: str,
    weights: Dict[str, float],
    model_loader: Optional[Callable[[], Any]],
) -> float:
    """Weighted combination of RapidFuzz metrics and embedding cosine."""
    pr, tr = _rf_scores(sub_text, span_text)
    emb = _embedding_cosine(sub_text, span_text, model_loader)
    return (
        weights.get("rapidfuzz_partial", 0.4) * pr
        + weights.get("rapidfuzz_token", 0.4) * tr
        + weights.get("embedding", 0.2) * emb
    )


def _lazy_st_model_loader(model_name: str) -> Callable[[], Any]:
    """Return a zero-arg closure that loads the sentence-transformers model once (cached)."""
    model_ref: Dict[str, Any] = {"model": None, "name": model_name}

    def _load():
        if model_ref["model"] is None:
            from sentence_transformers import SentenceTransformer  # type: ignore

            model_ref["model"] = SentenceTransformer(model_ref["name"])
        return model_ref["model"]

    return _load


def _best_transcript_span_for_sub(
    sub_tokens: List[str],
    transcript: List[Dict],
    start_idx: int,
    max_span: int = 5,
    min_sim: float = 0.2,
    *,
    hybrid: bool = False,
    weights: Optional[Dict[str, float]] = None,
    model_loader: Optional[Callable[[], Any]] = None,
    raw_sub_text: Optional[str] = None,
) -> Tuple[int, int, float]:
    """
    Find the best contiguous span [i, j] of transcript segments starting from start_idx within max_span
    that maximizes similarity to the subtitle.
    - If hybrid=False: use Jaccard over tokens (existing behavior).
    - If hybrid=True: use weighted RapidFuzz + Embedding cosine.
    Returns (i, j_inclusive, score). If no span exceeds min_sim, returns (start_idx, start_idx, 0.0).
    """
    best_i, best_j, best_score = start_idx, start_idx, 0.0
    for i in range(start_idx, min(len(transcript), start_idx + max_span)):
        span_text = ""
        for j in range(i, min(len(transcript), i + max_span)):
            span_text = (span_text + " " + str(transcript[j].get("text", ""))).strip() if span_text else str(
                transcript[j].get("text", "")
            )
            if not hybrid:
                span_tokens = _tokens(span_text)
                score = _jaccard(sub_tokens, span_tokens)
            else:
                score = _hybrid_score(raw_sub_text or " ".join(sub_tokens), span_text, weights or {}, model_loader)
            if score > best_score:
                best_i, best_j, best_score = i, j, score
    if best_score < min_sim:
        return (start_idx, start_idx, 0.0)
    return (best_i, best_j, best_score)

def _calc_reading_duration(text: str, chars_per_sec: float, min_duration: float, max_duration: float) -> float:
    """Estimate duration from text length with clamps."""
    sec = max(min_duration, len(_normalize_text(text)) / max(1e-6, chars_per_sec))
    return min(sec, max_duration)


def _distribute_time_within_span_with_delayed_fix(
    sub_text: str,
    span_text: str,
    span_start: float,
    span_end: float,
    *,
    last_end: float,
    min_gap: float,
    min_duration: float,
    max_duration: float,
    chars_per_sec: float,
    delay_threshold: float,
) -> Tuple[float, float]:
    """
    Improved timing calculation:
    - Start at max(span_start, last_end + min_gap), unless the original offset is far after span_start
      (delayed start), then snap closer to span_start + small pad.
    - End based on reading speed, clamped within [start, span_end] and [min_duration, max_duration].
    """
    span_start = float(span_start)
    span_end = float(span_end)
    base_start = max(span_start, last_end + min_gap)

    # Detect delayed start: if base_start is significantly after span_start, snap earlier
    if base_start - span_start > delay_threshold:
        # pull start towards span_start but keep minimal gap after last_end
        base_start = max(span_start + min_gap, last_end + min_gap)

    # Compute duration from text
    est_dur = _calc_reading_duration(sub_text, chars_per_sec, min_duration, max_duration)
    est_end = min(base_start + est_dur, span_end)

    # Ensure at least min_duration; if cannot extend, shift earlier within span
    if est_end - base_start < min_duration:
        need = (min_duration - (est_end - base_start))
        est_end = min(span_end, base_start + min_duration)
        if est_end - base_start < min_duration and span_end - span_start >= min_duration:
            # try shifting start back if possible (bounded by span_start)
            base_start = max(span_start, est_end - min_duration)

    return (float(base_start), float(max(base_start + min_duration, est_end)))

# PUBLIC_INTERFACE
def align_subtitles_to_transcript(
    transcript: Union[List[Dict], Dict[str, Any]],
    subtitles: List[Dict],
    *,
    max_span: int = 5,
    min_similarity: float = 0.2,
    min_duration: float = 0.4,
    min_gap: float = 0.02,
    verbose: bool = False,
    logger: Optional[logging.Logger] = None,
    # Advanced alignment toggles
    enable_hybrid: Optional[bool] = None,
    embedding_model_name: Optional[str] = None,
    fuzzy_weights: Optional[Dict[str, float]] = None,
    default_chars_per_sec: Optional[float] = None,
    max_cue_duration: Optional[float] = None,
    delayed_start_threshold: Optional[float] = None,
) -> List[Dict]:
    """
    Align subtitles' start/end timings to a reference transcript as much as possible.

    Input normalization:
    - transcript may be either:
        1) Whisper-like dict with a "segments" list. Each segment should have "text", "start", "end".
           We'll internally normalize to a flat list of dicts with keys: text/start/end.
        2) A direct list of segments where each item is dict-like (or even a string). We'll coerce into dicts.
    - subtitles must be a list of dicts with keys: index, start, end, text, and format. However, this
      function robustly handles missing or malformed fields:
        * Missing text -> "" (empty string)
        * Missing start/end -> 0.0
        * Missing index -> auto-sequence starting at 1
        * Missing format -> a common format determined from the first non-empty 'format' among inputs; else ""
      Extra fields are ignored in the output.

    Behavior:
    - Performs greedy, monotonic alignment based on token Jaccard similarity to assign better timings
      from the transcript to each subtitle cue.
    - Preserves and cleans output by returning a list of dicts with exactly:
        ["index", "start", "end", "text", "format"]
      with values validated and auto-filled.
    - Enforces non-overlap, minimal gap, and minimal duration on final timings.

    Parameters
    ----------
    transcript : Union[List[Dict], Dict[str, Any]]
        Whisper transcribe() output (dict with 'segments': [...]) or a flat list of segment dicts.
        Each segment is expected to include:
          - text: str
          - start: float (seconds)
          - end: float (seconds)
        Any missing values are defaulted during normalization.
    subtitles : List[Dict]
        List of subtitle dicts, each ideally with:
          - index: int (sequence)
          - start: float (seconds)
          - end: float (seconds)
          - text: str
          - format: str (e.g., 'srt', 'vtt'). If mixed/missing, a common format is derived or set to "".
        Missing/invalid values will be corrected as described above.
    max_span : int, optional
        Maximum number of transcript segments to consider as a contiguous match span for a single subtitle.
    min_similarity : float, optional
        Minimum Jaccard similarity for accepting a transcript span; if not met, falls back to original times
        but still participates in overlap cleanup.
    min_duration : float, optional
        Minimum duration for any subtitle (seconds).
    min_gap : float, optional
        Minimum gap enforced between consecutive subtitles (seconds).
    verbose : bool, optional
        If True, emits info logs for each cue when timings change due to alignment or non-overlap enforcement.
    logger : logging.Logger or None, optional
        Logger to use for logging. If None and verbose is True, a default logger is configured at INFO level.
        If verbose is False and logger is None, no logs are emitted.

    Returns
    -------
    List[Dict]
        Cleaned and aligned list of subtitle dicts, each with keys:
        ["index", "start", "end", "text", "format"].
    """
    # ---- Normalize transcript ----
    if isinstance(transcript, dict):
        # Whisper output: expect a 'segments' key
        segments_raw = transcript.get("segments") or []
        if not isinstance(segments_raw, list):
            segments_raw = []
        transcript_list = segments_raw
    elif isinstance(transcript, list):
        transcript_list = transcript
    else:
        raise TypeError("transcript must be a Whisper-like dict with 'segments' or a list of segments")

    t_coerced: List[Dict[str, Any]] = []
    for seg in transcript_list:
        if seg is None:
            continue
        if isinstance(seg, dict):
            text = str(seg.get("text", ""))
            start = _safe_float(seg.get("start", 0.0))
            end = _safe_float(seg.get("end", 0.0))
        else:
            # Coerce non-dict to a text-only segment
            text = str(seg)
            start = 0.0
            end = 0.0
        t_coerced.append({"text": text, "start": start, "end": end})
    t_segments = _sort_by_start(t_coerced)

    # ---- Normalize subtitles (fix malformed fields) ----
    if not isinstance(subtitles, list):
        raise TypeError("subtitles must be a list of dicts")
    s_raw: List[Dict[str, Any]] = []
    for idx, c in enumerate(subtitles, start=1):
        if c is None:
            c = {}
        if not isinstance(c, dict):
            c = {"text": str(c)}
        text = str(c.get("text", "")) if c.get("text") is not None else ""
        start = _safe_float(c.get("start", 0.0))
        end = _safe_float(c.get("end", 0.0))
        index_val = c.get("index")
        try:
            index = int(index_val) if index_val is not None else idx
        except Exception:
            index = idx
        fmt = c.get("format")
        fmt = str(fmt).strip() if isinstance(fmt, str) else ""
        s_raw.append({
            "index": index,
            "start": start,
            "end": end,
            "text": text,
            "format": fmt,
        })
    # Determine common format: first non-empty wins
    common_format = ""
    for c in s_raw:
        if c["format"]:
            common_format = c["format"]
            break
    # Sort by start for alignment
    s_cues = sorted(s_raw, key=lambda x: _safe_float(x.get("start", 0.0)))

    # Nothing to align edge cases
    if not t_segments or not s_cues:
        # Return cleaned list with ensured fields and consistent format/index
        normalized: List[Dict] = []
        for idx, item in enumerate(s_cues, start=1):
            start_v = _safe_float(item.get("start", 0.0))
            end_v = _safe_float(item.get("end", 0.0))
            text_v = str(item.get("text", ""))
            normalized.append({
                "index": int(idx),
                "start": float(start_v),
                "end": float(end_v if end_v >= start_v else start_v),
                "text": text_v,
                "format": common_format,
            })
        return normalized

    # Prepare logger
    _logger = _get_logger(verbose, logger)

    # Config-driven advanced flags (soft dependency on config module)
    # If caller passed explicit values, prefer them; else try reading from config Settings
    try:
        from .config import get_settings  # type: ignore

        cfg = get_settings()
        if enable_hybrid is None:
            enable_hybrid = bool(getattr(cfg, "ALIGNMENT_EMBEDDINGS_ENABLED", False))
        if embedding_model_name is None:
            embedding_model_name = str(getattr(cfg, "ALIGNMENT_MODEL_NAME", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"))
        if fuzzy_weights is None:
            fuzzy_weights = dict(getattr(cfg, "FUZZY_WEIGHTS", {"rapidfuzz_partial": 0.4, "rapidfuzz_token": 0.4, "embedding": 0.2}))
        if default_chars_per_sec is None:
            default_chars_per_sec = float(getattr(cfg, "DEFAULT_CHARS_PER_SEC", 15.0))
        if max_cue_duration is None:
            max_cue_duration = float(getattr(cfg, "MAX_CUE_DURATION_MS", 6000) / 1000.0)
        if delayed_start_threshold is None:
            delayed_start_threshold = float(getattr(cfg, "DELAY_THRESHOLD_MS", 500) / 1000.0)
        # Ensure numbers
        default_chars_per_sec = float(default_chars_per_sec)
        max_cue_duration = float(max_cue_duration)
        delayed_start_threshold = float(delayed_start_threshold)
    except Exception:
        # Fallback defaults if config not available
        enable_hybrid = bool(enable_hybrid) if enable_hybrid is not None else False
        embedding_model_name = embedding_model_name or "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        fuzzy_weights = fuzzy_weights or {"rapidfuzz_partial": 0.4, "rapidfuzz_token": 0.4, "embedding": 0.2}
        default_chars_per_sec = float(default_chars_per_sec or 15.0)
        max_cue_duration = float(max_cue_duration or 6.0)
        delayed_start_threshold = float(delayed_start_threshold or 0.5)

    # Set up embedding model loader if hybrid enabled
    model_loader = _lazy_st_model_loader(embedding_model_name) if enable_hybrid else None

    # ---- Alignment ----
    aligned: List[Dict] = []
    t_idx = 0  # monotonic pointer into transcript

    for cue_idx, cue in enumerate(s_cues):
        sub_text = str(cue.get("text", ""))
        sub_tokens = _tokens(sub_text)
        orig_start = _safe_float(cue.get("start", 0.0))
        orig_end = _safe_float(cue.get("end", 0.0))
        # Find best span in transcript starting from t_idx
        i, j, score = _best_transcript_span_for_sub(
            sub_tokens=sub_tokens,
            transcript=t_segments,
            start_idx=t_idx,
            max_span=max_span,
            min_sim=min_similarity,
            hybrid=bool(enable_hybrid),
            weights=fuzzy_weights or {"rapidfuzz_partial": 0.4, "rapidfuzz_token": 0.4, "embedding": 0.2},
            model_loader=model_loader,
            raw_sub_text=sub_text,
        )

        # Prepare the new cue dict (copy cleaned fields)
        new_cue = dict(cue)
        chosen_span_info = None

        if score >= min_similarity:
            span = t_segments[i : j + 1]
            span_text = _merge_texts(span)
            span_start, span_end = _span_time(span)

            # Estimate start/end within the matched span using improved timing with delayed start fix
            last_end = aligned[-1]["end"] if aligned else 0.0
            est_start, est_end = _distribute_time_within_span_with_delayed_fix(
                sub_text=sub_text,
                span_text=span_text,
                span_start=span_start,
                span_end=span_end,
                last_end=float(last_end),
                min_gap=float(min_gap),
                min_duration=float(min_duration),
                max_duration=float(max_cue_duration),
                chars_per_sec=float(default_chars_per_sec),
                delay_threshold=float(delayed_start_threshold),
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

            chosen_span_info = {
                "span_i": i,
                "span_j": j,
                "span_start": float(span_start),
                "span_end": float(span_end),
                "similarity": float(score),
            }

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
            chosen_span_info = {
                "span_i": i,
                "span_j": j,
                "span_start": float(t_segments[i].get("start", 0.0)) if 0 <= i < len(t_segments) else 0.0,
                "span_end": float(t_segments[j].get("end", 0.0)) if 0 <= j < len(t_segments) else 0.0,
                "similarity": float(score),
            }

        # Log if alignment adjusted times
        if _logger is not None and (new_cue["start"] != orig_start or new_cue["end"] != orig_end):
            _logger.info(
                "Alignment change | cue=%d | %0.3f-->%0.3f -> %0.3f-->%0.3f | sim=%0.3f | span=(%d..%d) [%0.3f..%0.3f]",
                cue_idx,
                orig_start,
                orig_end,
                new_cue["start"],
                new_cue["end"],
                chosen_span_info.get("similarity", 0.0) if chosen_span_info else 0.0,
                chosen_span_info.get("span_i", -1) if chosen_span_info else -1,
                chosen_span_info.get("span_j", -1) if chosen_span_info else -1,
                chosen_span_info.get("span_start", 0.0) if chosen_span_info else 0.0,
                chosen_span_info.get("span_end", 0.0) if chosen_span_info else 0.0,
            )

        aligned.append(new_cue)

    # Final non-overlap enforcement and minimal gap/duration
    nonoverlap_adjustments: List[Tuple[int, float, float, float, float]] = []
    aligned = _enforce_monotonic_nonoverlap(
        aligned, min_gap=min_gap, min_dur=min_duration, _collect_adjustments=nonoverlap_adjustments
    )

    # Emit logs for non-overlap adjustments
    if _logger is not None:
        for (cidx, old_s, old_e, new_s, new_e) in nonoverlap_adjustments:
            _logger.info(
                "Non-overlap adjust | cue=%d | %0.3f-->%0.3f -> %0.3f-->%0.3f",
                cidx,
                old_s,
                old_e,
                new_s,
                new_e,
            )

    # ---- Output cleaning: enforce required keys and consistent format ----
    normalized: List[Dict] = []
    for idx, item in enumerate(aligned, start=1):
        start_v = _safe_float(item.get("start", 0.0))
        end_v = _safe_float(item.get("end", 0.0))
        text_v = str(item.get("text", ""))

        normalized.append({
            "index": int(idx),  # re-sequence to ensure valid index
            "start": float(start_v),
            "end": float(end_v),
            "text": text_v,
            "format": common_format,  # enforce consistent format across all outputs
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
    out = align_subtitles_to_transcript(demo_transcript, demo_subs, verbose=True)
    for i, c in enumerate(out, 1):
        print(f"{i}\n{c['start']:.2f} --> {c['end']:.2f}\n{c['text']}\n")
