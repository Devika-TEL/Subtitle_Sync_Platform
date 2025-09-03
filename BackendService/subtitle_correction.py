"""
Additional correction and compliance helpers.

This module provides:
- correct_subtitles: language-agnostic alignment of subtitle cues to a Whisper-like transcript
- apply_additional_compliance_fixes: post-processing copy hook (stub)

Design principles:
- No language-specific heuristics: tokenization is whitespace-based and normalization is Unicode-aware.
- Optional language mismatch handling: if transcript/subtitles languages clearly differ (via 'language' field or
  normalized script mismatch heuristic), return the original subtitles unchanged.
- OTT timing constraints enforcement: min/max cue duration, no overlaps, basic gap handling.
- Pure functions only; no file I/O except apply_additional_compliance_fixes which copies a file by design elsewhere.
"""

from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
import uuid
import math
import unicodedata
import difflib


# --------------------------
# General normalization utils
# --------------------------

def _normalize_text(text: str) -> str:
    """
    Unicode-aware normalization suitable for any language/scripts.
    - Normalize to NFKC
    - Collapse all whitespace to single spaces
    - Strip leading/trailing whitespace
    """
    if text is None:
        return ""
    t = unicodedata.normalize("NFKC", text)
    # Collapse all unicode whitespace
    t = " ".join(t.split())
    return t.strip()


def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


def _ms_to_srt_time(ms: int) -> str:
    """
    Convert milliseconds to SRT timestamp: HH:MM:SS,mmm
    """
    ms = max(0, ms)
    s, msec = divmod(ms, 1000)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return f"{h:02d}:{m:02d}:{s:02d},{msec:03d}"


def _s_to_ms(s: float) -> int:
    return int(round(s * 1000.0))


# --------------------------
# Language mismatch detection
# --------------------------

def _normalize_lang_code(value: Optional[str]) -> Optional[str]:
    """
    Normalize a language code if present: lowercase and 2-5 char token (e.g., 'en', 'pt-br').
    """
    if not value or not isinstance(value, str):
        return None
    v = value.strip().lower()
    if not v:
        return None
    return v


def _likely_same_language(transcript: Dict[str, Any], subtitles: List[Dict[str, Any]]) -> bool:
    """
    Determine if transcript and subtitles are likely the same language.

    Rules:
    - If both include a 'language' key (on transcript and at least the first subtitle), and they differ -> False.
    - Otherwise, do a simple script/character set heuristic:
        * Compare fraction of ASCII letters/digits vs non-ASCII; if wildly different, consider mismatch.
        * This is deliberately conservative to avoid false triggers; only return False on clear mismatch.
    - If unsure, return True (proceed with correction).
    """
    # Check explicit language keys
    t_lang = _normalize_lang_code(transcript.get("language")) if isinstance(transcript, dict) else None
    s_lang = None
    if subtitles and isinstance(subtitles[0], dict):
        s_lang = _normalize_lang_code(subtitles[0].get("language"))
    if t_lang and s_lang and t_lang != s_lang:
        return False

    # Heuristic on text/script
    def char_profile(text: str) -> Tuple[int, int]:
        ascii_cnt = 0
        non_ascii_cnt = 0
        for ch in text:
            # Count letters and numbers mostly
            if ch.isalpha() or ch.isdigit():
                if ord(ch) < 128:
                    ascii_cnt += 1
                else:
                    non_ascii_cnt += 1
        return ascii_cnt, non_ascii_cnt

    # Gather sample text
    t_text = []
    if isinstance(transcript, dict):
        for seg in transcript.get("segments", []):
            t_text.append(_normalize_text(str(seg.get("text", ""))))
    t_join = " ".join(t_text)[:2000]

    s_text = []
    for cue in subtitles[: min(len(subtitles), 10)]:
        s_text.append(_normalize_text(str(cue.get("text", ""))))
    s_join = " ".join(s_text)[:2000]

    if not t_join or not s_join:
        return True

    ta, tn = char_profile(t_join)
    sa, sn = char_profile(s_join)
    t_total = ta + tn
    s_total = sa + sn
    if t_total == 0 or s_total == 0:
        return True

    # Compare ratios of ASCII vs non-ASCII; if drastically different, assume mismatch
    t_ratio = ta / max(1, t_total)
    s_ratio = sa / max(1, s_total)
    # Threshold chosen conservatively
    if abs(t_ratio - s_ratio) > 0.6:
        return False
    return True


