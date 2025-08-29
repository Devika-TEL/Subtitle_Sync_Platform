"""
Backend subtitle processing orchestrator with language detection, hybrid alignment, and text correction.

This module provides PUBLIC_INTERFACE functions for end-to-end subtitle generation and processing:
- generate_subtitle: Generate subtitles from video (ASR), optional translation, and formatting.
- process_and_align_subtitles: Align an existing subtitle file to an ASR transcript, correct text, and export.

Key pipeline features:
- Language detection via langid (graceful fallback to 'en').
- ASR via whisperx (with CI-safe stub if dependency unavailable).
- Hybrid fuzzy/semantic alignment using subtitle_alignment_simple (RapidFuzz + embeddings when enabled in config).
- Text correction using language-tool-python with spaCy-based entity protection and OTT line wrapping.
- Improved timing with reading-speed-based duration, minimal gap enforcement, delay start snapping.

Notes:
- External models are loaded lazily and guarded. Defaults ensure deterministic behavior in CI without models.
- Environment configuration via config.get_settings() is respected.

Dependencies (requirements.txt already includes):
- langid, whisperx, rapidfuzz, sentence-transformers, language-tool-python, spacy, python-srt
"""

from __future__ import annotations

import os
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .config import get_settings
from .subtitle_alignment_simple import align_subtitles_to_transcript
from .subtitle_correction import correct_subtitle_text, wrap_lines_for_ott


# ---------------------------
# Utilities: language detect
# ---------------------------

def _detect_language(text: str) -> str:
    """
    Detect language using langid. Fallback to 'en' on error.
    """
    try:
        import langid  # type: ignore
        lang, _ = langid.classify(text or "")
        if not isinstance(lang, str) or not lang:
            return "en"
        return lang.lower()
    except Exception:
        return "en"


def _normalize_lang_code(lang: str) -> str:
    return (lang or "").strip().lower()


def _ensure_supported_format(fmt: str) -> str:
    fmt_norm = (fmt or "").strip().lower()
    if fmt_norm not in {"srt", "vtt"}:
        raise ValueError(f"Unsupported subtitle format '{fmt}'. Use 'srt' or 'vtt'.")
    return fmt_norm


def _determine_output_path_with_subtitle_suffix(video_path: str, fmt: str) -> str:
    base, _ext = os.path.splitext(video_path)
    return f"{base}.subtitle.{fmt}"


def _format_ts_srt(seconds: float) -> str:
    ms = int(round(max(0.0, float(seconds)) * 1000))
    h = ms // 3_600_000
    ms %= 3_600_000
    m = ms // 60_000
    ms %= 60_000
    s = ms // 1000
    ms %= 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _format_ts_vtt(seconds: float) -> str:
    ms = int(round(max(0.0, float(seconds)) * 1000))
    h = ms // 3_600_000
    ms %= 3_600_000
    m = ms // 60_000
    ms %= 60_000
    s = ms // 1000
    ms %= 1000
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def _format_segments_as_srt(segments: List[Dict]) -> str:
    lines: List[str] = []
    for i, seg in enumerate(segments, start=1):
        start = _format_ts_srt(float(seg.get("start", 0.0)))
        end = _format_ts_srt(float(seg.get("end", max(0.5, float(seg.get("start", 0.0)) + 0.5))))
        text = (seg.get("text") or "").strip()
        lines.append(str(i))
        lines.append(f"{start} --> {end}")
        lines.append(text)
        lines.append("")  # blank line
    return "\n".join(lines).strip() + "\n"


def _format_segments_as_vtt(segments: List[Dict]) -> str:
    out: List[str] = ["WEBVTT", ""]
    for seg in segments:
        start = _format_ts_vtt(float(seg.get("start", 0.0)))
        end = _format_ts_vtt(float(seg.get("end", max(0.5, float(seg.get("start", 0.0)) + 0.5))))
        text = (seg.get("text") or "").strip()
        out.append(f"{start} --> {end}")
        out.append(text)
        out.append("")
    return "\n".join(out).strip() + "\n"


# ---------------------------
# ASR via whisperx (with stub)
# ---------------------------

