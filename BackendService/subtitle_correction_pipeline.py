"""
subtitle_correction_pipeline.py

Centralized module for applying a comprehensive subtitle correction pipeline.

This module consolidates:
- Traditional text corrections (spell check, basic grammar improvements).
- OTT compliance checks (line length, line count, reading speed heuristics).
- Optional audio-aware correction using automatic speech recognition (ASR) to
  harmonize misheard words by aligning subtitle text to spoken audio.

The public API accepts a list of subtitle cue dictionaries (index, start, end, text, format)
and returns a corrected list with the same structure.

Dependencies (imported but not installed here):
- textstat (optional; for reading speed/complexity heuristics)
- language_tool_python (optional; for grammar/style suggestions)
- pyphen (optional; for syllable-based estimations if needed)
- rapidfuzz (optional; for string similarity when reconciling ASR text with subtitle text)
- whisper or faster-whisper or any other ASR library (optional; for audio-aware correction)
- pydub/moviepy (optional; for audio extraction from video)

ENVIRONMENT VARIABLES (not read directly here, but recommended to configure the application):
- ASR_MODEL_NAME: The ASR model name (e.g., "base", "small", "medium", or a local path)
- ASR_DEVICE: Preferred device for inference (e.g., "cpu", "cuda")
- LANGUAGE_TOOL_HOST/LANGUAGE_TOOL_PORT: Optional self-hosted LanguageTool settings
- DEFAULT_SUBTITLE_LANG: Two-letter language code for rules selection (e.g., "en")

NOTE: This module does not install dependencies, read files, or manage the .env directly.
      The hosting application should provide configured dependencies and pass inputs.

Author: BackendService
"""

from typing import List, Dict, Optional, Tuple
import logging
import re

# Optional imports guarded within try/except so module remains importable even if not installed.
try:
    import language_tool_python  # Grammar/style rules
except Exception:  # pragma: no cover - optional
    language_tool_python = None

try:
    from rapidfuzz import fuzz  # String similarity
except Exception:  # pragma: no cover - optional
    fuzz = None

try:
    import textstat  # Reading speed and complexity heuristics
except Exception:  # pragma: no cover - optional
    textstat = None

# Optional ASR libraries: choose whichever is available in the environment.
# You can integrate with 'whisper' or 'faster_whisper', or another ASR provider.
try:
    import whisper  # openai/whisper
except Exception:  # pragma: no cover - optional
    whisper = None

try:
    from faster_whisper import WhisperModel  # faster-whisper
except Exception:  # pragma: no cover - optional
    WhisperModel = None


logger = logging.getLogger(__name__)


