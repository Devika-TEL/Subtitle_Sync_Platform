"""
Standalone alignment and correction module with optional Gemini LLM integration.

This file is self-contained and does not import any project-local modules.
It provides a public interface for transcript-based subtitle alignment and
light text correction suitable for OTT-style constraints.

Alignment policy (updated):
- Exact text matches: If a subtitle's text exactly matches its corresponding transcript text, the subtitle's timestamps
  are snapped to the transcript's timestamps (authoritative timing).
- Non-exact matches: The module optionally queries Gemini to judge semantic equivalence.
  * If semantically equivalent: keep the subtitle text and snap its timestamps to the transcript span.
  * If not semantically equivalent (or Gemini unavailable): replace the subtitle text with the transcript span text and
    snap timestamps. The transcript is the source of truth when semantics do not match.

Time normalization contract:
- All time values for 'start' and 'end' are normalized to float seconds internally and in outputs.
- If inputs contain SRT-like timecodes or strings, they are converted to float seconds at ingestion.
- No string timecodes are returned; callers can format times to SRT if needed using helper functions in this module.

Dependencies (optional but supported):
- google-generativeai (official Gemini SDK) — optional; used if available and enabled via env
- rapidfuzz (for robust fuzzy text similarity)
- sentence-transformers (for semantic similarity, optional; local model load only)
- language-tool-python (for grammar correction, optional; local or public API if available)
- python-srt (for composing/parsing SRT when needed, optional)

If optional dependencies are unavailable at runtime, the module falls back to
simpler heuristics to maintain deterministic behavior.

Important note on language support:
- All corrections here are heuristic/rule-based, with optional LLM rewriting if Gemini is available and enabled.
- For languages with complex tokenization or script (e.g., CJK, Thai, Arabic), results depend on spaCy/language-tool
  availability and the correctness of tokenization models. Without them, fallback heuristics apply and quality may be limited.

Gemini integration:
- This module supports the official Gemini Python SDK (google-generativeai) without using raw HTTP requests.
- To enable, set environment variables (recommended to be provided via the orchestrator into .env):
    GEMINI_API_KEY           # Your Google API key
    GEMINI_MODEL_NAME        # e.g., "gemini-1.5-pro" or "gemini-1.5-flash" (optional, defaults inside code)
    GEMINI_ENABLED           # "1" or "true" (case-insensitive) to enable usage in this module
- The code attempts to import google.generativeai; if missing, it will gracefully skip LLM calls.
- All Gemini usage is optional and guarded; local heuristics remain the default behavior.

PUBLIC_INTERFACE:
- write_corrected_alignment(transcript, subtitles, processed_dir=None, language=None) -> List[Dict]
  Create corrected, aligned subtitles and return as list of dicts (no file I/O)
"""

from __future__ import annotations

from typing import List, Dict, Any, Optional, Tuple, Callable, Union
import re
import logging
from math import isfinite
import json
import os


# ---------------------------
# Basic text utilities
# ---------------------------
_PUNCT_RE = re.compile(r"[^\w\s']", flags=re.UNICODE)
_WS_RE = re.compile(r"\s+")


def _try_import_gemini_sdk():
    """
    Attempt to import the official Gemini SDK.

    Returns:
        module or None: google.generativeai if import succeeded, else None.
    """
    try:
        import google.generativeai as genai  # type: ignore
        return genai
    except Exception:
        return None


def _is_truthy_env(val: Optional[str]) -> bool:
    return str(val or "").strip().lower() in {"1", "true", "yes", "on"}


def _init_gemini_client() -> Optional[Dict[str, Any]]:
    """
    Initialize Gemini client using the official SDK (if installed) and environment variables.

    Environment variables (should be managed by orchestrator; do not read .env directly here):
        GEMINI_API_KEY: API key for Google AI
        GEMINI_MODEL_NAME: Optional, e.g., "gemini-1.5-pro" or "gemini-1.5-flash"
        GEMINI_ENABLED: "1"/"true" to enable LLM usage in this module

    Returns:
        dict with {"genai": module, "model_name": str} or None if not enabled/unavailable.
    """
    # Only enable if explicitly toggled via env
    if not _is_truthy_env(os.getenv("GEMINI_ENABLED")):
        return None

    genai = _try_import_gemini_sdk()
    if genai is None:
        # SDK not installed; caller gets graceful fallback to heuristics.
        return None

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        # No API key provided; do not initialize.
        return None

    try:
        genai.configure(api_key=api_key)
        model_name = os.getenv("GEMINI_MODEL_NAME") or "gemini-1.5-flash"
        # We don't instantiate the model object globally to keep import-time light.
        return {"genai": genai, "model_name": model_name}
    except Exception:
        return None


