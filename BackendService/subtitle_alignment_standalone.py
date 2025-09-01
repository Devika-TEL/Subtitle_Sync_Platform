"""
Standalone alignment and correction entry point (no FastAPI dependency).

PUBLIC_INTERFACE:
- write_corrected_alignment(transcript, subtitles, processed_dir=None, language=None) -> str

Inputs:
- transcript: Whisper-like transcript either as:
    * dict with "segments": [{"text","start","end"}, ...]
    * list of {"text","start","end"} dicts (strings will be coerced)
- subtitles: list of dicts, each with keys:
    { index, start, end, text, format }
    Missing values are tolerated and fixed; format is carried through if available.

Behavior:
- Aligns subtitles to transcript using subtitle_alignment_simple.align_subtitles_to_transcript
- Applies light text correction for OTT compliance using subtitle_correction.correct_subtitle_text
- Writes resulting SRT as 'subtitle_alignment_simple.srt' to processed_dir
- Returns absolute path to the written file

This is intentionally decoupled from FastAPI, providing a pure-Python callable.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Any, Optional

from .subtitle_alignment_simple import align_subtitles_to_transcript
from .subtitle_correction import correct_subtitle_text

try:
    # Optional config; fallback to defaults if unavailable
    from .config import get_settings  # type: ignore
except Exception:  # pragma: no cover
    get_settings = None  # type: ignore


def _format_seconds_to_srt(seconds: float) -> str:
    ms = int(round(max(0.0, float(seconds)) * 1000))
    h = ms // 3_600_000
    ms %= 3_600_000
    m = ms // 60_000
    ms %= 60_000
    s = ms // 1000
    ms %= 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _compose_srt(cues: List[Dict]) -> str:
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


def _ensure_processed_dir(processed_dir: Optional[str]) -> Path:
    if processed_dir:
        p = Path(processed_dir)
    else:
        if get_settings is not None:
            try:
                p = Path(get_settings().PROCESSED_DIR)
            except Exception:
                p = Path("./processed")
        else:
            p = Path("./processed")
    p.mkdir(parents=True, exist_ok=True)
    return p


# PUBLIC_INTERFACE
def write_corrected_alignment(
    transcript: Any,
    subtitles: List[Dict],
    *,
    processed_dir: Optional[str] = None,
    language: Optional[str] = None,
) -> str:
    """Create corrected, aligned subtitles and write SRT to processed/subtitle_alignment_simple.srt.

    PUBLIC_INTERFACE
    Args:
        transcript: Whisper-like transcript content. Either:
            - dict with key 'segments' -> list of {'text','start','end'}
            - list of {'text','start','end'} items
            Non-dict items will be coerced to text with zeroed times.
        subtitles: List of subtitle dicts with keys:
            - index: int (optional; will be resequenced)
            - start: float or timecode string
            - end: float or timecode string
            - text: str
            - format: str (propagated to output if provided)
        processed_dir: Optional directory to write output file; defaults to settings.PROCESSED_DIR or ./processed.
        language: Optional language code guiding light text correction.

    Returns:
        str: Absolute path to the written 'subtitle_alignment_simple.srt' file.
    """
    # Align using the robust aligner
    settings = None
    if get_settings is not None:
        try:
            settings = get_settings()
        except Exception:
            settings = None

    aligned_cues = align_subtitles_to_transcript(
        transcript=transcript,
        subtitles=subtitles,
        enable_hybrid=(bool(getattr(settings, "ALIGNMENT_EMBEDDINGS_ENABLED", False)) if settings else False),
        embedding_model_name=(getattr(settings, "ALIGNMENT_MODEL_NAME", None) if settings else None),
        fuzzy_weights=(getattr(settings, "FUZZY_WEIGHTS", None) if settings else None),
        default_chars_per_sec=(getattr(settings, "DEFAULT_CHARS_PER_SEC", None) if settings else None),
        max_cue_duration=(float(getattr(settings, "MAX_CUE_DURATION_MS", 6000)) / 1000.0 if settings else None),
        delayed_start_threshold=(float(getattr(settings, "DELAY_THRESHOLD_MS", 500)) / 1000.0 if settings else None),
    )

    # Light correction on text
    lang = (language or "").strip().lower() or "auto"
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
        final_cues.append(new_cue)

    # Compose and write SRT
    out_dir = _ensure_processed_dir(processed_dir)
    out_path = out_dir / "subtitle_alignment_simple.srt"
    srt_text = _compose_srt(final_cues)
    out_path.write_text(srt_text, encoding="utf-8")
    return str(out_path)
