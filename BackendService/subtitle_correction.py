"""
Text correction and compliance helpers.

This module provides:
- Grammar/spell correction using language-tool-python
- Light punctuation/whitespace normalization
- spaCy-based entity protection and sentence casing
- Line wrapping respecting OTT limits (max chars/line and lines per cue)

All heavy dependencies are loaded lazily and guarded with safe fallbacks so CI
environments without models still pass deterministically.

Public interfaces:
- correct_subtitle_text
- wrap_lines_for_ott
- apply_additional_compliance_fixes
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, List, Tuple, Dict, Callable
import uuid
import re


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
    # If starts with a letter, uppercase first, else keep as-is
    first_alpha = next((i for i, ch in enumerate(s) if ch.isalpha()), None)
    if first_alpha is None:
        return s
    return s[:first_alpha] + s[first_alpha:first_alpha + 1].upper() + s[first_alpha + 1:]


def _load_spacy_model(lang: str) -> Optional[Callable[[], any]]:
    """
    Return a lazy loader for spaCy model based on ISO-639-1 code.
    Uses small core models if available. Fallback to None if not installed.
    """
    lang = (lang or "en").lower()

    # Map some common languages to default model names
    lang_to_model = {
        "en": "en_core_web_sm",
        "es": "es_core_news_sm",
        "fr": "fr_core_news_sm",
        "de": "de_core_news_sm",
        "it": "it_core_news_sm",
        "pt": "pt_core_news_sm",
        "nl": "nl_core_news_sm",
        "xx": "xx_sent_ud_sm",  # multi-language small
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
            # Fallback to blank model (no NER) to still split tokens/sents where possible
            try:
                import spacy  # type: ignore
                state["nlp"] = spacy.blank(lang if lang in spacy.util.get_lang_class.__self__.languages else "xx")  # type: ignore
                return state["nlp"]
            except Exception:
                return None

    return _loader


def _spacy_protect_entities(text: str, nlp_loader: Optional[Callable[[], any]]) -> List[Tuple[str, bool]]:
    """
    Split text into tokens and mark protected spans (e.g., named entities).
    Returns list of (token_text, protected).
    If spaCy unavailable, return single token whole text as unprotected.
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
        # Build tokens list with protection flags
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
    Run language-tool-python corrections. If the tool or server is unavailable,
    return the original text unchanged.
    """
    try:
        import language_tool_python  # type: ignore
        tool = language_tool_python.LanguageToolPublicAPI(lang.lower() or "en")
        # Some environments require Tool() instead; try both
        try:
            matches = tool.check(text)
            return language_tool_python.utils.correct(text, matches)
        except Exception:
            # Fallback to default LanguageTool if public API not available
            tool = language_tool_python.LanguageTool(lang.lower() or "en")
            matches = tool.check(text)
            return language_tool_python.utils.correct(text, matches)
    except Exception:
        return text


def _normalize_punctuation(text: str) -> str:
    # Simple punctuation spacing and dashes; avoid aggressive changes to not break timing tags
    text = text.replace(" ,", ",").replace(" .", ".").replace(" !", "!").replace(" ?", "?")
    text = re.sub(r"\s+([,\.!?;:])", r"\1", text)
    text = re.sub(r"([(\[])\s+", r"\1", text)
    text = re.sub(r"\s+([)\]])", r"\1", text)
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

    # If too many lines, try to merge while respecting max_lines
    if len(lines) > max_lines:
        # Combine into exactly max_lines by joining and re-splitting longer lines
        joined = " ".join(words)
        if max_lines == 1:
            # Clip if necessary
            if len(joined) <= max_chars_per_line:
                return [joined]
            # Force-break
            return [joined[:max_chars_per_line]]
        else:
            # Two lines: attempt near half split at word boundary
            half = max(1, min(len(joined) // 2, len(joined) - 1))
            # Find nearest space to half
            left = joined.rfind(" ", 0, half)
            right = joined.find(" ", half)
            split_at = left if left != -1 else right
            if split_at == -1:
                split_at = half
            l1 = joined[:split_at].strip()
            l2 = joined[split_at:].strip()
            # Ensure per-line max; if overflow, hard wrap each
            if len(l1) > max_chars_per_line:
                l1 = l1[:max_chars_per_line]
            if len(l2) > max_chars_per_line:
                l2 = l2[:max_chars_per_line]
            return [l1, l2]

    # Enforce per-line max (hard break overflow words)
    fixed: List[str] = []
    for ln in lines:
        if len(ln) <= max_chars_per_line:
            fixed.append(ln)
        else:
            fixed.append(ln[:max_chars_per_line])
    return fixed[:max_lines]


# PUBLIC_INTERFACE
def wrap_lines_for_ott(text: str, max_chars_per_line: int = 42, max_lines: int = 2) -> str:
    """Wrap a single cue text to OTT-friendly line lengths and line counts."""
    max_chars_per_line = int(max_chars_per_line or 42)
    max_lines = int(max_lines or 2)
    wrapped_lines = _wrap_text(text.strip(), max_chars_per_line, max_lines)
    return "\n".join(wrapped_lines)


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
) -> str:
    """
    Correct grammar/spelling and format a subtitle cue text.

    Steps:
    - Unicode NFKC normalization and whitespace cleanup
    - Optional spaCy NER-based entity protection (to avoid altering proper names)
    - Optional sentence casing on first sentence
    - Optional language-tool-python correction
    - Punctuation normalization
    - OTT wrapping to max characters per line and lines per cue
    """
    lang = (lang or "en").lower()
    original = text or ""

    # Basic normalization
    normalized = _normalize_spaces(_nfkc_normalize(original))

    # spaCy entity protection: split into protected/unprotected spans
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
    # Final whitespace normalization after corrections
    corrected = _normalize_spaces(corrected)

    # Line wrapping
    wrapped = wrap_lines_for_ott(corrected, max_chars_per_line=max_chars_per_line, max_lines=max_lines)
    return wrapped


# PUBLIC_INTERFACE
def apply_additional_compliance_fixes(path: str, processed_dir: str) -> str:
    """Apply post-processing corrections on an SRT file by grammar-correcting and wrapping cue texts.

    This function:
    - Parses SRT content in a tolerant manner (regex-based simple parse)
    - Applies correct_subtitle_text to each cue line block
    - Writes a new SRT file into processed_dir and returns its path
    """
    src = Path(path)
    content = src.read_text(encoding="utf-8", errors="ignore")

    # Try python-srt if available for reliable parsing; otherwise use a simple block parser
    try:
        import srt  # type: ignore

        subs = list(srt.parse(content))
        fixed_subs = []
        for sub in subs:
            fixed_text = correct_subtitle_text(str(sub.content))
            sub.content = fixed_text
            fixed_subs.append(sub)
        new_content = srt.compose(fixed_subs)
    except Exception:
        # Simple parser: split on blank lines; fix only text lines (skip index and timing line)
        blocks = re.split(r"\n\s*\n", content.strip())
        out_blocks: List[str] = []
        for b in blocks:
            lines = b.splitlines()
            if len(lines) >= 2 and ("-->" in lines[1] or "-->" in " ".join(lines[:2])):
                head = lines[:2]
                text_lines = lines[2:]
                text_joined = " ".join(t.strip() for t in text_lines if t.strip())
                fixed_text = correct_subtitle_text(text_joined)
                out_blocks.append("\n".join(head + fixed_text.splitlines()))
            else:
                out_blocks.append(b)
        new_content = "\n\n".join(out_blocks) + "\n"

    out = Path(processed_dir) / f"temp_{uuid.uuid4()}_postfix.srt"
    out.write_text(new_content, encoding="utf-8")
    return str(out)