def _gemini_generate_text(prompt: str, client: Optional[Dict[str, Any]], safety: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """
    Use the Gemini SDK to generate text for a given prompt.

    Args:
        prompt: The text prompt to send to the model.
        client: The dict returned by _init_gemini_client().
        safety: Optional dict to pass additional parameters (e.g., generation_config).

    Returns:
        The generated text (string) or None if generation fails or client is None.
    """
    if not client:
        return None
    try:
        model_name = client["model_name"]
        genai = client["genai"]
        # Create a GenerativeModel and call generate_content
        model = genai.GenerativeModel(model_name)
        generation_config = (safety or {}).get("generation_config") or {
            "temperature": 0.2,
            "top_p": 0.9,
            "top_k": 40,
            "max_output_tokens": 512,
        }
        response = model.generate_content(prompt, generation_config=generation_config)
        # Depending on SDK version, text may be in response.text or within candidates
        text = getattr(response, "text", None)
        if text:
            return str(text)
        # Fallback parse
        try:
            cands = getattr(response, "candidates", None)
            if cands and len(cands) > 0:
                parts = getattr(cands[0], "content", None)
                if parts and getattr(parts, "parts", None):
                    return "".join(getattr(p, "text", "") for p in parts.parts if hasattr(p, "text"))
        except Exception:
            pass
        return None
    except Exception:
        return None


def _gemini_correct_text_if_enabled(text: str, lang: Optional[str], client: Optional[Dict[str, Any]]) -> Optional[str]:
    """
    If Gemini SDK is enabled, request a lightly-edited version of the subtitle cue text
    constrained by OTT guidelines (no hallucinations, keep semantics).

    Returns the corrected text or None if not available.
    """
    if not client:
        return None
    # Craft a tightly-scoped instruction to minimize hallucination and preserve content
    language_hint = (lang or "en").lower()
    prompt = (
        "You are a subtitle editor. Improve grammar and punctuation of the following subtitle text "
        "without adding or removing semantic content. Keep names and entities intact. "
        "Respect OTT guidelines: max ~42 characters per line, max 2 lines. "
        "Return ONLY the corrected subtitle text, with line breaks if needed. "
        f"Language: {language_hint}.\n\n"
        f"Subtitle:\n{text.strip()}"
    )
    return _gemini_generate_text(prompt, client)


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


def _format_seconds_to_srt(seconds: float) -> str:
    ms = int(round(max(0.0, float(seconds)) * 1000))
    h = ms // 3_600_000
    ms %= 3_600_000
    m = ms // 60_000
    ms %= 60_000
    s = ms // 1000
    ms %= 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _rf_scores(a: str, b: str) -> Tuple[float, float]:
    """Compute RapidFuzz partial_ratio and token_set_ratio in [0,1], fallback to Jaccard."""
    try:
        from rapidfuzz import fuzz  # type: ignore
        pr = float(fuzz.partial_ratio(a, b)) / 100.0
        tr = float(fuzz.token_set_ratio(a, b)) / 100.0
        return pr, tr
    except Exception:
        at, bt = _tokens(a), _tokens(b)
        j = _jaccard(at, bt)
        return j, j


def _lazy_st_model_loader(model_name: str) -> Callable[[], Any]:
    """Return a zero-arg closure that loads the sentence-transformers model once (cached)."""
    model_ref: Dict[str, Any] = {"model": None, "name": model_name}

    def _load():
        if model_ref["model"] is None:
            from sentence_transformers import SentenceTransformer  # type: ignore

            model_ref["model"] = SentenceTransformer(model_ref["name"])
        return model_ref["model"]

    return _load


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


def _gemini_similarity_hint(sub_text: str, span_text: str, client: Optional[Dict[str, Any]]) -> float:
    """
    Optionally query Gemini to estimate semantic closeness between a subtitle and a transcript span.

    Returns:
        float similarity in [0,1], or 0.0 if unavailable.
    """
    if not client:
        return 0.0
    # Keep the request tiny to save tokens; ask for a number between 0 and 1.
    prompt = (
        "Rate the semantic similarity between the two snippets on a scale from 0.0 to 1.0.\n"
        "Respond with only the number (e.g., 0.82) and nothing else.\n\n"
        f"A: {sub_text}\n"
        f"B: {span_text}\n"
    )
    out = _gemini_generate_text(prompt, client)
    if not out:
        return 0.0
    try:
        val = float(re.findall(r"[0-1](?:\.\d+)?", out.strip())[0])
        return _clip(val, 0.0, 1.0)
    except Exception:
        return 0.0


def _hybrid_score(
    sub_text: str,
    span_text: str,
    weights: Dict[str, float],
    model_loader: Optional[Callable[[], Any]],
    *,
    gemini_client: Optional[Dict[str, Any]] = None,
) -> float:
    """Weighted combination of RapidFuzz metrics, embedding cosine, and optional Gemini similarity."""
    pr, tr = _rf_scores(sub_text, span_text)
    emb = _embedding_cosine(sub_text, span_text, model_loader)
    gsim = _gemini_similarity_hint(sub_text, span_text, gemini_client) if gemini_client else 0.0
    return (
        weights.get("rapidfuzz_partial", 0.35) * pr
        + weights.get("rapidfuzz_token", 0.35) * tr
        + weights.get("embedding", 0.2) * emb
        + weights.get("gemini", 0.1) * gsim
    )


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
    gemini_client: Optional[Dict[str, Any]] = None,
) -> Tuple[int, int, float]:
    """
    Find the best contiguous span [i, j] of transcript segments starting from start_idx within max_span
    that maximizes similarity to the subtitle.

    Enhancement: If an exact text match is found in any single transcript segment starting
    from start_idx within the search window, immediately return that exact-match span with a perfect score.

    - If hybrid=False: use Jaccard over tokens.
    - If hybrid=True: use weighted RapidFuzz + Embedding cosine (and optional Gemini score if provided).
    Returns (i, j_inclusive, score). If no span exceeds min_sim, returns (start_idx, start_idx, 0.0).
    """
    # Fast-path: exact literal match snap
    if raw_sub_text:
        sub_stripped = (raw_sub_text or "").strip()
        for k in range(start_idx, min(len(transcript), start_idx + max_span)):
            t_text = str(transcript[k].get("text", "")).strip()
            if t_text and t_text == sub_stripped:
                return (k, k, 1.0)

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
                score = _hybrid_score(
                    raw_sub_text or " ".join(sub_tokens),
                    span_text,
                    weights or {},
                    model_loader,
                    gemini_client=gemini_client,
                )
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
        est_end = min(span_end, base_start + min_duration)
        if est_end - base_start < min_duration and span_end - span_start >= min_duration:
            # try shifting start back if possible (bounded by span_start)
            base_start = max(span_start, est_end - min_duration)

    return (float(base_start), float(max(base_start + min_duration, est_end)))