# PUBLIC_INTERFACE
def correct_subtitles_pipeline(
    cues: List[Dict],
    *,
    language: str = "en",
    enable_grammar: bool = True,
    enable_ott_rules: bool = True,
    enable_audio_correction: bool = False,
    audio_source: Optional[str] = None,
    asr_model_name: Optional[str] = None,
    asr_device: Optional[str] = None,
) -> List[Dict]:
    """
    Central entrypoint to run the full subtitle correction pipeline.

    Parameters:
    - cues: List[Dict]
        Each dict represents a subtitle cue with keys:
          - index: int
          - start: str (e.g., "00:00:01,000")
          - end: str (e.g., "00:00:04,000")
          - text: str
          - format: str (e.g., "srt", "vtt")
    - language: str
        ISO language code (e.g., "en") for rule selection. Defaults to "en".
    - enable_grammar: bool
        If True, applies grammar/spell/style improvements.
    - enable_ott_rules: bool
        If True, applies OTT compliance rules (line length, count, reading speed heuristics).
    - enable_audio_correction: bool
        If True and ASR is available, runs audio-aware word-level harmonization
        by comparing the audio transcript to the subtitle text.
    - audio_source: Optional[str]
        Path to the audio file (wav/mp3) or video file. If None but audio correction
        is enabled, the caller must ensure the ASR mechanism knows how to access audio.
        This module does not extract audio automatically for safety; do it upstream or
        pass a path here that ASR can process directly.
    - asr_model_name: Optional[str]
        ASR model identifier. If None, defaults will be chosen by the ASR backend.
    - asr_device: Optional[str]
        Preferred device for inference (e.g., "cpu", "cuda") if the backend supports it.

    Returns:
    - List[Dict]: corrected cues with the same structure as input.

    Pipeline:
    1) Normalize whitespace/punctuation.
    2) Grammar/spell/style correction (optional).
    3) OTT compliance adjustments: line breaking rules, max lines per cue, character
       limits per line, and naive reading speed heuristics (optional).
    4) Audio-aware correction: run ASR over the audio and reconcile with subtitle text
       via fuzzy matching to harmonize misheard words (optional).
    5) Return the corrected cues.

    Notes:
    - This is a best-effort pipeline; if any optional dependency is missing, that
      step is skipped and a debug log is emitted. The function remains safe to call.
    - OTT compliance rules here are heuristic baselines and may be adapted to the
      organization’s standards.
    """
    if not isinstance(cues, list):
        raise ValueError("cues must be a list of subtitle cue dictionaries")

    # Defensive copy to avoid mutating the caller's list
    working = [dict(c) for c in cues]

    # 1) Basic normalization
    for c in working:
        c["text"] = _normalize_text(c.get("text", ""))

    # 2) Grammar/Spell
    if enable_grammar:
        _apply_grammar_and_spell_corrections(working, language=language)

    # 3) OTT rules
    if enable_ott_rules:
        _apply_ott_compliance_rules(working, language=language)

    # 4) Audio-aware correction
    if enable_audio_correction:
        try:
            _apply_audio_aware_corrections(
                working,
                audio_source=audio_source,
                language=language,
                asr_model_name=asr_model_name,
                asr_device=asr_device,
            )
        except Exception as asr_err:  # pragma: no cover - robustness
            logger.warning("Audio-aware correction failed or is unavailable: %s", asr_err)

    return working


# ------------------------
# Helpers: Text Normalization
# ------------------------

def _normalize_text(text: str) -> str:
    """
    Normalize whitespace, trim extra spaces, and standardize punctuation spacing.
    Avoid altering content semantics.
    """
    if not text:
        return ""

    # Replace multiple spaces/tabs with a single space
    t = re.sub(r"[ \t]+", " ", text)

    # Normalize spaces around punctuation (simple heuristics)
    t = re.sub(r"\s+([,.!?;:])", r"\1", t)      # remove space before punctuation
    t = re.sub(r"([,.!?;:])([^\s])", r"\1 \2", t)  # ensure space after punctuation if followed by non-space

    # Normalize common quote characters
    t = t.replace("“", "\"").replace("”", "\"").replace("’", "'").replace("‘", "'")

    # Trim
    return t.strip()


# ------------------------
# Helpers: Grammar and Spell Correction
# ------------------------

def _apply_grammar_and_spell_corrections(cues: List[Dict], language: str = "en") -> None:
    """
    Applies grammar/spell corrections to each cue using language_tool_python when available.
    This function mutates the cues in-place.
    """
    if language_tool_python is None:
        logger.debug("language_tool_python not available; skipping grammar/spell corrections.")
        return

    try:
        # If a self-hosted LanguageTool server is configured, it can be used by specifying host/port
        tool = language_tool_python.LanguageToolPublicAPI(language)  # Lightweight public API client if allowed
    except Exception:
        try:
            tool = language_tool_python.LanguageTool(language)
        except Exception as e:  # pragma: no cover - optional path
            logger.debug("Could not initialize LanguageTool: %s", e)
            return

    for c in cues:
        text_before = c.get("text", "")
        if not text_before.strip():
            continue
        try:
            corrected = tool.correct(text_before)
            # Avoid excessive changes: if the correction is wildly different, use a conservative approach.
            if _is_change_reasonable(text_before, corrected):
                c["text"] = corrected.strip()
        except Exception as e:  # pragma: no cover - robustness
            logger.debug("Grammar correction failed for cue %s: %s", c.get("index"), e)