# --------------------------
# Transcript and cues shaping
# --------------------------

def _flatten_transcript_segments(transcript: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Flatten a Whisper-like transcript into a list of segments with start_ms, end_ms, text.
    Accepts timestamp in seconds (float) or ms in ints if provided.
    """
    out: List[Dict[str, Any]] = []
    if not isinstance(transcript, dict):
        return out
    for seg in transcript.get("segments", []):
        start = seg.get("start")
        end = seg.get("end")
        # Whisper uses seconds; ensure ms
        start_ms = _s_to_ms(_safe_float(start))
        end_ms = _s_to_ms(_safe_float(end))
        if end_ms < start_ms:
            end_ms = start_ms + 1
        text = _normalize_text(str(seg.get("text", "")))
        if text == "" and (end_ms - start_ms) <= 0:
            continue
        out.append({"start_ms": start_ms, "end_ms": end_ms, "text": text})
    return out


def _normalize_subtitle_cues(subtitles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Normalize input subtitle cues to a standard structure:
    - start_ms, end_ms, text
    Accept inputs that might use start/end in seconds or ms; try to detect.
    """
    cues: List[Dict[str, Any]] = []
    for cue in subtitles or []:
        if not isinstance(cue, dict):
            # Skip invalid entries
            continue
        # Accept keys: start, end (sec) or start_ms, end_ms (ms)
        if "start_ms" in cue and "end_ms" in cue:
            start_ms = int(cue["start_ms"])
            end_ms = int(cue["end_ms"])
        else:
            start_ms = _s_to_ms(_safe_float(cue.get("start")))
            end_ms = _s_to_ms(_safe_float(cue.get("end")))
        if end_ms < start_ms:
            end_ms = start_ms + 1
        text = _normalize_text(str(cue.get("text", "")))
        # carry forward language if exists for language check
        lang = _normalize_lang_code(cue.get("language"))
        norm = {"start_ms": start_ms, "end_ms": end_ms, "text": text}
        if lang:
            norm["language"] = lang
        cues.append(norm)
    return cues


# --------------------------
# Alignment logic
# --------------------------

# --------------------------
# Similarity and correction settings
# --------------------------

# Tunable thresholds for semantic preservation and fuzzy spelling detection
SEMANTIC_SIMILARITY_THRESHOLD = 0.86  # if >= keep subtitle core as-is (semantic match/near-identical)
FUZZY_SPELLING_THRESHOLD = 0.72       # if >= treat as likely typo and replace with transcript word
LOW_OVERLAP_SKIP_THRESHOLD = 0.18     # if window overlap less than this, skip aggressive correction

# Minimal synonym/lemma map (internal only; no external deps)
# Use lowercase keys/values. Include common paraphrases or lemma forms.
_SYNONYM_MAP = {
    "yeah": "yes",
    "ya": "yes",
    "yep": "yes",
    "nope": "no",
    "okay": "ok",
    "alright": "ok",
    "alrighty": "ok",
    "gonna": "going",
    "wanna": "want",
    "gotta": "got",
    "kinda": "kind",
    "sorta": "sort",
    "cannot": "can't",  # note: keep canonicalization simple
    "okey": "ok",
    "thanks": "thank",
    "thankyou": "thank",
    "tho": "though",
    "through": "thru",  # sometimes appears in transcript variants
}

def _tokenize(text: str) -> List[str]:
    """
    Simple language-agnostic tokenization: split on whitespace.
    """
    if not text:
        return []
    return [tok for tok in text.split() if tok]


def _normalize_core_for_compare(core: str) -> str:
    """
    Normalize a token core for comparison:
    - Unicode NFKC
    - Lowercase
    """
    return _normalize_text(core).lower()

def _sequence_similarity(a: str, b: str) -> float:
    """
    Normalized string similarity using difflib.SequenceMatcher ratio.
    """
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()

def _best_fuzzy_match(word: str, candidates: List[str]) -> Tuple[str, float]:
    """
    Find the best fuzzy match for 'word' among candidates, returning (best, score).
    Comparison is done on normalized (lowercased) forms but returns the original candidate.
    """
    best = ""
    best_score = 0.0
    w_norm = _normalize_core_for_compare(word)
    for cand in candidates:
        c_norm = _normalize_core_for_compare(cand)
        score = _sequence_similarity(w_norm, c_norm)
        if score > best_score:
            best_score = score
            best = cand
    return best, best_score

def _synonym_or_same(a: str, b: str) -> bool:
    """
    Returns True if a and b are the same under normalization or mapped via synonym map.
    """
    na = _normalize_core_for_compare(a)
    nb = _normalize_core_for_compare(b)
    if na == nb:
        return True
    # Check both directions in the map
    mapped_a = _SYNONYM_MAP.get(na, na)
    mapped_b = _SYNONYM_MAP.get(nb, nb)
    return mapped_a == mapped_b

def _token_overlap_ratio(a_tokens: List[str], b_tokens: List[str]) -> float:
    """
    Token overlap (Jaccard-like but on normalized token cores only).
    """
    if not a_tokens or not b_tokens:
        return 0.0
    a_norm = { _normalize_core_for_compare(x) for x in a_tokens if x }
    b_norm = { _normalize_core_for_compare(x) for x in b_tokens if x }
    if not a_norm or not b_norm:
        return 0.0
    inter = len(a_norm & b_norm)
    union = len(a_norm | b_norm)
    return inter / max(1, union)

def _split_token_core_punct(token: str) -> Tuple[str, str, str]:
    """
    Split a token into (leading_punct, core, trailing_punct) where core is alnum/letter chunk.
    Example:
      '"Hello,' -> ('"', 'Hello', ',')
      'world!'  -> ('', 'world', '!')
      '...'     -> ('...', '', '')
    """
    if not token:
        return "", "", ""
    # Identify leading punctuation
    i = 0
    while i < len(token) and not token[i].isalnum():
        i += 1
    j = len(token) - 1
    while j >= i and not token[j].isalnum():
        j -= 1
    leading = token[:i]
    core = token[i:j+1] if j >= i else ""
    trailing = token[j+1:] if j+1 < len(token) else ""
    return leading, core, trailing


def _overlap_ms(a_start: int, a_end: int, b_start: int, b_end: int) -> int:
    return max(0, min(a_end, b_end) - max(a_start, b_start))


def _jaccard_similarity(tokens_a: List[str], tokens_b: List[str]) -> float:
    if not tokens_a or not tokens_b:
        return 0.0
    set_a = set(tokens_a)
    set_b = set(tokens_b)
    inter = len(set_a & set_b)
    union = len(set_a | set_b)
    if union == 0:
        return 0.0
    return inter / union


def _apply_case_like(source: str, target_style: str) -> str:
    """
    Apply case style of target_style to source.
    - If target_style is all upper -> upper
    - If all lower -> lower
    - If title case -> title
    - Else keep source as is.
    """
    if not source:
        return source
    if target_style.isupper():
        return source.upper()
    if target_style.islower():
        return source.lower()
    if target_style.istitle():
        return source.title()
    return source


def _find_best_segment_window_for_cue(cue: Dict[str, Any], segments: List[Dict[str, Any]], window_ms: int = 8000) -> Tuple[int, int]:
    """
    Find segment index range [i, j) whose concatenated text best matches the cue tokens
    within a temporal window around the cue time.
    Returns (start_index, end_index_exclusive). If none fits, returns (-1, -1).
    """
    cue_center = (cue["start_ms"] + cue["end_ms"]) // 2
    cue_tokens = _tokenize(cue.get("text", ""))

    # Filter candidate segments by time proximity
    candidates: List[int] = []
    for idx, seg in enumerate(segments):
        # Keep segments whose center is within window_ms
        seg_center = (seg["start_ms"] + seg["end_ms"]) // 2
        if abs(seg_center - cue_center) <= window_ms:
            candidates.append(idx)

    if not candidates:
        # fallback: all segments
        candidates = list(range(len(segments)))

    best_score = -1.0
    best_span = (-1, -1)

    # Evaluate small windows around candidates: single seg and neighboring joins
    for idx in candidates:
        for span_len in (1, 2, 3):
            i = idx
            j = min(len(segments), i + span_len)
            if i >= j:
                continue
            # Build concatenated text and time range
            text = " ".join(segments[k]["text"] for k in range(i, j)).strip()
            tokens = _tokenize(text)
            sim = _jaccard_similarity(cue_tokens, tokens)
            # Consider also temporal overlap with cue window
            seg_start = segments[i]["start_ms"]
            seg_end = segments[j - 1]["end_ms"]
            time_overlap = _overlap_ms(seg_start, seg_end, cue["start_ms"], cue["end_ms"])
            # Weighted scoring: prioritize token sim, then time overlap
            score = sim * 0.8 + (time_overlap / max(1, (cue["end_ms"] - cue["start_ms"]))) * 0.2
            if score > best_score:
                best_score = score
                best_span = (i, j)

    # If tokens are empty, just align by time nearest single segment
    if not cue_tokens and best_span == (-1, -1) and segments:
        # pick segment with closest center
        min_d = 1e18
        best_idx = 0
        for i, seg in enumerate(segments):
            d = abs(((seg["start_ms"] + seg["end_ms"]) // 2) - cue_center)
            if d < min_d:
                min_d = d
                best_idx = i
        return (best_idx, best_idx + 1)

    return best_span


def _build_corrected_cue_from_segments(span: Tuple[int, int], segments: List[Dict[str, Any]], base_cue_text: Optional[str] = None) -> Dict[str, Any]:
    """
    Build a corrected cue covering the given segment span.

    If base_cue_text is provided, perform word-level correction with semantic and fuzzy logic:
    - Extract transcript tokens from the span.
    - Compute token overlap to guard against low-overlap windows.
    - For each subtitle token:
        * If core matches or is a synonym of any window token (or similarity >= SEMANTIC_SIMILARITY_THRESHOLD),
          keep as-is to preserve paraphrases/synonyms.
        * Else if best fuzzy match similarity >= FUZZY_SPELLING_THRESHOLD, replace with the best transcript word.
        * Else, map sequentially to next transcript core (previous fallback) to softly guide wording.
    - Preserve punctuation, casing, and token structure.

    Returns:
        Dict with keys: start_ms, end_ms, text, and metadata:
            _meta: {
                'overlap': float,
                'conservative_mode': bool,
                'replacements': [ {'from': str, 'to': str, 'reason': str, 'score': float} ... ],
                'kept_tokens': [str],
            }
    """
    i, j = span
    if i < 0 or j <= i or i >= len(segments):
        return {}
    segs = segments[i:j]
    start_ms = segs[0]["start_ms"]
    end_ms = segs[-1]["end_ms"]

    # Gather transcript tokens and core list
    transcript_text = " ".join(x["text"] for x in segs if x.get("text"))
    transcript_tokens = _tokenize(transcript_text)
    transcript_cores = []
    for t in transcript_tokens:
        _, tcore, _ = _split_token_core_punct(t)
        if tcore:
            transcript_cores.append(tcore)

    if not base_cue_text:
        return {"start_ms": start_ms, "end_ms": end_ms, "text": transcript_text, "_meta": {"overlap": 1.0, "conservative_mode": False, "replacements": [], "kept_tokens": []}}

    sub_tokens_raw = base_cue_text.split() if base_cue_text else []
    sub_cores_for_overlap = []
    for st in sub_tokens_raw:
        _, sc, _ = _split_token_core_punct(st)
        if sc:
            sub_cores_for_overlap.append(sc)

    overlap = _token_overlap_ratio(sub_cores_for_overlap, transcript_cores)
    conservative_mode = overlap < LOW_OVERLAP_SKIP_THRESHOLD

    corrected_tokens: List[str] = []
    t_idx = 0
    replacements: List[Dict[str, Any]] = []
    kept_tokens: List[str] = []

    for sub_tok in sub_tokens_raw:
        lead, core, trail = _split_token_core_punct(sub_tok)
        if core == "":
            corrected_tokens.append(sub_tok)
            kept_tokens.append(sub_tok)
            continue

        if conservative_mode:
            # Allow only very strong fuzzy correction even in conservative mode
            mapped_core = core
            if transcript_cores:
                cand, score = _best_fuzzy_match(core, transcript_cores)
                if score >= max(FUZZY_SPELLING_THRESHOLD, 0.90):  # very high confidence
                    mapped_core = _apply_case_like(cand, core)
                    replacements.append({"from": core, "to": mapped_core, "reason": "fuzzy-high-conservative", "score": score})
                else:
                    kept_tokens.append(core)
            # Advance index lightly to keep relative progression
            if t_idx < len(transcript_cores):
                t_idx += 1
            corrected_tokens.append(f"{lead}{mapped_core}{trail}")
            continue

        # Non-conservative: attempt semantic preserve or fuzzy spelling correction
        keep_as_is = False
        best_semantic = 0.0

        # Check direct synonym/equality with any transcript core (fast path)
        for t_core in transcript_cores:
            if _synonym_or_same(core, t_core):
                keep_as_is = True
                break

        # If not synonym, compute best semantic similarity
        best_cand = core
        best_score = 0.0
        if not keep_as_is and transcript_cores:
            best_cand, best_semantic = _best_fuzzy_match(core, transcript_cores)
            best_score = best_semantic
            if best_semantic >= SEMANTIC_SIMILARITY_THRESHOLD:
                keep_as_is = True

        if keep_as_is:
            corrected_tokens.append(f"{lead}{core}{trail}")
            kept_tokens.append(core)
            continue

        # Not semantic; consider as spelling error if fuzzy is strong enough
        mapped_core = core
        if transcript_cores:
            cand, score = (best_cand, best_score) if best_cand != core else _best_fuzzy_match(core, transcript_cores)
            if score >= FUZZY_SPELLING_THRESHOLD:
                mapped_core = _apply_case_like(cand, core)
                replacements.append({"from": core, "to": mapped_core, "reason": "fuzzy", "score": score})
            else:
                # Soft sequential guide (fallback) - keep original core but advance index
                if t_idx < len(transcript_cores):
                    t_idx += 1
                kept_tokens.append(core)

        corrected_tokens.append(f"{lead}{mapped_core}{trail}")

    corrected_text = " ".join(corrected_tokens).strip()
    if not corrected_text:
        corrected_text = transcript_text

    return {
        "start_ms": start_ms,
        "end_ms": end_ms,
        "text": corrected_text,
        "_meta": {
            "overlap": overlap,
            "conservative_mode": conservative_mode,
            "replacements": replacements,
            "kept_tokens": kept_tokens,
        },
    }


def _generate_missing_cues(segments: List[Dict[str, Any]], used_spans: List[Tuple[int, int]]) -> List[Dict[str, Any]]:
    """
    Create cues for segments not covered by any used span.
    """
    covered = [False] * len(segments)
    for (i, j) in used_spans:
        for k in range(max(0, i), min(len(segments), j)):
            covered[k] = True
    out: List[Dict[str, Any]] = []
    # Group uncovered runs into cues
    k = 0
    while k < len(segments):
        if covered[k]:
            k += 1
            continue
        run_start = k
        while k < len(segments) and not covered[k]:
            k += 1
        run_end = k  # exclusive
        # Build a cue from run [run_start, run_end)
        cue = _build_corrected_cue_from_segments((run_start, run_end), segments)
        if cue:
            out.append(cue)
    return out


# --------------------------
# OTT timing constraints
# --------------------------

def _enforce_ott_constraints(cues: List[Dict[str, Any]],
                             min_duration_ms: int = 800,
                             max_duration_ms: int = 8000) -> List[Dict[str, Any]]:
    """
    Enforce basic OTT constraints:
    - Each cue duration within [min_duration_ms, max_duration_ms]
    - No overlaps; adjust by shifting ends or starts slightly
    - Ensure chronological order
    """
    if not cues:
        return []

    cues_sorted = sorted(cues, key=lambda x: (x["start_ms"], x["end_ms"]))
    fixed: List[Dict[str, Any]] = []
    prev_end = 0

    for i, cue in enumerate(cues_sorted):
        orig_start = int(cue["start_ms"])
        orig_end = int(cue["end_ms"])
        start = max(prev_end, orig_start)
        end = max(start + 1, orig_end)
        dur = end - start
        change_reasons = []

        # Resolve overlap with previous
        if start != orig_start:
            change_reasons.append(f"shift-start-to-avoid-overlap prev_end={prev_end}")

        # Clamp duration
        if dur < min_duration_ms:
            end = start + min_duration_ms
            dur = min_duration_ms
            change_reasons.append(f"min-duration {min_duration_ms}ms")
        elif dur > max_duration_ms:
            end = start + max_duration_ms
            dur = max_duration_ms
            change_reasons.append(f"max-duration {max_duration_ms}ms")

        if change_reasons or orig_start != start or orig_end != end:
            print(f"[OTT] Cue#{i+1} time adjusted: "
                  f"{_ms_to_srt_time(orig_start)} --> {_ms_to_srt_time(orig_end)}  "
                  f"to  {_ms_to_srt_time(start)} --> {_ms_to_srt_time(end)}  "
                  f"reason={'|'.join(change_reasons) if change_reasons else 'normalize'}")

        fixed.append({"start_ms": start, "end_ms": end, "text": cue.get("text", "")})
        prev_end = end

    return fixed


def _merge_and_sort_cues(primary: List[Dict[str, Any]], generated: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Merge two sets of cues and sort by time, attempting to avoid duplicates with identical times/text.
    """
    all_cues = list(primary) + list(generated)
    # Remove exact duplicates
    unique = []
    seen = set()
    for c in all_cues:
        key = (c["start_ms"], c["end_ms"], c.get("text", ""))
        if key in seen:
            continue
        seen.add(key)
        unique.append(c)
    return sorted(unique, key=lambda x: (x["start_ms"], x["end_ms"]))


def _reindex_and_format_srt(cues: List[Dict[str, Any]]) -> str:
    """
    Convert normalized cues to SRT text with reindexing.
    """
    lines: List[str] = []
    for idx, cue in enumerate(cues, start=1):
        start = _ms_to_srt_time(int(cue["start_ms"]))
        end = _ms_to_srt_time(int(cue["end_ms"]))
        text = cue.get("text", "")
        # Keep lines reasonable by splitting on explicit newlines only (do not auto-wrap by chars)
        lines.append(str(idx))
        lines.append(f"{start} --> {end}")
        if text:
            lines.extend(text.splitlines())
        lines.append("")  # blank separator
    return "\n".join(lines).rstrip() + "\n"


# --------------------------
# Public interfaces
# --------------------------

# PUBLIC_INTERFACE
def correct_subtitles(transcript: dict, subtitles: list) -> list:
    """Align and correct per-cue timestamps and text using the provided transcript.

    Behavior:
    - Language-agnostic: uses Unicode normalization and whitespace tokenization only.
    - If transcript and subtitle languages clearly differ (either via explicit 'language' keys or
      conservative script profile mismatch), return the original subtitles unchanged.
    - Align each subtitle cue to the most similar transcript segment window based on token overlap
      and temporal proximity; adjust cue timestamps and text accordingly.
    - Generate missing cues for transcript segments not covered by any subtitle cue.
    - Enforce OTT timing constraints (min/max duration) and remove overlaps; reindex cues.
    - Edge cases: empty inputs return empty list.

    Args:
        transcript: Whisper-like transcript dict with 'segments': [{'start': float sec, 'end': float sec, 'text': str}, ...]
                    Optional 'language' key may be present.
        subtitles: List of cues, each dict containing any of: start/end (sec), start_ms/end_ms (ms), text, optional 'language'.

    Returns:
        List of corrected cues with structure: {'start_ms': int, 'end_ms': int, 'text': str}
        This function is pure and performs no file I/O.
    """
    if not isinstance(transcript, dict) or not isinstance(subtitles, list):
        return subtitles or []

    segments = _flatten_transcript_segments(transcript)
    cues_in = _normalize_subtitle_cues(subtitles)

    if not segments or not cues_in:
        return cues_in

    if not _likely_same_language(transcript, cues_in):
        print("[CorrectSubtitles] Language mismatch detected; returning original subtitles unchanged.")
        return subtitles

    # Counters for safeguard reporting
    changed_time = 0
    changed_text = 0
    duration_clamped = 0

    used_spans: List[Tuple[int, int]] = []
    aligned_cues: List[Dict[str, Any]] = []

    for idx, cue in enumerate(cues_in, start=1):
        span = _find_best_segment_window_for_cue(cue, segments)
        if span == (-1, -1):
            # No matching window by similarity; snap to nearest transcript segment by time
            # This ensures start times correspond to real speech window.
            nearest_idx = None
            min_d = 1e18
            cue_center = (cue["start_ms"] + cue["end_ms"]) // 2
            for i, seg in enumerate(segments):
                d = abs(((seg["start_ms"] + seg["end_ms"]) // 2) - cue_center)
                if d < min_d:
                    min_d = d
                    nearest_idx = i
            if nearest_idx is not None:
                span = (nearest_idx, nearest_idx + 1)
                print(f"[Align] Cue#{idx}: No text match; snapped to nearest transcript segment {nearest_idx}.")
            else:
                print(f"[Align] Cue#{idx}: No transcript available; keeping original timing and text.")
                aligned_cues.append({"start_ms": cue["start_ms"], "end_ms": cue["end_ms"], "text": cue.get("text", "")})
                continue

        used_spans.append(span)
        corrected = _build_corrected_cue_from_segments(span, segments, base_cue_text=cue.get("text", ""))

        if not corrected:
            print(f"[Align] Cue#{idx}: Failed to build corrected cue; keeping original.")
            aligned_cues.append({"start_ms": cue["start_ms"], "end_ms": cue["end_ms"], "text": cue.get("text", "")})
            continue

        # Always clamp cue to the transcript span window first (snap/clamp)
        seg_start = segments[span[0]]["start_ms"]
        seg_end = segments[span[1]-1]["end_ms"]
        new_start = max(seg_start, corrected["start_ms"])
        new_end = min(seg_end, corrected["end_ms"])
        # Ensure within the transcript span; if inverted due to min/max, expand to span
        if new_end <= new_start:
            new_start = seg_start
            new_end = seg_end

        # Track and log timestamp changes from original cue to aligned window prior to OTT
        if new_start != cue["start_ms"] or new_end != cue["end_ms"]:
            changed_time += 1
            print(
                f"[Align] Cue#{idx} time changed: "
                f"{_ms_to_srt_time(cue['start_ms'])} --> {_ms_to_srt_time(cue['end_ms'])}  "
                f"to  {_ms_to_srt_time(new_start)} --> {_ms_to_srt_time(new_end)} (snap-to-transcript)"
            )

        # Replace corrected timing
        corrected["start_ms"] = new_start
        corrected["end_ms"] = new_end

        # Log text changes and token-level replacements
        old_text = cue.get("text", "") or ""
        new_text = corrected.get("text", "") or ""
        if old_text != new_text:
            changed_text += 1
            print(f"[Text] Cue#{idx} text changed:\n  OLD: {old_text}\n  NEW: {new_text}")
        meta = corrected.get("_meta", {})
        if meta:
            if meta.get("conservative_mode"):
                print(f"[Text] Cue#{idx} conservative_mode=True (overlap={meta.get('overlap', 0.0):.2f}); limited changes applied.")
            reps = meta.get("replacements", [])
            for r in reps:
                print(f"[TextReplace] Cue#{idx}: '{r['from']}' -> '{r['to']}' reason={r.get('reason')} score={r.get('score'):.2f}")

        # Remove meta before proceeding
        corrected.pop("_meta", None)
        aligned_cues.append(corrected)

    # Generate missing cues for uncovered transcript segments
    missing = _generate_missing_cues(segments, used_spans)
    for m in missing:
        print(f"[Generate] New cue created for uncovered transcript span: "
              f"{_ms_to_srt_time(m['start_ms'])} --> {_ms_to_srt_time(m['end_ms'])} | {m.get('text','')[:80]}")

    merged = _merge_and_sort_cues(aligned_cues, missing)

    # Before OTT, detect overlong durations and log that they will be clamped
    for i, c in enumerate(merged, start=1):
        dur = c["end_ms"] - c["start_ms"]
        if dur > 8000:
            duration_clamped += 1
            print(f"[Duration] Cue#{i} overlong ({dur} ms); will be clamped to OTT max.")

    constrained = _enforce_ott_constraints(merged)

    # After OTT, report any further time changes by comparing merged vs constrained
    for i, cue in enumerate(constrained):
        if i < len(merged):
            m = merged[i]
            if m["start_ms"] != cue["start_ms"] or m["end_ms"] != cue["end_ms"]:
                print(f"[OTT-Final] Cue#{i+1} final time: "
                      f"{_ms_to_srt_time(m['start_ms'])} --> {_ms_to_srt_time(m['end_ms'])}  "
                      f"to  {_ms_to_srt_time(cue['start_ms'])} --> {_ms_to_srt_time(cue['end_ms'])}")

    # Safeguard summary
    total_cues = len(cues_in)
    if changed_time == 0 and changed_text == 0 and duration_clamped == 0:
        print("[Summary] No cues were modified by alignment, text correction, or OTT duration clamping. "
              "Verify similarity thresholds and input transcript accuracy.")
    else:
        print(f"[Summary] Cues processed: {total_cues} | time-adjusted: {changed_time} | "
              f"text-changed: {changed_text} | duration-clamped: {duration_clamped}")

    return constrained


# PUBLIC_INTERFACE
def apply_additional_compliance_fixes(path: str, processed_dir: str) -> str:
    """Apply post-processing corrections; for now, return a copy to a new file.

    Args:
        path: Path to the corrected subtitle file to post-process.
        processed_dir: Directory to write the resulting file into.

    Returns:
        Absolute path to the newly written file in processed_dir.
    """
    src = Path(path)
    content = src.read_text(encoding="utf-8", errors="ignore")
    # Placeholder: could adjust reading speeds, spacing, punctuation etc.
    out = Path(processed_dir) / f"temp_{uuid.uuid4()}_postfix.srt"
    out.write_text(content, encoding="utf-8")
    return str(out)


# PUBLIC_INTERFACE
def log_matching_cues_summary_from_srt(subtitle_content: str, video_name: Optional[str] = None) -> None:
    """Print a centralized, simplified summary of matching cues and potential issues based on SRT content.

    This function is the single place responsible for high-level console output related to
    subtitle-audio matching summaries. It does not perform alignment; for detailed per-cue alignment
    and logging, see correct_subtitles().

    Args:
        subtitle_content: The SRT text content to scan.
        video_name: Optional video name for display in logs.
    """
    try:
        import re as _re
        blocks = _re.split(r"\n\s*\n", (subtitle_content or "").strip())
        cue_count = 0
        issues = 0
        sample_findings: List[str] = []
        for b in blocks:
            parts = b.splitlines()
            if len(parts) >= 2 and "-->" in "\n".join(parts[:2]):
                cue_count += 1
                text_lines = [x for x in parts[2:] if x.strip() != ""]
                for tl in text_lines:
                    if len(tl) > 42:
                        issues += 1
                        if len(sample_findings) < 5:
                            sample_findings.append(f"Long line ({len(tl)} chars): {tl[:60]}...")
        print("[QualityCheck] Subtitle-Audio Matching Cues Summary")
        if video_name:
            print(f"[QualityCheck] Video: {video_name}")
        print(f"[QualityCheck] Detected cues: {cue_count}")
        if issues == 0:
            print("[QualityCheck] No immediate reading-speed issues detected in sample scan.")
        else:
            print(f"[QualityCheck] Potential issues detected: {issues} (reading speed/line length)")
            for s in sample_findings:
                print(f"[QualityCheck] • {s}")
        print("[QualityCheck] Note: This is a simplified console summary. Detailed per-cue alignment is handled in correction modules.")
    except Exception as e:
        print(f"[QualityCheck] Failed to compute matching cues summary: {e}")