def _transcribe_with_whisperx(video_path: str) -> Tuple[List[Dict], str]:
    """
    Transcribe a video using whisperx with suitable defaults.
    Returns:
        segments: List[Dict] with 'start', 'end', 'text'
        detected_lang: Lowercase language code (best effort)
    """
    # Import locally to avoid import-time failures if dependency missing during CI
    try:
        import whisperx  # type: ignore
        import torch  # type: ignore
    except Exception:
        # Stub fallback, deterministic for CI
        segments = [
            {"start": 0.0, "end": 2.0, "text": "Generated subtitle line 1"},
            {"start": 2.5, "end": 5.0, "text": "Generated subtitle line 2"},
        ]
        # Attempt language detection on concatenated stub text
        concat = " ".join(s["text"] for s in segments)
        return segments, _detect_language(concat)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    compute_type = "float16" if device == "cuda" else "float32"

    # Load transcription model
    model = whisperx.load_model("small", device, compute_type=compute_type)
    audio = whisperx.load_audio(video_path)
    asr_result = model.transcribe(audio, batch_size=16)

    detected_lang = _normalize_lang_code(asr_result.get("language", "")) or "en"

    # Load alignment model to get better timings
    try:
        model_a, metadata = whisperx.load_align_model(language_code=detected_lang, device=device)
        aligned_result = whisperx.align(
            asr_result["segments"], model_a, metadata, audio, device, return_char_alignments=False
        )
        segments_raw = aligned_result.get("segments", asr_result.get("segments", []))
    except Exception:
        segments_raw = asr_result.get("segments", [])

    # Normalize segments
    segments: List[Dict] = []
    for s in segments_raw:
        start = float(s.get("start", 0.0))
        end = float(s.get("end", max(start + 0.5, start)))
        text = (s.get("text") or "").strip()
        if text:
            segments.append({"start": start, "end": end, "text": text})

    if not segments:
        full_text = (asr_result.get("text") or "").strip()
        if full_text:
            duration = max(2.0, 0.5 * len(full_text.split()))
            segments = [{"start": 0.0, "end": duration, "text": full_text}]
        else:
            segments = [{"start": 0.0, "end": 2.0, "text": ""}]

    # If whisper didn't detect language, detect from text
    if not detected_lang or detected_lang == "xx":
        concat = " ".join(s["text"] for s in segments)
        detected_lang = _detect_language(concat)

    return segments, detected_lang


# ---------------------------
# Translation (local M2M100)
# ---------------------------

def _translate_segments_with_m2m100_local(
    segments: List[Dict],
    source_lang: str,
    target_lang: str,
) -> List[Dict]:
    """
    Translate text of segments using a locally available M2M100 model directory.
    The directory is read from the environment variable LOCAL_M2M100_DIR.

    Fallback: append [<lang>] for deterministic CI behavior.
    """
    model_dir = os.getenv("LOCAL_M2M100_DIR", "").strip()
    if not model_dir:
        return [
            {**seg, "text": f"{(seg.get('text') or '').strip()} [{target_lang}]"}
            for seg in segments
        ]

    try:
        from transformers import M2M100ForConditionalGeneration, M2M100Tokenizer  # type: ignore

        tokenizer = M2M100Tokenizer.from_pretrained(model_dir)
        model = M2M100ForConditionalGeneration.from_pretrained(model_dir)

        tokenizer.src_lang = source_lang
        tgt_lang = target_lang

        translated_segments: List[Dict] = []
        for seg in segments:
            text = (seg.get("text") or "").strip()
            if not text:
                translated_segments.append({**seg})
                continue
            encoded = tokenizer(text, return_tensors="pt")
            generated_tokens = model.generate(
                **encoded,
                forced_bos_token_id=tokenizer.get_lang_id(tgt_lang),
                max_length=512,
                num_beams=4,
            )
            out_text = tokenizer.batch_decode(generated_tokens, skip_special_tokens=True)[0].strip()
            translated_segments.append({**seg, "text": out_text})
        return translated_segments
    except Exception:
        return [
            {**seg, "text": f"{(seg.get('text') or '').strip()} [{target_lang}]"}
            for seg in segments
        ]


def _segments_to_subtitle_cues(segments: List[Dict], fmt: str) -> List[Dict]:
    """
    Convert ASR segments into a generic 'cues' list used by aligner/corrector:
    Each cue: { index, start, end, text, format }
    """
    cues: List[Dict] = []
    for i, s in enumerate(segments, 1):
        cues.append({
            "index": i,
            "start": float(s.get("start", 0.0)),
            "end": float(s.get("end", float(s.get("start", 0.0)) + 0.5))),
            "text": (s.get("text") or "").strip(),
            "format": fmt,
        })
    return cues


def _compose_from_cues(cues: List[Dict], fmt: str) -> str:
    """
    Compose SRT or VTT content from cues list.
    """
    if fmt == "srt":
        return _format_segments_as_srt(cues)
    return _format_segments_as_vtt(cues)