def _is_change_reasonable(original: str, corrected: str) -> bool:
    """
    Compare original vs corrected to ensure changes are not extreme.
    Uses rapidfuzz if available; falls back to ratio of lengths and simple equality.
    """
    if not original and not corrected:
        return True
    if original == corrected:
        return True

    if fuzz is not None:
        try:
            ratio = fuzz.token_sort_ratio(original, corrected)
            return ratio >= 70  # heuristic threshold
        except Exception:
            pass

    # Fallback heuristic: length difference under 30%
    if not original:
        return False
    len_ok = abs(len(corrected) - len(original)) / max(len(original), 1) <= 0.3
    return len_ok


# ------------------------
# Helpers: OTT Compliance
# ------------------------

def _apply_ott_compliance_rules(
    cues: List[Dict],
    *,
    language: str = "en",
    max_lines_per_cue: int = 2,
    max_chars_per_line: int = 42,
    enforce_terminal_punctuation: bool = False,
) -> None:
    """
    Applies baseline OTT compliance rules in-place:
    - Limits lines per cue.
    - Enforces character length per line with smart wrapping.
    - Optional terminal punctuation enforcement.
    - Reading speed heuristic (if textstat available): simplistic gating.

    Note: In practice, standards vary by platform and region. Adjust thresholds accordingly.
    """
    for c in cues:
        text = c.get("text", "").strip()
        if not text:
            continue

        # Split into natural lines if present; otherwise treat as single text block.
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if not lines:
            lines = [text]

        # Join into one, then re-wrap respecting max length and max line count
        joined = " ".join(lines)
        wrapped = _wrap_text(joined, max_chars_per_line, max_lines_per_cue)

        # Optionally enforce terminal punctuation (avoid adding punctuation to obvious non-sentences)
        if enforce_terminal_punctuation and not re.search(r"[.!?…]$", wrapped[-1]):
            # Only add period if the last token looks alphabetic (rudimentary)
            if re.search(r"[A-Za-z]$", wrapped[-1]):
                wrapped[-1] = wrapped[-1] + "."

        c["text"] = "\n".join(wrapped)

    # Optional reading speed check; if too dense, attempt further splitting
    if textstat is not None:
        for c in cues:
            c["text"] = _adjust_for_reading_speed(c["text"])


def _wrap_text(text: str, max_chars: int, max_lines: int) -> List[str]:
    """
    Simple greedy wrapper that tries to keep words intact and limit lines/characters.
    """
    words = text.split()
    lines: List[str] = []
    cur: List[str] = []

    for w in words:
        candidate = (" ".join(cur) + (" " if cur else "") + w).strip()
        if len(candidate) <= max_chars:
            cur.append(w)
        else:
            if cur:
                lines.append(" ".join(cur))
                cur = [w]
            else:
                # Single long word: hard break
                lines.append(w[:max_chars])
                w_remainder = w[max_chars:]
                while w_remainder:
                    lines.append(w_remainder[:max_chars])
                    w_remainder = w_remainder[max_chars:]

    if cur:
        lines.append(" ".join(cur))

    # If too many lines, merge last ones greedily
    while len(lines) > max_lines:
        merged = (lines[-2] + " " + lines[-1]).strip()
        lines = lines[:-2] + [merged]

    return lines


def _adjust_for_reading_speed(text: str) -> str:
    """
    Adjusts text for reading speed using simple heuristics when textstat is available.
    - If lines are too long and complex, attempt to re-break lines.

    This is conservative and avoids large semantic changes.
    """
    if textstat is None:
        return text

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return text

    # Heuristic thresholds
    target_max_chars = 42
    improved: List[str] = []
    for ln in lines:
        complexity = 0.0
        try:
            complexity = textstat.char_count(ln, ignore_spaces=True)
        except Exception:
            complexity = len(ln)

        if complexity > target_max_chars:
            # Re-wrap this line into smaller chunks
            chunks = _wrap_text(ln, max_chars=target_max_chars, max_lines=2)
            improved.extend(chunks)
        else:
            improved.append(ln)

    return "\n".join(improved)


