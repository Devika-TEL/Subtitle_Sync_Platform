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

def _tokenize(text: str) -> List[str]:
    """
    Simple language-agnostic tokenization: split on whitespace.
    """
    if not text:
        return []
    return [tok for tok in text.split() if tok]


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

    If base_cue_text is provided, perform word-level correction:
    - Extract transcript tokens from the span.
    - Split subtitle tokens preserving leading/trailing punctuation.
    - Replace core words with closest transcript core words by sequential alignment.
      This keeps punctuation and general structure while improving lexical accuracy.
    """
    i, j = span
    if i < 0 or j <= i or i >= len(segments):
        return {}
    segs = segments[i:j]
    start_ms = segs[0]["start_ms"]
    end_ms = segs[-1]["end_ms"]

    # Gather transcript tokens
    transcript_text = " ".join(x["text"] for x in segs if x.get("text"))
    transcript_tokens = _tokenize(transcript_text)

    if not base_cue_text:
        # Fallback to concatenated transcript if no base for word-level mapping
        return {"start_ms": start_ms, "end_ms": end_ms, "text": transcript_text}

    # Prepare subtitle tokens (preserve whitespace boundaries)
    sub_tokens_raw = base_cue_text.split() if base_cue_text else []
    corrected_tokens: List[str] = []
    t_idx = 0

    for sub_tok in sub_tokens_raw:
        lead, core, trail = _split_token_core_punct(sub_tok)
        if core == "":
            # No alnum core; keep token as-is
            corrected_tokens.append(sub_tok)
            continue

        # Find next transcript core to map
        mapped = core
        while t_idx < len(transcript_tokens):
            t_tok = transcript_tokens[t_idx]
            t_idx += 1
            t_lead, t_core, t_trail = _split_token_core_punct(t_tok)
            if t_core:
                # Map case like subtitle core
                mapped = _apply_case_like(t_core, core)
                break
        # Rebuild token with preserved punctuation
        corrected_tokens.append(f"{lead}{mapped}{trail}")

    corrected_text = " ".join(corrected_tokens).strip()
    if not corrected_text:
        corrected_text = transcript_text

    return {"start_ms": start_ms, "end_ms": end_ms, "text": corrected_text}


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
        start = max(prev_end, int(cue["start_ms"]))
        end = max(start + 1, int(cue["end_ms"]))
        dur = end - start

        # Clamp duration
        if dur < min_duration_ms:
            end = start + min_duration_ms
            dur = min_duration_ms
        elif dur > max_duration_ms:
            end = start + max_duration_ms
            dur = max_duration_ms

        # Assign and advance
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
    # Defensive copies are not necessary; we build fresh outputs.
    if not isinstance(transcript, dict) or not isinstance(subtitles, list):
        return subtitles or []

    # Normalize inputs
    segments = _flatten_transcript_segments(transcript)
    cues_in = _normalize_subtitle_cues(subtitles)

    if not segments or not cues_in:
        # Nothing to align; return normalized cues as-is
        return cues_in

    # Language mismatch check
    if not _likely_same_language(transcript, cues_in):
        return subtitles  # original unchanged per requirements

    # Align cues to transcript segments
    used_spans: List[Tuple[int, int]] = []
    aligned_cues: List[Dict[str, Any]] = []
    for cue in cues_in:
        span = _find_best_segment_window_for_cue(cue, segments)
        if span == (-1, -1):
            # If no good span found, keep cue as-is but normalized
            aligned_cues.append({"start_ms": cue["start_ms"], "end_ms": cue["end_ms"], "text": cue.get("text", "")})
            continue
        used_spans.append(span)
        corrected = _build_corrected_cue_from_segments(span, segments, base_cue_text=cue.get("text", ""))
        if not corrected:
            # Fallback to original if construction failed
            aligned_cues.append({"start_ms": cue["start_ms"], "end_ms": cue["end_ms"], "text": cue.get("text", "")})
            continue
        aligned_cues.append(corrected)

    # Generate missing cues for uncovered transcript segments
    missing = _generate_missing_cues(segments, used_spans)

    # Merge, sort, and enforce OTT constraints
    merged = _merge_and_sort_cues(aligned_cues, missing)
    constrained = _enforce_ott_constraints(merged)

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
