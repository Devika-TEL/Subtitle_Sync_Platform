#!/usr/bin/env python3
"""
Standalone Subtitle Generation Script

This module provides a PUBLIC_INTERFACE function `subtitle_generation(video_path, subtitle_lang, subtitle_format)`
that:
1. Uses OpenAI Whisper to transcribe the input video file and auto-detect its language.
2. If the desired subtitle language differs from the detected language, uses Google Gemini API
   to translate each segment to the target language.
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
- requests
- python-dotenv (optional, for loading GEMINI_API_KEY from .env)
- torch
- ffmpeg (system dependency, needed by Whisper/ffmpeg-python internally)

Notes:
- This script does NOT depend on FastAPI or any web server code.
- It will attempt to read GEMINI_API_KEY from the environment or a .env file (if python-dotenv is installed).
"""

import os
import math
import argparse
from typing import List, Tuple, Dict, Optional

# Try to load environment variables from .env for local development convenience.
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    # dotenv is optional; if not available, environment must provide variables.
    pass

# Import Whisper
try:
    import whisper
except Exception as exc:
    raise RuntimeError(
        "Failed to import 'whisper'. Please install with 'pip install openai-whisper' "
        "and ensure ffmpeg is installed on your system."
    ) from exc

# requests is used to call the Gemini API HTTP endpoint
try:
    import requests
except Exception as exc:
    raise RuntimeError(
        "Failed to import 'requests'. Please install with 'pip install requests'."
    ) from exc


# ----------------------------
# Helper functions
# ----------------------------