# ------------------------
# Helpers: Audio-Aware Correction (ASR)
# ------------------------

def _apply_audio_aware_corrections(
    cues: List[Dict],
    *,
    audio_source: Optional[str],
    language: str = "en",
    asr_model_name: Optional[str] = None,
    asr_device: Optional[str] = None,
) -> None:
    """
    Runs an ASR engine on the provided audio and reconciles cue text with transcribed
    segments using fuzzy-matching. This mutates the cues in-place.

    Requirements:
    - Provide audio_source (path to audio or video).
    - An ASR backend must be available (whisper or faster-whisper preferred).

    Strategy:
    - Transcribe audio to segments with timestamps.
    - For each cue window [start, end], aggregate ASR text overlapping that window.
    - Compare the subtitle text to ASR text; if a high-similarity alternative is found,
      substitute words to harmonize likely misheard tokens (e.g., "lion" -> "line").

    If ASR libraries are not available or audio_source is missing, the function exits gracefully.
    """
    if not audio_source:
        logger.debug("Audio source not provided; skipping audio-aware corrections.")
        return

    segments = _run_asr(audio_source, language=language, model_name=asr_model_name, device=asr_device)
    if not segments:
        logger.debug("ASR produced no segments; skipping audio-aware corrections.")
        return

    # Build simple index of ASR segments to speed up matching per cue
    for c in cues:
        start_s = _timestamp_to_seconds(c.get("start", "00:00:00,000"))
        end_s = _timestamp_to_seconds(c.get("end", "00:00:00,000"))
        cue_asr_text = _collect_asr_text_for_window(segments, start_s, end_s)
        if not cue_asr_text.strip():
            continue

        original_text = c.get("text", "").strip()
        if not original_text:
            continue

        harmonized = _harmonize_text_with_asr(original_text, cue_asr_text)
        if _is_change_reasonable(original_text, harmonized):
            c["text"] = harmonized


def _run_asr(
    audio_source: str,
    *,
    language: str,
    model_name: Optional[str],
    device: Optional[str],
) -> List[Dict]:
    """
    Execute ASR and return a list of segments:
    [
        {"start": float_seconds, "end": float_seconds, "text": "recognized speech"}
    ]

    The function tries faster-whisper first, then whisper. If neither is available,
    returns an empty list without raising errors.
    """
    # Attempt faster-whisper (preferred for performance)
    if WhisperModel is not None:
        try:
            model = WhisperModel(model_name or "base", device=device or "auto")
            segments_out = []
            # Transcribe generator yields Segment(start, end, text)
            for seg in model.transcribe(audio_source, language=language, vad_filter=True, vad_parameters=dict(min_silence_duration_ms=500))[0]:
                segments_out.append({"start": float(seg.start), "end": float(seg.end), "text": seg.text.strip()})
            return segments_out
        except Exception as e:  # pragma: no cover - robustness
            logger.debug("faster-whisper ASR failed: %s", e)

    # Fallback to whisper
    if whisper is not None:
        try:
            model = whisper.load_model(model_name or "base", device=device or None)
            result = model.transcribe(audio_source, language=language, verbose=False)
            segments_out = []
            for seg in result.get("segments", []):
                segments_out.append({
                    "start": float(seg.get("start", 0.0)),
                    "end": float(seg.get("end", 0.0)),
                    "text": str(seg.get("text", "")).strip(),
                })
            return segments_out
        except Exception as e:  # pragma: no cover - robustness
            logger.debug("whisper ASR failed: %s", e)

    logger.debug("No ASR backend available; skipping ASR.")
    return []


def _collect_asr_text_for_window(segments: List[Dict], start: float, end: float) -> str:
    """
    Concatenate ASR text that overlaps with the given [start, end] window.
    """
    collected: List[str] = []
    for seg in segments:
        s, e = seg.get("start", 0.0), seg.get("end", 0.0)
        if _overlaps(start, end, s, e):
            t = seg.get("text", "").strip()
            if t:
                collected.append(t)
    return " ".join(collected)