# PUBLIC_INTERFACE
def generate_subtitle(video_path: str, subtitle_lang: str, format: str) -> str:
    """Generate a subtitle file for a video.

    PUBLIC_INTERFACE
    Args:
        video_path: Path to the input video file.
        subtitle_lang: Target language code (e.g., 'en', 'fr', 'es'). If empty, auto-detect from ASR.
        format: Output subtitle format. Either 'srt' or 'vtt'.

    Returns:
        The path to the generated subtitle file saved next to the video, named "<video_base>.subtitle.<ext>".

    Raises:
        FileNotFoundError, ValueError, RuntimeError
    """
    vp = Path(video_path)
    if not vp.exists() or not vp.is_file():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    target_lang = _normalize_lang_code(subtitle_lang)
    fmt = _ensure_supported_format(format)

    # 1) Transcribe with whisperx + language detection
    segments, detected_lang = _transcribe_with_whisperx(str(vp))
    if not target_lang:
        target_lang = detected_lang or "en"

    # 2) Optional MT if target differs
    if detected_lang and target_lang and detected_lang != target_lang:
        segments = _translate_segments_with_m2m100_local(
            segments=segments, source_lang=detected_lang, target_lang=target_lang
        )

    # 3) Build transcript and initial cues
    transcript = [{"text": s["text"], "start": s["start"], "end": s["end"]} for s in segments]
    cues = _segments_to_subtitle_cues(segments, fmt=fmt)

    # 4) Alignment with improved timing
    settings = get_settings()
    aligned_cues = align_subtitles_to_transcript(
        transcript=transcript,
        subtitles=cues,
        enable_hybrid=settings.ALIGNMENT_EMBEDDINGS_ENABLED,
        embedding_model_name=settings.ALIGNMENT_MODEL_NAME,
        fuzzy_weights=settings.FUZZY_WEIGHTS,
        default_chars_per_sec=settings.DEFAULT_CHARS_PER_SEC,
        max_cue_duration=float(settings.MAX_CUE_DURATION_MS) / 1000.0,
        delayed_start_threshold=float(settings.DELAY_THRESHOLD_MS) / 1000.0,
    )

    # 5) Text correction and wrapping per cue
    final_cues: List[Dict] = []
    for cue in aligned_cues:
        fixed_text = correct_subtitle_text(
            text=cue.get("text", ""),
            lang=target_lang or "en",
            protect_entities=True,
            sentence_case=True,
            use_language_tool=True,
            max_chars_per_line=42,
            max_lines=2,
        )
        new_cue = dict(cue)
        new_cue["text"] = fixed_text
        final_cues.append(new_cue)

    # 6) Compose and write output
    content = _compose_from_cues(final_cues, fmt)
    out_path = _determine_output_path_with_subtitle_suffix(str(vp), fmt)
    Path(out_path).write_text(content, encoding="utf-8")
    return out_path


# PUBLIC_INTERFACE
def process_and_align_subtitles(
    video_path: str,
    existing_subtitle_cues: List[Dict],
    output_format: str = "srt",
    language_hint: Optional[str] = None,
) -> str:
    """Align an existing set of subtitle cues to an ASR transcript from the video, correct text, and export.

    Args:
        video_path: Path to the video file for ASR transcript reference.
        existing_subtitle_cues: List of cues (dicts) with keys: index, start, end, text, format.
        output_format: 'srt' or 'vtt'.
        language_hint: Optional language code; if absent, language detected from cues/transcript.

    Returns:
        Path to the written subtitle file next to the video with ".subtitle.<ext>" naming.
    """
    fmt = _ensure_supported_format(output_format)
    vp = Path(video_path)
    if not vp.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    # 1) Transcript
    transcript_segments, asr_lang = _transcribe_with_whisperx(str(vp))

    # 2) Language
    concat_text = " ".join([c.get("text", "") for c in existing_subtitle_cues]) + " " + " ".join(
        s.get("text", "") for s in transcript_segments
    )
    detected_lang = _normalize_lang_code(language_hint) or _detect_language(concat_text) or asr_lang or "en"

    # 3) Align
    transcript = [{"text": s["text"], "start": s["start"], "end": s["end"]} for s in transcript_segments]
    settings = get_settings()
    aligned_cues = align_subtitles_to_transcript(
        transcript=transcript,
        subtitles=existing_subtitle_cues,
        enable_hybrid=settings.ALIGNMENT_EMBEDDINGS_ENABLED,
        embedding_model_name=settings.ALIGNMENT_MODEL_NAME,
        fuzzy_weights=settings.FUZZY_WEIGHTS,
        default_chars_per_sec=settings.DEFAULT_CHARS_PER_SEC,
        max_cue_duration=float(settings.MAX_CUE_DURATION_MS) / 1000.0,
        delayed_start_threshold=float(settings.DELAY_THRESHOLD_MS) / 1000.0,
    )

    # 4) Correction
    final_cues: List[Dict] = []
    for cue in aligned_cues:
        fixed_text = correct_subtitle_text(
            text=cue.get("text", ""),
            lang=detected_lang,
            protect_entities=True,
            sentence_case=True,
            use_language_tool=True,
            max_chars_per_line=42,
            max_lines=2,
        )
        new_cue = dict(cue)
        new_cue["text"] = fixed_text
        final_cues.append(new_cue)

    # 5) Compose and write
    content = _compose_from_cues(final_cues, fmt)
    out_path = _determine_output_path_with_subtitle_suffix(str(vp), fmt)
    Path(out_path).write_text(content, encoding="utf-8")
    return out_path