def _normalize_lang_code(lang: str) -> str:
    """
    Normalize language code to lowercase ISO-like code (best-effort).
    Whisper returns two-letter codes (e.g., 'en', 'fr').
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


def _determine_output_path(video_path: str, fmt: str) -> str:
    """
    Determine output subtitle path based on input video path and desired format.
    e.g., /folder/video.mp4 + srt -> /folder/video.srt
    """
    base, _ext = os.path.splitext(video_path)
    return f"{base}.{fmt}"


def _ensure_supported_format(fmt: str) -> str:
    """
    Validate and normalize subtitle format to 'srt' or 'vtt'.
    """
    fmt_norm = (fmt or "").strip().lower()
    if fmt_norm not in {"srt", "vtt"}:
        raise ValueError(f"Unsupported subtitle format '{fmt}'. Use 'srt' or 'vtt'.")
    return fmt_norm


def _transcribe_with_whisper(video_path: str, model_size: str = "small") -> Tuple[List[Dict], str]:
    """
    Run Whisper transcription and return segments and detected language code.
    Returns:
        segments: list of dicts with keys: id, start, end, text
        detected_lang: two-letter lower-case language code detected by Whisper
    """
    model = whisper.load_model(model_size)
    result = model.transcribe(video_path, verbose=False)
    detected_lang = _normalize_lang_code(result.get("language", ""))
    segments = []
    for s in result.get("segments", []):
        segments.append({
            "id": s.get("id"),
            "start": float(s.get("start", 0.0)),
            "end": float(s.get("end", 0.0)),
            "text": (s.get("text") or "").strip(),
        })
    return segments, detected_lang


def _get_gemini_api_key() -> Optional[str]:
    """
    Retrieve the Gemini API key from the environment.
    The variable name is GEMINI_API_KEY.
    """
    return os.getenv("GEMINI_API_KEY", "").strip() or None


def _gemini_translate_texts(texts: List[str], source_lang: str, target_lang: str) -> List[str]:
    """
    Translate a list of texts using Google Gemini API via the Generative Language API.
    This implementation uses the 'text' generation endpoint with a clear instruction
    to translate from source_lang to target_lang, preserving meaning and style.

    Environment:
    - Requires GEMINI_API_KEY to be set in the environment or available via .env.

    Raises:
    - RuntimeError with helpful messages if API key is missing or if the API call fails.
    """
    api_key = _get_gemini_api_key()
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Please set it in your environment or in a .env file. "
            "Example .env entry:\nGEMINI_API_KEY=your_api_key_here"
        )

    # Choose a widely available text model; adjust if your environment standardizes differently.
    model = "gemini-1.5-flash"

    # Endpoint for text generation. We instruct the model to translate.
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    headers = {"Content-Type": "application/json"}

    translated: List[str] = []
    for text in texts:
        if not text:
            translated.append("")
            continue

        prompt = (
            f"Translate the following text from {source_lang} to {target_lang}. "
            "Return only the translated text without additional commentary.\n\n"
            f"Text:\n{text}"
        )
        payload = {
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "topP": 0.9,
                "topK": 40,
                "maxOutputTokens": 2048
            }
        }

        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=60)
        except requests.RequestException as req_exc:
            raise RuntimeError(
                "Failed to reach Gemini API. Check your network connection and try again."
            ) from req_exc

        if resp.status_code != 200:
            raise RuntimeError(
                f"Gemini API error (HTTP {resp.status_code}). Response: {resp.text}\n"
                "Please verify that your GEMINI_API_KEY is valid, that the model name is available to your key, "
                "and that your billing/quota allow requests."
            )

        data = {}
        try:
            data = resp.json()
        except Exception as json_exc:
            raise RuntimeError("Failed to parse Gemini API response as JSON.") from json_exc

        try:
            # Response shape: candidates[0].content.parts[0].text
            candidates = data.get("candidates") or []
            if not candidates:
                raise KeyError("No candidates in response")
            first = candidates[0]
            content = first.get("content") or {}
            parts = content.get("parts") or []
            first_text = parts[0].get("text", "") if parts else ""
            translated.append(first_text.strip())
        except Exception as parse_exc:
            raise RuntimeError(
                f"Unexpected Gemini response format. Raw response: {data}"
            ) from parse_exc

    return translated


def _translate_segments_with_gemini(segments: List[Dict], src_lang: str, tgt_lang: str) -> List[Dict]:
    """
    Translate each segment's text from src_lang to tgt_lang using Gemini API.
    Returns a new list of segments with 'text' replaced by translated text.
    """
    if not segments:
        return segments

    texts = [(seg.get("text") or "").strip() for seg in segments]
    # Preserve alignment of empty vs non-empty
    non_empty_indices = [i for i, t in enumerate(texts) if t]
    non_empty_texts = [texts[i] for i in non_empty_indices]

    translated_map: Dict[int, str] = {}
    if non_empty_texts:
        translated_texts = _gemini_translate_texts(non_empty_texts, source_lang=src_lang, target_lang=tgt_lang)
        for idx, t in zip(non_empty_indices, translated_texts):
            translated_map[idx] = t

    out_segments: List[Dict] = []
    for i, seg in enumerate(segments):
        new_seg = dict(seg)
        if i in translated_map:
            new_seg["text"] = translated_map[i]
        else:
            new_seg["text"] = (seg.get("text") or "").strip()
        out_segments.append(new_seg)
    return out_segments


# PUBLIC_INTERFACE
def subtitle_generation(video_path: str, subtitle_lang: str, subtitle_format: str) -> str:
    """
    Generate subtitles for a video using Whisper and Google Gemini API for translation when needed.

    Parameters:
    - video_path: Path to the input video file.
    - subtitle_lang: Desired language code (e.g., 'en', 'fr', 'es').
    - subtitle_format: 'srt' or 'vtt'.

    Returns:
    - The path to the generated subtitle file.

    Behavior:
    - Transcribes the video with Whisper, auto-detecting the source language.
    - If subtitle_lang differs from detected language, translates each segment using Gemini API
      (requires GEMINI_API_KEY to be set).
    - Formats the segments into the specified subtitle format and writes the file beside the video.

    Environment:
    - GEMINI_API_KEY must be set in the environment or provided via a .env file in development.
      Example .env:
        GEMINI_API_KEY=your_api_key_here
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
            segments = _translate_segments_with_gemini(segments, detected_lang, target_lang)
        except RuntimeError as api_exc:
            # Provide a helpful error message focused on missing key or API failure.
            raise RuntimeError(
                f"Translation from '{detected_lang}' to '{target_lang}' failed via Gemini API. "
                "Please ensure GEMINI_API_KEY is set (e.g., in a .env file) and that your key has access. "
                f"Details: {api_exc}"
            ) from api_exc
        except Exception as exc:
            # Unexpected exception path
            raise RuntimeError(
                f"An unexpected error occurred during translation: {exc}"
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
    p = argparse.ArgumentParser(description="Generate subtitles from a video using Whisper and Gemini translation (if needed).")
    p.add_argument("--video", "-v", required=True, help="Path to the video file.")
    p.add_argument("--lang", "-l", required=True, help="Target language code (e.g., en, fr, es).")
    p.add_argument("--format", "-f", default="srt", choices=["srt", "vtt"], help="Subtitle format.")
    p.add_argument("--model", "-m", default="small", choices=["tiny", "base", "small", "medium", "large"], help="Whisper model size.")
    return p


def _cli_main():
    parser = _build_arg_parser()
    args = parser.parse_args()

    # Allow model override for CLI runs
    global _transcribe_with_whisper

    original = _transcribe_with_whisper

    def _transcribe_with_whisper_override(video_path: str, model_size: str = "small"):
        return original(video_path, model_size=args.model)

    _transcribe_with_whisper = _transcribe_with_whisper_override
    try:
        out_path = subtitle_generation(args.video, args.lang, args.format)
        print("Subtitle generated:", out_path)
    finally:
        _transcribe_with_whisper = original


if __name__ == "__main__":
    _cli_main()