def _overlaps(a_start: float, a_end: float, b_start: float, b_end: float) -> bool:
    """
    Check if intervals [a_start, a_end] and [b_start, b_end] overlap.
    """
    return not (a_end <= b_start or b_end <= a_start)


def _timestamp_to_seconds(ts: str) -> float:
    """
    Convert SRT-like timestamp "HH:MM:SS,mmm" to seconds as float.
    """
    m = re.match(r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})", ts.strip())
    if not m:
        return 0.0
    h, mi, s, ms = m.groups()
    return int(h) * 3600 + int(mi) * 60 + int(s) + int(ms) / 1000.0


def _harmonize_text_with_asr(sub_text: str, asr_text: str) -> str:
    """
    Attempt to harmonize subtitle text with ASR text using token-level fuzzy matching.
    - Keeps the structure (line breaks) of the subtitle text.
    - Replaces tokens in subtitle text when a close ASR candidate exists.
    """

    # Split subtitle by lines to preserve layout
    sub_lines = sub_text.splitlines()
    asr_tokens = _tokenize(asr_text)

    # If rapidfuzz unavailable, fallback to very conservative replacement using simple equality/near match.
    use_fuzzy = fuzz is not None

    harmonized_lines: List[str] = []
    for ln in sub_lines:
        tokens = _tokenize(ln)
        new_tokens: List[str] = []
        for tok in tokens:
            candidate = tok
            if use_fuzzy and asr_tokens:
                # Find best match in ASR tokens by token_set_ratio
                best_score = -1
                best_token = tok
                for atok in asr_tokens:
                    try:
                        score = fuzz.ratio(tok.lower(), atok.lower())
                    except Exception:  # pragma: no cover
                        score = 0
                    if score > best_score:
                        best_score, best_token = score, atok

                # If best score indicates a likely mismatch (e.g., "lion" vs "line" ~ >85),
                # replace with ASR token to harmonize
                if best_score >= 85 and best_token.lower() != tok.lower():
                    candidate = _match_casing(best_token, tok)
            else:
                # Conservative heuristic without fuzzy:
                # Replace only if exact case-insensitive match found in ASR tokens (rarely helpful, but safe)
                if tok.lower() in {t.lower() for t in asr_tokens}:
                    # Already matches; keep as-is
                    candidate = tok
                # else leave unchanged

            new_tokens.append(candidate)

        harmonized_lines.append(_detokenize(new_tokens))

    return "\n".join(harmonized_lines).strip()


def _tokenize(text: str) -> List[str]:
    """
    Tokenize text into words and punctuation tokens while preserving punctuation as separate tokens.
    """
    # Split on word boundaries but keep punctuation
    return re.findall(r"\w+|[^\w\s]", text, re.UNICODE)


def _detokenize(tokens: List[str]) -> str:
    """
    Rebuild text from tokens with basic spacing rules.
    """
    out = ""
    for i, t in enumerate(tokens):
        if i == 0:
            out += t
            continue
        if re.match(r"[,.!?;:)\]\}]", t):
            # punctuation that should not have a leading space
            out += t
        elif re.match(r"[(\[\{]", t):
            # opening punctuation should have a space before it
            out += " " + t
        else:
            out += " " + t
    # Clean spaces before punctuation just in case
    out = re.sub(r"\s+([,.!?;:])", r"\1", out)
    return out.strip()


def _match_casing(source: str, template: str) -> str:
    """
    Match casing of source string to template string:
    - If template is title case, return source in title case.
    - If template is uppercase, return source in uppercase.
    - If template is lowercase, return source in lowercase.
    Otherwise, return source unchanged.
    """
    if template.isupper():
        return source.upper()
    if template.islower():
        return source.lower()
    if template.istitle():
        # Title-case per word
        return " ".join([w.capitalize() if w else w for w in source.split(" ")])
    return source
