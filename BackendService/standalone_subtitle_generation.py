#!/usr/bin/env python3
"""
Standalone Subtitle Generation Script

This module provides a PUBLIC_INTERFACE function `subtitle_generation(video_path, subtitle_lang, subtitle_format)`
that:
1. Uses OpenAI Whisper to transcribe the input video file and auto-detect its language.
2. If the desired subtitle language differs from the detected language, uses Helsinki-NLP/opus-mt
   via Hugging Face Transformers to translate each segment to the target language.
3. Formats the result into SRT or VTT as specified.
4. Saves the output subtitle file in the same folder as the video, named as "<original_filename>.<srt|vtt>".
5. Can be executed independently as a CLI script for testing:
   - Example:
       python standalone_subtitle_generation.py --video /path/to/video.mp4 --lang en --format srt
   - or import and call:
       from standalone_subtitle_generation import subtitle_generation
       subtitle_path = subtitle_generation("/path/video.mp4", "en", "vtt")

Requirements (ensure these are installed in your environment):
- openai-whisper
- transformers
- torch
- ffmpeg (system dependency, needed by Whisper/ffmpeg-python internally)

Notes:
- This script does NOT depend on FastAPI or any web server code.
- It uses environment-agnostic defaults and does not read a .env file.
"""

import os
import math
import argparse
from typing import List, Tuple, Dict, Optional

# Import Whisper
try:
    import whisper
except Exception as exc:
    raise RuntimeError(
        "Failed to import 'whisper'. Please install with 'pip install openai-whisper' "
        "and ensure ffmpeg is installed on your system."
    ) from exc

# Import Transformers for translation
try:
    from transformers import MarianMTModel, MarianTokenizer, pipeline
except Exception as exc:
    raise RuntimeError(
        "Failed to import 'transformers'. Please install with 'pip install transformers torch'."
    ) from exc


# ----------------------------
# Helper functions
# ----------------------------

def _normalize_lang_code(lang: str) -> str:
    """
    Normalize language code to lowercase ISO-like code (best-effort).
    Whisper returns two-letter codes (e.g., 'en', 'fr'), while opus-mt models
    often use ISO 639-1 and 639-2 codes. We'll keep it lowercase for comparisons.
    """
    return (lang or "").strip().lower()