def _enforce_monotonic_nonoverlap(
    subs: List[Dict],
    min_gap: float = 0.02,
    min_dur: float = 0.2,
) -> List[Dict]:
    """
    Make sure subtitle timings are monotonic and non-overlapping.
    - Ensures start[i] >= end[i-1] + min_gap
    - Ensures duration >= min_dur (expanding end if necessary)
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
        s["start"], s["end"] = start, max(end, start)
    # Second pass: ensure next starts after current with min gap; if needed, extend next
    for i in range(len(result) - 1):
        cur = result[i]
        nxt = result[i + 1]
        if _safe_float(nxt["start"]) < _safe_float(cur["end"]) + min_gap:
            nxt["start"] = _safe_float(cur["end"]) + min_gap
            if _safe_float(nxt["end"]) < _safe_float(nxt["start"]) + min_dur:
                nxt["end"] = _safe_float(nxt["start"]) + min_dur
    return result


# ---------------------------
# Light text correction
# ---------------------------
_PUNCT_SPACE_RE = re.compile(r"\s+")
_TRAILING_SPACES_RE = re.compile(r"[ \t]+$", re.MULTILINE)


def _nfkc_normalize(text: str) -> str:
    try:
        import unicodedata
        return unicodedata.normalize("NFKC", text)
    except Exception:
        return text


def _normalize_spaces(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _TRAILING_SPACES_RE.sub("", text)
    # Collapse multiple spaces but preserve newlines
    return "\n".join(_PUNCT_SPACE_RE.sub(" ", ln).strip() for ln in text.splitlines())


def _sentence_case(s: str) -> str:
    if not s:
        return s
    first_alpha = next((i for i, ch in enumerate(s) if ch.isalpha()), None)
    if first_alpha is None:
        return s
    return s[:first_alpha] + s[first_alpha:first_alpha + 1].upper() + s[first_alpha + 1:]


def _load_spacy_model(lang: str) -> Optional[Callable[[], any]]:
    """
    Return a lazy loader for spaCy model based on ISO-639-1 code.
    Fallback gracefully if not installed.
    """
    lang = (lang or "en").lower()
    lang_to_model = {
        "en": "en_core_web_sm",
        "es": "es_core_news_sm",
        "fr": "fr_core_news_sm",
        "de": "de_core_news_sm",
        "it": "it_core_news_sm",
        "pt": "pt_core_news_sm",
        "nl": "nl_core_news_sm",
        "xx": "xx_sent_ud_sm",
    }
    model_name = lang_to_model.get(lang, "xx_sent_ud_sm")
    state: Dict[str, any] = {"nlp": None}

    def _loader():
        if state["nlp"] is not None:
            return state["nlp"]
        try:
            import spacy  # type: ignore
            state["nlp"] = spacy.load(model_name)
            return state["nlp"]
        except Exception:
            try:
                import spacy  # type: ignore
                state["nlp"] = spacy.blank(lang if hasattr(spacy.util, "get_lang_class") else "xx")  # type: ignore
                return state["nlp"]
            except Exception:
                return None

    return _loader


def _spacy_protect_entities(text: str, nlp_loader: Optional[Callable[[], any]]) -> List[Tuple[str, bool]]:
    """
    Split text into tokens and mark protected spans (e.g., named entities).
    Returns list of (token_text, protected). Falls back to unprotected span if unavailable.
    """
    if nlp_loader is None:
        return [(text, False)]
    try:
        nlp = nlp_loader()
        if nlp is None:
            return [(text, False)]
        doc = nlp(text)
        protected_ranges = []
        if hasattr(doc, "ents"):
            for ent in doc.ents:
                protected_ranges.append((ent.start_char, ent.end_char))
        tokens: List[Tuple[str, bool]] = []
        i = 0
        for start, end in protected_ranges:
            if i < start:
                tokens.append((text[i:start], False))
            tokens.append((text[start:end], True))
            i = end
        if i < len(text):
            tokens.append((text[i:], False))
        if not protected_ranges:
            return [(text, False)]
        return tokens
    except Exception:
        return [(text, False)]


def _apply_language_tool(text: str, lang: str) -> str:
    """
    Run language-tool-python corrections. If unavailable, return original text.
    """
    try:
        import language_tool_python  # type: ignore
        # Try Public API first
        try:
            tool = language_tool_python.LanguageToolPublicAPI(lang.lower() or "en")
            matches = tool.check(text)
            return language_tool_python.utils.correct(text, matches)
        except Exception:
            tool = language_tool_python.LanguageTool(lang.lower() or "en")
            matches = tool.check(text)
            return language_tool_python.utils.correct(text, matches)
    except Exception:
        return text


def _normalize_punctuation(text: str) -> str:
    text = text.replace(" ,", ",").replace(" .", ".").replace(" !", "!").replace(" ?", "?")
    text = re.sub(r"\s+([,\.!?;:])", r"\1", text)
    text = re.sub(r"([\(\[])\\s+", r"\1", text)
    text = re.sub(r"\s+([\)\]])", r"\1", text)
    return text


def _wrap_text(text: str, max_chars_per_line: int, max_lines: int) -> List[str]:
    """
    Greedy word-wrapping for subtitle cues:
    - Do not exceed max_chars_per_line
    - Try to balance two lines by length if max_lines == 2
    - If single word exceeds max, hard-break
    """
    words = text.split()
    if not words:
        return [""]
    lines: List[str] = []
    cur = ""
    for w in words:
        if not cur:
            cur = w
            continue
        if len(cur) + 1 + len(w) <= max_chars_per_line:
            cur = f"{cur} {w}"
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)

    if len(lines) > max_lines:
        joined = " ".join(words)
        if max_lines == 1:
            if len(joined) <= max_chars_per_line:
                return [joined]
            return [joined[:max_chars_per_line]]
        else:
            half = max(1, min(len(joined) // 2, len(joined) - 1))
            left = joined.rfind(" ", 0, half)
            right = joined.find(" ", half)
            split_at = left if left != -1 else right
            if split_at == -1:
                split_at = half
            l1 = joined[:split_at].strip()
            l2 = joined[split_at:].strip()
            if len(l1) > max_chars_per_line:
                l1 = l1[:max_chars_per_line]
            if len(l2) > max_chars_per_line:
                l2 = l2[:max_chars_per_line]
            return [l1, l2]

    fixed: List[str] = []
    for ln in lines:
        if len(ln) <= max_chars_per_line:
            fixed.append(ln)
        else:
            fixed.append(ln[:max_chars_per_line])
    return fixed[:max_lines]


# PUBLIC_INTERFACE
def correct_subtitle_text(
    text: str,
    lang: Optional[str] = None,
    *,
    protect_entities: bool = True,
    sentence_case: bool = True,
    use_language_tool: bool = True,
    max_chars_per_line: int = 42,
    max_lines: int = 2,
    use_gemini_if_available: bool = True,
) -> str:
    """
    Correct grammar/spelling and format a subtitle cue text.

    If the official Gemini SDK is available and enabled via environment (GEMINI_ENABLED=1, GEMINI_API_KEY set),
    the function will first attempt a conservative LLM rewrite constrained by OTT rules; if it fails or is disabled,
    it falls back to local heuristics and language-tool when available.
    """
    lang = (lang or "en").lower()
    original = text or ""

    # Try Gemini LLM correction first (optional)
    corrected_via_llm: Optional[str] = None
    gemini_client = _init_gemini_client() if use_gemini_if_available else None
    if gemini_client:
        llm_out = _gemini_correct_text_if_enabled(original, lang, gemini_client)
        if isinstance(llm_out, str) and llm_out.strip():
            corrected_via_llm = llm_out.strip()

    if corrected_via_llm:
        # Still apply final wrapping to respect display constraints
        return "\n".join(_wrap_text(_normalize_spaces(_nfkc_normalize(corrected_via_llm)), int(max_chars_per_line or 42), int(max_lines or 2)))

    # Local heuristic corrections
    normalized = _normalize_spaces(_nfkc_normalize(original))
    nlp_loader = _load_spacy_model(lang) if protect_entities else None
    spans = _spacy_protect_entities(normalized, nlp_loader) if protect_entities else [(normalized, False)]

    corrected_parts: List[str] = []
    for span_text, is_protected in spans:
        part = span_text
        if not is_protected:
            if sentence_case:
                part = _sentence_case(part)
            if use_language_tool:
                part = _apply_language_tool(part, lang)
            part = _normalize_punctuation(part)
        corrected_parts.append(part)

    corrected = "".join(corrected_parts)
    corrected = _normalize_spaces(corrected)
    wrapped = "\n".join(_wrap_text(corrected, int(max_chars_per_line or 42), int(max_lines or 2)))
    return wrapped


# ---------------------------
# Core alignment
# ---------------------------
def _get_logger(verbose: bool, logger: Optional[logging.Logger]) -> Optional[logging.Logger]:
    """Return logger instance according to verbose and provided logger."""
    if logger is not None:
        return logger
    if verbose:
        logging.basicConfig(level=logging.INFO)
        return logging.getLogger(__name__)
    return None


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
    # Advanced toggles (no project config dependency; use provided or defaults)
    enable_hybrid: Optional[bool] = False,
    embedding_model_name: Optional[str] = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    fuzzy_weights: Optional[Dict[str, float]] = None,
    default_chars_per_sec: Optional[float] = 15.0,
    max_cue_duration: Optional[float] = 6.0,
    delayed_start_threshold: Optional[float] = 0.5,
) -> List[Dict]:
    """
    Align subtitles' start/end timings and text to a reference transcript.

    Rules implemented:
    1) If subtitle text and the matched transcript text are exactly the same (literal match) but timestamps differ,
       snap the subtitle start/end to the transcript span timings.
    2) If texts do not match literally, use Gemini SDK (if enabled via env) to test if they are semantically equivalent.
       - If semantically equivalent, keep the subtitle text and snap its timestamps to the transcript span timings.
       - If not semantically equivalent (or Gemini unavailable), correct the subtitle text to exactly match the transcript
         span text and align timestamps to the transcript.
    3) Transcript is the authority whenever semantic parity is not met.

    Contract:
    - Inputs may contain numeric seconds, strings, or SRT-like timecodes for 'start'/'end'.
    - All inputs are normalized to float seconds internally.
    - The returned list always uses float seconds for 'start' and 'end' (no strings/timecodes).
    - Gemini integration requires environment variables:
        GEMINI_ENABLED=1, GEMINI_API_KEY, optional GEMINI_MODEL_NAME
      If not available, semantic checks fall back to hybrid/fuzzy or simple heuristics only.
    """
    # ---- Normalize transcript ----
    if isinstance(transcript, dict):
        segments_raw = transcript.get("segments") or []
        if not isinstance(segments_raw, list):
            segments_raw = []
        transcript_list = segments_raw
    elif isinstance(transcript, list):
        transcript_list = transcript
    else:
        raise TypeError("transcript must be a Whisper-like dict with 'segments' or a list of segments")

    def _maybe_timecode_to_seconds(v: Any) -> float:
        if isinstance(v, (int, float)):
            try:
                return float(v)
            except Exception:
                return 0.0
        if isinstance(v, str):
            m = re.match(r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})", v.strip())
            if m:
                h, mi, s, ms = m.groups()
                return int(h) * 3600 + int(mi) * 60 + int(s) + int(ms) / 1000.0
            try:
                return float(v)
            except Exception:
                return 0.0
        try:
            return float(v)
        except Exception:
            return 0.0

    t_coerced: List[Dict[str, Any]] = []
    for seg in transcript_list:
        if seg is None:
            continue
        if isinstance(seg, dict):
            text = str(seg.get("text", "")) if seg.get("text") is not None else ""
            start = _maybe_timecode_to_seconds(seg.get("start", 0.0))
            end = _maybe_timecode_to_seconds(seg.get("end", 0.0))
        else:
            text = str(seg)
            start = 0.0
            end = 0.0
        t_coerced.append({"text": text, "start": float(start), "end": float(end if end >= start else start)})
    t_segments = _sort_by_start(t_coerced)

    # ---- Normalize subtitles ----
    if not isinstance(subtitles, list):
        raise TypeError("subtitles must be a list of dicts")

    s_raw: List[Dict[str, Any]] = []
    for idx, c in enumerate(subtitles, start=1):
        if c is None:
            c = {}
        if not isinstance(c, dict):
            c = {"text": str(c)}
        text = str(c.get("text", "")) if c.get("text") is not None else ""
        start = _maybe_timecode_to_seconds(c.get("start", 0.0))
        end = _maybe_timecode_to_seconds(c.get("end", 0.0))
        index_val = c.get("index")
        try:
            index = int(index_val) if index_val is not None else idx
        except Exception:
            index = idx
        fmt = c.get("format")
        fmt = str(fmt).strip() if isinstance(fmt, str) else ""
        if end < start:
            end = start
        s_raw.append(
            {
                "index": index,
                "start": float(start),
                "end": float(end),
                "text": text,
                "format": fmt,
            }
        )

    # Determine common format: first non-empty wins
    common_format = ""
    for c in s_raw:
        if c["format"]:
            common_format = c["format"]
            break

    s_cues = sorted(s_raw, key=lambda x: _safe_float(x.get("start", 0.0)))

    if not t_segments or not s_cues:
        normalized: List[Dict] = []
        for idx, item in enumerate(s_cues, start=1):
            start_v = _safe_float(item.get("start", 0.0))
            end_v = _safe_float(item.get("end", 0.0))
            text_v = str(item.get("text", ""))
            normalized.append(
                {
                    "index": int(idx),
                    "start": float(start_v),
                    "end": float(end_v if end_v >= start_v else start_v),
                    "text": text_v,
                    "format": common_format,
                }
            )
        return normalized

    _logger = _get_logger(verbose, logger)

    enable_hybrid = bool(enable_hybrid)
    embedding_model_name = embedding_model_name or "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    fuzzy_weights = fuzzy_weights or {"rapidfuzz_partial": 0.4, "rapidfuzz_token": 0.4, "embedding": 0.2}
    default_chars_per_sec = float(default_chars_per_sec or 15.0)
    max_cue_duration = float(max_cue_duration or 6.0)
    delayed_start_threshold = float(delayed_start_threshold or 0.5)

    model_loader = _lazy_st_model_loader(embedding_model_name) if enable_hybrid else None

    # Initialize Gemini client once (optional; requires GEMINI_ENABLED and GEMINI_API_KEY)
    gemini_client = _init_gemini_client()

    aligned: List[Dict] = []
    t_idx = 0

    for cue_idx, cue in enumerate(s_cues):
        sub_text = str(cue.get("text", ""))
        sub_tokens = _tokens(sub_text)
        orig_start = _safe_float(cue.get("start", 0.0))
        orig_end = _safe_float(cue.get("end", 0.0))

        i, j, score = _best_transcript_span_for_sub(
            sub_tokens=sub_tokens,
            transcript=t_segments,
            start_idx=t_idx,
            max_span=max_span,
            min_sim=min_similarity,
            hybrid=bool(enable_hybrid),
            weights=fuzzy_weights,
            model_loader=model_loader,
            raw_sub_text=sub_text,
            gemini_client=gemini_client,
        )

        new_cue = dict(cue)
        if score >= min_similarity:
            span = t_segments[i : j + 1]
            span_text = _merge_texts(span)
            span_start, span_end = _span_time(span)

            # Decision 1: literal match => snap times to transcript span
            literal_match = sub_text.strip() == span_text.strip()

            # Optional semantic equivalence via Gemini (only if no literal match)
            semantically_equivalent = False
            if not literal_match and gemini_client:
                try:
                    sim = _gemini_similarity_hint(sub_text.strip(), span_text.strip(), gemini_client)
                    # Threshold: fairly strict, but tolerant to minor paraphrase
                    semantically_equivalent = sim >= 0.85
                except Exception:
                    semantically_equivalent = False

            # Compute target times: always prefer transcript span times when we deem texts equivalent or will replace text
            # We still distribute within span using reading-speed estimate to respect min durations and gaps.
            last_end = aligned[-1]["end"] if aligned else 0.0
            est_start, est_end = _distribute_time_within_span_with_delayed_fix(
                sub_text=(span_text if (literal_match or semantically_equivalent or not sub_text.strip()) else sub_text),
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
            if est_end - est_start < min_duration:
                est_end = est_start + min_duration
                if est_end > span_end:
                    shift = est_end - span_end
                    est_end = span_end
                    est_start = max(span_start, est_start - shift)

            # Rule application on text:
            # - If literal match: keep original subtitle text (already same) and snap times.
            # - Else if semantic equivalent: keep subtitle text, but snap times to transcript span.
            # - Else (not equivalent or Gemini not available): replace subtitle text with transcript span text and align times.
            if literal_match:
                # Text unchanged; times snapped (via est_start/est_end within span)
                new_text = sub_text
            elif semantically_equivalent:
                new_text = sub_text
            else:
                # Semantic mismatch: Use transcript as authority for text.
                new_text = span_text

            new_cue["text"] = new_text
            new_cue["start"] = float(est_start)
            new_cue["end"] = float(est_end)
            t_idx = max(t_idx, j)
        else:
            # No acceptable span: keep original timing (cleaned to min duration), do not alter text.
            start_o = _safe_float(cue.get("start", 0.0))
            end_o = _safe_float(cue.get("end", start_o + min_duration))
            if end_o - start_o < min_duration:
                end_o = start_o + min_duration
            new_cue["start"] = float(start_o)
            new_cue["end"] = float(end_o)

        if _logger is not None and (new_cue["start"] != orig_start or new_cue["end"] != orig_end):
            # Indicate if text changed relative to original
            text_changed = (new_cue.get("text", "") or "") != (sub_text or "")
            _logger.info(
                "Alignment change | cue=%d | %0.3f-->%0.3f -> %0.3f-->%0.3f | sim=%0.3f | text_changed=%s",
                cue_idx,
                orig_start,
                orig_end,
                new_cue["start"],
                new_cue["end"],
                float(score),
                str(bool(text_changed)),
            )

        aligned.append(new_cue)

    aligned = _enforce_monotonic_nonoverlap(aligned, min_gap=min_gap, min_dur=min_duration)

    normalized: List[Dict] = []
    for idx, item in enumerate(aligned, start=1):
        start_v = _safe_float(item.get("start", 0.0))
        end_v = _safe_float(item.get("end", 0.0))
        text_v = str(item.get("text", ""))
        out_item = {
            "index": int(idx),
            "start": float(start_v),
            "end": float(end_v if end_v >= start_v else start_v),
            "text": text_v,
            "format": common_format,
        }
        # Enforce float seconds contract
        assert isinstance(out_item["start"], float), "start must be float seconds"
        assert isinstance(out_item["end"], float), "end must be float seconds"
        normalized.append(out_item)
    return normalized


def _compose_srt(cues: List[Dict]) -> str:
    """
    Compose an SRT text from a list of cues.
    Note: This helper is intentionally kept for callers who want to write output themselves.
    Expects 'start' and 'end' to be float seconds and performs SRT formatting.
    """
    out_lines: List[str] = []
    for i, cue in enumerate(cues, start=1):
        start = _format_seconds_to_srt(float(cue.get("start", 0.0)))
        end = _format_seconds_to_srt(float(cue.get("end", float(cue.get("start", 0.0)) + 0.5)))
        text = (cue.get("text") or "").strip()
        out_lines.append(str(i))
        out_lines.append(f"{start} --> {end}")
        if text:
            out_lines.extend(text.splitlines())
        out_lines.append("")  # blank line
    return "\n".join(out_lines).strip() + "\n"


# PUBLIC_INTERFACE
def write_corrected_alignment(
    transcript: Any,
    subtitles: List[Dict],
    *,
    processed_dir: Optional[str] = None,  # retained for signature compatibility; not used
    language: Optional[str] = None,
) -> List[Dict]:
    """Create corrected, aligned subtitles and return them as a list of dicts.

    PUBLIC_INTERFACE
    Args:
        transcript: Whisper-like transcript content. Either:
            - dict with key 'segments' -> list of {'text','start','end'}
            - list of {'text','start','end'} items
            Non-dict items will be coerced to text with zeroed times.
        subtitles: List of subtitle dicts with keys:
            - index: int (optional; will be resequenced)
            - start: seconds (float) or timecode string, will be normalized to float seconds
            - end: seconds (float) or timecode string, will be normalized to float seconds
            - text: str
            - format: str (propagated to output if provided)
        processed_dir: Deprecated here; retained for compatibility (no write happens).
        language: Optional language code guiding light text correction.

    Behavior summary:
    - During alignment, for each cue we compare with the best transcript span:
        * If texts are exactly the same, we snap the cue times to the transcript span.
        * If texts differ, we use Gemini (if enabled) to check semantic equivalence. If equivalent, we keep the subtitle
          text and snap its times to the transcript span. If not equivalent or Gemini unavailable, we replace the subtitle
          text with the transcript span text and snap times.
    - After alignment, we apply light grammatical/punctuation correction and OTT wrapping conservatively.

    Returns:
        List[Dict]: Corrected subtitles with 'start' and 'end' guaranteed to be float seconds:
            [{ "index": int, "start": float, "end": float, "text": str, "format": str }, ...]
    """
    aligned_cues = align_subtitles_to_transcript(
        transcript=transcript,
        subtitles=subtitles,
        enable_hybrid=False,  # pure fuzzy by default to avoid heavy model load unless caller opts in
    )

    # Language note:
    # We perform only local, heuristic corrections below. Effectiveness varies by language, especially
    # where tokenization or grammar is complex and optional tools (spaCy/language-tool) are unavailable.
    lang = (language or "").strip().lower() or "auto"

    # Light local correction on text (grammar/punctuation/wrapping)
    final_cues: List[Dict] = []
    for cue in aligned_cues:
        fixed_text = correct_subtitle_text(
            text=cue.get("text", ""),
            lang=(None if lang == "auto" else lang),
            protect_entities=True,
            sentence_case=False,   # conservative by default
            use_language_tool=True,
            max_chars_per_line=42,
            max_lines=2,
        )
        new_cue = dict(cue)
        new_cue["text"] = fixed_text
        # Explicitly normalize to float seconds for contract enforcement
        new_cue["start"] = float(_safe_float(new_cue.get("start", 0.0)))
        new_cue["end"] = float(_safe_float(new_cue.get("end", new_cue["start"])))
        if new_cue["end"] < new_cue["start"]:
            new_cue["end"] = new_cue["start"]
        # Sanity asserts for public contract
        assert isinstance(new_cue["start"], float), "start must be float seconds"
        assert isinstance(new_cue["end"], float), "end must be float seconds"
        final_cues.append(new_cue)

    return final_cues


# PUBLIC_INTERFACE
def align_subtitles(
    transcript: Union[List[Dict], Dict[str, Any]],
    subtitles: List[Dict],
) -> List[Dict]:
    """Align subtitles against an authoritative transcript.

    PUBLIC_INTERFACE
    Implements the following policy:
    1) If text matches (case-insensitive normalized), but timestamps differ by > 1s, use the transcript's timestamps.
    2) If timestamps match (within 1s) but text differs, use the transcript text. Optionally, an LLM could be used to
       decide, but by default transcript text is preferred.
    3) Insert or remove subtitles so the output sequence matches the transcript's sequencing and content (treating the
       transcript as the authoritative source).

    Inputs:
        transcript: Whisper-like segments list or dict with "segments":
            - Either a list of dicts with keys: text, start, end
            - Or dict {"segments": [ ...same as above... ]}
        subtitles: list of dicts with shape:
            - index: int
            - start: float seconds (or a string that can be parsed)
            - end: float seconds (or a string that can be parsed)
            - text: str
            - format: str

    Returns:
        A list of dicts with the same keys as the input subtitles (index, start, end, text, format),
        sequenced to match the transcript order and content. Timestamps are float seconds.

    Notes:
        - This function does not attempt semantic LLM checks; it follows the simple prioritization rules above.
        - Normalization uses case-insensitive tokenization stripping punctuation for text matching.
    """
    # Reuse aligner machinery to match transcript spans, then override with rules specified.
    # Normalize transcript segments
    if isinstance(transcript, dict):
        t_raw = transcript.get("segments") or []
        if not isinstance(t_raw, list):
            t_raw = []
        t_list = t_raw
    elif isinstance(transcript, list):
        t_list = transcript
    else:
        raise TypeError("transcript must be a list or dict with 'segments'")

    def _maybe_timecode_to_seconds(v: Any) -> float:
        if isinstance(v, (int, float)):
            try:
                return float(v)
            except Exception:
                return 0.0
        if isinstance(v, str):
            m = re.match(r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})", v.strip())
            if m:
                h, mi, s, ms = m.groups()
                return int(h) * 3600 + int(mi) * 60 + int(s) + int(ms) / 1000.0
            try:
                return float(v)
            except Exception:
                return 0.0
        try:
            return float(v)
        except Exception:
            return 0.0

    transcript_segs: List[Dict[str, Any]] = []
    for seg in t_list:
        if not isinstance(seg, dict):
            # Coerce unknown types to text-only segments with zeroed time
            transcript_segs.append({"text": str(seg), "start": 0.0, "end": 0.0})
            continue
        st = _maybe_timecode_to_seconds(seg.get("start", 0.0))
        en = _maybe_timecode_to_seconds(seg.get("end", 0.0))
        if en < st:
            en = st
        transcript_segs.append(
            {"text": str(seg.get("text", "") or ""), "start": float(st), "end": float(en)}
        )
    transcript_segs = _sort_by_start(transcript_segs)

    # Normalize subtitles; also detect and propagate common format
    sub_cues: List[Dict[str, Any]] = []
    common_format = ""
    for idx, c in enumerate(subtitles or [], start=1):
        c = c or {}
        if not isinstance(c, dict):
            c = {"text": str(c)}
        st = _maybe_timecode_to_seconds(c.get("start", 0.0))
        en = _maybe_timecode_to_seconds(c.get("end", 0.0))
        if en < st:
            en = st
        fmt = c.get("format")
        fmt = str(fmt).strip() if isinstance(fmt, str) else ""
        if not common_format and fmt:
            common_format = fmt
        sub_cues.append(
            {
                "index": int(c.get("index", idx) or idx),
                "start": float(st),
                "end": float(en),
                "text": str(c.get("text", "") or ""),
                "format": fmt,
            }
        )
    sub_cues = _sort_by_start(sub_cues)

    # If no transcript, return cleaned subtitles
    if not transcript_segs:
        out: List[Dict] = []
        for i, c in enumerate(sub_cues, start=1):
            out.append(
                {
                    "index": i,
                    "start": float(_safe_float(c.get("start", 0.0))),
                    "end": float(_safe_float(c.get("end", c.get("start", 0.0)))),
                    "text": str(c.get("text", "") or ""),
                    "format": common_format,
                }
            )
        return out

    # Build output strictly from transcript: one output cue per transcript segment
    # Match each transcript segment to the best subtitle cue for comparison of "timestamps match?" and "text match?"
    # Time-match threshold
    TIME_EPS = 1.0  # seconds

    # Precompute normalized texts for quick compare
    def _norm(s: str) -> str:
        return _normalize_text(s or "")

    # For each transcript segment, find closest subtitle cue by time overlap
    def _time_overlap(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
        lo = max(a_start, b_start)
        hi = min(a_end, b_end)
        return max(0.0, hi - lo)

    used_subs = set()
    aligned_output: List[Dict] = []
    # Keep original format for output (if none in inputs, keep "")
    out_format = common_format

    for i, seg in enumerate(transcript_segs, start=1):
        seg_text = str(seg.get("text", "") or "")
        seg_s = float(_safe_float(seg.get("start", 0.0)))
        seg_e = float(_safe_float(seg.get("end", seg_s)))

        # Find best overlapping subtitle cue
        best_idx = -1
        best_overlap = -1.0
        for j, sc in enumerate(sub_cues):
            if j in used_subs:
                continue
            s_s = float(_safe_float(sc.get("start", 0.0)))
            s_e = float(_safe_float(sc.get("end", s_s)))
            ov = _time_overlap(seg_s, seg_e, s_s, s_e)
            if ov > best_overlap:
                best_overlap = ov
                best_idx = j

        chosen_sub = sub_cues[best_idx] if best_idx >= 0 else None
        # Apply rules:
        if chosen_sub:
            used_subs.add(best_idx)
            s_text = str(chosen_sub.get("text", "") or "")
            # Text match (normalized)
            text_matches = _norm(s_text) == _norm(seg_text)
            # Timestamp match within 1s threshold
            s_s = float(_safe_float(chosen_sub.get("start", 0.0)))
            s_e = float(_safe_float(chosen_sub.get("end", s_s)))
            times_match = (abs(s_s - seg_s) <= TIME_EPS) and (abs(s_e - seg_e) <= TIME_EPS)

            if text_matches and not times_match:
                # Rule 1: use transcript timestamps, keep text (same)
                out_text = s_text  # same as seg_text effectively
                out_start, out_end = seg_s, seg_e
            elif times_match and not text_matches:
                # Rule 2: use transcript text, keep times (times already ~equal to transcript, but to be safe use seg times)
                # The instruction says timestamps match -> use transcript text; we will output transcript's times as well
                # to keep transcript authoritative and consistent.
                out_text = seg_text
                out_start, out_end = seg_s, seg_e
            else:
                # If both match or both differ:
                # - If both match: keep transcript timestamps (authoritative) and keep one text; prefer transcript text.
                # - If both differ: follow transcript as authority for both text and time.
                out_text = seg_text
                out_start, out_end = seg_s, seg_e
        else:
            # No matching subtitle => insertion to match transcript sequence
            out_text = seg_text
            out_start, out_end = seg_s, seg_e

        aligned_output.append(
            {
                "index": i,
                "start": float(out_start),
                "end": float(out_end if out_end >= out_start else out_start),
                "text": out_text,
                "format": out_format,
            }
        )

    # We have matched each transcript segment to one output cue.
    # Any subtitles not used are effectively removed per rule 3 (transcript is authoritative).
    # Ensure monotonic non-overlap and minimal duration hygiene
    aligned_output = _enforce_monotonic_nonoverlap(aligned_output, min_gap=0.0, min_dur=0.0)

    # Reindex final output
    for k, c in enumerate(aligned_output, start=1):
        c["index"] = k
        # Ensure float seconds
        c["start"] = float(_safe_float(c.get("start", 0.0)))
        c["end"] = float(_safe_float(c.get("end", c["start"])))
        if c["end"] < c["start"]:
            c["end"] = c["start"]

    return aligned_output


if __name__ == "__main__":
    # Simple manual demo for quick testing when running this file directly.
    # This demo uses only local heuristics with no external API calls.
    demo_transcript = [
        {"text": "Hello world", "start": 0.0, "end": 1.0},
        {"text": "This is a demo", "start": 1.05, "end": 2.5},
        {"text": "Enjoy!", "start": 2.6, "end": 3.2},
    ]
    demo_subs = [
        {"text": "hello world", "start": 0.4, "end": 1.6},
        {"text": "this is demo", "start": 2.1, "end": 3.5},
    ]
    out = write_corrected_alignment(demo_transcript, demo_subs, language="en")
    print(_compose_srt(out))