def _timestamp_to_srt_time(ts_seconds: float) -> str:
    """
    Convert a float seconds timestamp to SRT timestamp format: HH:MM:SS,mmm
    Example: 75.123 -> "00:01:15,123"
    """
    if ts_seconds is None:
        ts_seconds = 0.0
    ts_seconds = max(0.0, float(ts_seconds))
    hours = int(ts_seconds // 3600)
    minutes = int((ts_seconds % 3600) // 60)
    seconds = int(ts_seconds % 60)
    millis = int(round((ts_seconds - math.floor(ts_seconds)) * 1000.0))
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def _timestamp_to_vtt_time(ts_seconds: float) -> str:
    """
    Convert a float seconds timestamp to VTT timestamp format: HH:MM:SS.mmm
    """
    if ts_seconds is None:
        ts_seconds = 0.0
    ts_seconds = max(0.0, float(ts_seconds))
    hours = int(ts_seconds // 3600)
    minutes = int((ts_seconds % 3600) // 60)
    seconds = int(ts_seconds % 60)
    millis = int(round((ts_seconds - math.floor(ts_seconds)) * 1000.0))
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"


def _format_segments_as_srt(segments: List[Dict]) -> str:
    """
    Format Whisper segments to SRT string.
    Each segment dict must contain 'id', 'start', 'end', 'text'
    """
    lines = []
    for idx, seg in enumerate(segments, start=1):
        start = _timestamp_to_srt_time(seg.get("start", 0.0))
        end = _timestamp_to_srt_time(seg.get("end", 0.0))
        text = (seg.get("text") or "").strip()
        lines.append(str(idx))
        lines.append(f"{start} --> {end}")
        lines.append(text)
        lines.append("")  # Blank line after each cue
    return "\n".join(lines).strip() + "\n"


def _format_segments_as_vtt(segments: List[Dict]) -> str:
    """
    Format Whisper segments to VTT string (WebVTT).
    The header "WEBVTT" is required.
    """
    lines = ["WEBVTT", ""]
    for seg in segments:
        start = _timestamp_to_vtt_time(seg.get("start", 0.0))
        end = _timestamp_to_vtt_time(seg.get("end", 0.0))
        text = (seg.get("text") or "").strip()
        lines.append(f"{start} --> {end}")
        lines.append(text)
        lines.append("")  # Blank line after each cue
    return "\n".join(lines).strip() + "\n"


def _select_marian_model_name(src_lang: str, tgt_lang: str) -> Optional[str]:
    """
    Pick a reasonable Helsinki-NLP/opus-mt model name given source and target languages.
    Returns None if cannot determine a direct mapping.
    This is a heuristic mapping for common languages.
    """
    # Common direct pairs; expand as needed.
    pairs = {
        ("en", "de"): "Helsinki-NLP/opus-mt-en-de",
        ("en", "fr"): "Helsinki-NLP/opus-mt-en-fr",
        ("en", "es"): "Helsinki-NLP/opus-mt-en-es",
        ("en", "it"): "Helsinki-NLP/opus-mt-en-it",
        ("en", "pt"): "Helsinki-NLP/opus-mt-en-pt",
        ("en", "ru"): "Helsinki-NLP/opus-mt-en-ru",
        ("en", "zh"): "Helsinki-NLP/opus-mt-en-zh",
        ("de", "en"): "Helsinki-NLP/opus-mt-de-en",
        ("fr", "en"): "Helsinki-NLP/opus-mt-fr-en",
        ("es", "en"): "Helsinki-NLP/opus-mt-es-en",
        ("it", "en"): "Helsinki-NLP/opus-mt-it-en",
        ("pt", "en"): "Helsinki-NLP/opus-mt-pt-en",
        ("ru", "en"): "Helsinki-NLP/opus-mt-ru-en",
        ("zh", "en"): "Helsinki-NLP/opus-mt-zh-en",
        # Some pairs might not exist directly; user may see a model download error if unavailable.
    }
    return pairs.get((src_lang, tgt_lang))


def _get_translation_pipeline(src_lang: str, tgt_lang: str):
    """
    Create a translation pipeline for the given source and target language using MarianMT.
    Attempts a direct pair model first; if not available, tries a generic 'opus-mt-{src}-{tgt}'.
    """
    model_name = _select_marian_model_name(src_lang, tgt_lang)
    # Fallback to the generic naming scheme if direct mapping not found.
    if model_name is None:
        model_name = f"Helsinki-NLP/opus-mt-{src_lang}-{tgt_lang}"
    # Load tokenizer and model
    tokenizer = MarianTokenizer.from_pretrained(model_name)
    model = MarianMTModel.from_pretrained(model_name)
    return pipeline("translation", model=model, tokenizer=tokenizer)


def _translate_segments(segments: List[Dict], src_lang: str, tgt_lang: str) -> List[Dict]:
    """
    Translate each segment's text from src_lang to tgt_lang using MarianMT.
    Returns new list of segments with 'text' replaced by translated text.
    """
    if not segments:
        return segments

    translator = _get_translation_pipeline(src_lang, tgt_lang)
    # Batch process texts for efficiency; pipeline supports list input.
    texts = [(seg.get("text") or "").strip() for seg in segments]
    # Handle empty strings gracefully to maintain alignment
    non_empty_indices = [i for i, t in enumerate(texts) if t]
    non_empty_texts = [texts[i] for i in non_empty_indices]

    translated_texts_map = {}
    if non_empty_texts:
        results = translator(non_empty_texts, max_length=1000)
        # results is a list of dicts with 'translation_text'
        for idx, res in zip(non_empty_indices, results):
            translated_texts_map[idx] = res.get("translation_text", "")

    translated_segments = []
    for i, seg in enumerate(segments):
        new_seg = dict(seg)
        if i in translated_texts_map:
            new_seg["text"] = translated_texts_map[i]
        else:
            # keep as-is (empty or untranslatable)
            new_seg["text"] = (seg.get("text") or "").strip()
        translated_segments.append(new_seg)

    return translated_segments


def _ensure_supported_format(fmt: str) -> str:
    """
    Validate and normalize subtitle format to 'srt' or 'vtt'.
    """
    fmt_norm = (fmt or "").strip().lower()
    if fmt_norm not in {"srt", "vtt"}:
        raise ValueError(f"Unsupported subtitle format '{fmt}'. Use 'srt' or 'vtt'.")
    return fmt_norm


def _determine_output_path(video_path: str, fmt: str) -> str:
    """
    Determine output subtitle path based on input video path and desired format.
    e.g., /folder/video.mp4 + srt -> /folder/video.srt
    """
    base, _ext = os.path.splitext(video_path)
    return f"{base}.{fmt}"


def _transcribe_with_whisper(video_path: str, model_size: str = "small") -> Tuple[List[Dict], str]:
    """
    Run Whisper transcription and return segments and detected language code.
    Returns:
        segments: list of dicts with keys: id, start, end, text
        detected_lang: two-letter lower-case language code detected by Whisper
    """
    model = whisper.load_model(model_size)
    result = model.transcribe(video_path, verbose=False)
    # result keys include 'text', 'segments', 'language' (ISO-639-1 like)
    detected_lang = _normalize_lang_code(result.get("language", ""))
    # Ensure segments have numeric id, start, end, text
    segments = []
    for s in result.get("segments", []):
        segments.append({
            "id": s.get("id"),
            "start": float(s.get("start", 0.0)),
            "end": float(s.get("end", 0.0)),
            "text": (s.get("text") or "").strip(),
        })
    return segments, detected_lang


# PUBLIC_INTERFACE
def subtitle_generation(video_path: str, subtitle_lang: str, subtitle_format: str) -> str:
    """
    Generate subtitles for a video using Whisper and optional translation via Helsinki-NLP/opus-mt.

    Parameters:
    - video_path: Path to the input video file.
    - subtitle_lang: Desired language code (e.g., 'en', 'fr', 'es').
    - subtitle_format: 'srt' or 'vtt'.

    Returns:
    - The path to the generated subtitle file.

    Behavior:
    - Transcribes the video with Whisper, auto-detecting the source language.
    - If subtitle_lang differs from detected language, translates each segment using MarianMT.
    - Formats the segments into the specified subtitle format and writes the file beside the video.
    """
    if not os.path.isfile(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    fmt = _ensure_supported_format(subtitle_format)
    target_lang = _normalize_lang_code(subtitle_lang)
    if not target_lang:
        raise ValueError("subtitle_lang must be a non-empty language code like 'en', 'fr', etc.")

    # Transcribe
    segments, detected_lang = _transcribe_with_whisper(video_path)

    # Translate if needed
    if detected_lang and target_lang and detected_lang != target_lang:
        try:
            segments = _translate_segments(segments, detected_lang, target_lang)
        except Exception as exc:
            raise RuntimeError(
                f"Translation from '{detected_lang}' to '{target_lang}' failed. "
                f"Ensure the appropriate Helsinki-NLP/opus-mt model exists."
            ) from exc

    # Format output
    if fmt == "srt":
        content = _format_segments_as_srt(segments)
    else:
        content = _format_segments_as_vtt(segments)

    out_path = _determine_output_path(video_path, fmt)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)

    return out_path


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Generate subtitles from a video using Whisper and opus-mt.")
    p.add_argument("--video", "-v", required=True, help="Path to the video file.")
    p.add_argument("--lang", "-l", required=True, help="Target language code (e.g., en, fr, es).")
    p.add_argument("--format", "-f", default="srt", choices=["srt", "vtt"], help="Subtitle format.")
    p.add_argument("--model", "-m", default="small", choices=["tiny", "base", "small", "medium", "large"], help="Whisper model size.")
    return p


def _cli_main():
    parser = _build_arg_parser()
    args = parser.parse_args()

    # Allow model override for CLI runs
    # We re-use the public function; for model override, temporarily monkey-patch the transcribe function.
    global _transcribe_with_whisper

    original = _transcribe_with_whisper

    def _transcribe_with_whisper_override(video_path: str, model_size: str = "small"):
        return original(video_path, model_size=args.model)

    _transcribe_with_whisper = _transcribe_with_whisper_override
    try:
        out_path = subtitle_generation(args.video, args.lang, args.format)
        print(f"Subtitle generated: {out_path}")
    finally:
        # Restore original to avoid side effects if imported and used later in same process
        _transcribe_with_whisper = original


if __name__ == "__main__":
    _cli_main()
