"""
Subtitle generation utilities using a Whisper-like model (stubbed for CI).

This module provides a single public function:
- create_subtitles(video_path, language, file_format)

Behavior:
1) Transcribes the video at video_path using a Whisper (or similar) model.
   In this reference implementation, transcription is deterministic and stubbed.
2) If the detected language differs from the requested language, performs a simple
   placeholder translation of the transcript to the requested target language.
3) Generates subtitles in the requested file format ('srt' or 'vtt').
4) Writes the output to the processed directory and also returns structured cues.

Note:
- In production, replace _transcribe_video_stub and _translate_segments_stub with real
  integrations to OpenAI Whisper or other ASR/translation providers.
- No environment variables are hard-coded; processed_dir is inferred at runtime by
  reading configuration via config.get_settings().
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional
from pathlib import Path
import uuid

from config import get_settings


@dataclass
class TranscriptSegment:
    """Represents a transcribed segment."""
    start: float
    end: float
    text: str


def _format_timestamp_srt(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h = ms // 3_600_000
    ms %= 3_600_000
    m = ms // 60_000
    ms %= 60_000
    s = ms // 1000
    ms %= 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _format_timestamp_vtt(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h = ms // 3_600_000
    ms %= 3_600_000
    m = ms // 60_000
    ms %= 60_000
    s = ms // 1000
    ms %= 1000
    # WebVTT permits hours; we keep hours as two digits as well
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def _format_srt(cues: List[Dict]) -> str:
    """
    Format cues to SRT. Each cue dict:
      { 'index': int, 'start': float, 'end': float, 'text': str | List[str] }
    """
    blocks: List[str] = []
    for i, cue in enumerate(cues, start=1):
        start = _format_timestamp_srt(float(cue["start"]))
        end = _format_timestamp_srt(float(cue["end"]))
        text_val = cue.get("text", "")
        if isinstance(text_val, list):
            text_str = "\n".join([str(t) for t in text_val])
        else:
            text_str = str(text_val)
        blocks.append(f"{i}\n{start} --> {end}\n{text_str}")
    return "\n\n".join(blocks) + "\n"


def _format_vtt(cues: List[Dict]) -> str:
    """
    Format cues to VTT with standard header.
    """
    lines: List[str] = ["WEBVTT", ""]
    for cue in cues:
        start = _format_timestamp_vtt(float(cue["start"]))
        end = _format_timestamp_vtt(float(cue["end"]))
        text_val = cue.get("text", "")
        if isinstance(text_val, list):
            text_str = "\n".join([str(t) for t in text_val])
        else:
            text_str = str(text_val)
        lines.append(f"{start} --> {end}")
        lines.append(text_str)
        lines.append("")  # blank between cues
    return "\n".join(lines).rstrip() + "\n"


def _write_processed(basename: str, content: str) -> str:
    settings = get_settings()
    out = Path(settings.PROCESSED_DIR) / basename
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding="utf-8")
    return str(out)


def _transcribe_video_stub(video_path: str) -> Tuple[str, List[TranscriptSegment]]:
    """
    Stub for ASR transcription. Returns (detected_language, segments).
    The output is deterministic and independent of actual audio for CI stability.
    """
    # Simple two segments transcript
    segments = [
        TranscriptSegment(start=0.0, end=2.0, text="Generated subtitle line 1"),
        TranscriptSegment(start=2.5, end=5.0, text="Generated subtitle line 2"),
    ]
    detected_language = "en"
    return detected_language, segments


def _translate_segments_stub(segments: List[TranscriptSegment], target_lang: str) -> List[TranscriptSegment]:
    """
    Placeholder translation: append [<lang>] to each segment's text.
    """
    out: List[TranscriptSegment] = []
    for seg in segments:
        out.append(TranscriptSegment(start=seg.start, end=seg.end, text=f"{seg.text} [{target_lang}]"))
    return out


def _segments_to_cues(segments: List[TranscriptSegment], lang: str) -> List[Dict]:
    """
    Convert transcript segments to normalized cue dicts used in this project.
    """
    cues: List[Dict] = []
    for idx, seg in enumerate(segments, start=1):
        cues.append({
            "index": idx,
            "start": float(seg.start),
            "end": float(seg.end),
            "text": f"{seg.text} ({lang})",
            "format": "srt",  # base normalized; final formatter decides actual output
            "raw": None,
        })
    return cues


# PUBLIC_INTERFACE
def create_subtitles(video_path: str, language: Optional[str], file_format: str) -> Dict[str, object]:
    """Create subtitles for a given video, returning the output file path and cues.

    PUBLIC_INTERFACE
    Args:
        video_path: Path to the video to transcribe.
        language: Target language code (ISO-639-1). If None, defaults to detected.
        file_format: Output subtitle format. Only 'srt' and 'vtt' are supported.

    Returns:
        Dict with:
            - 'file_path': str absolute path to generated subtitle file
            - 'format': str 'srt' or 'vtt'
            - 'language': str final language of the subtitles
            - 'cues': List[Dict] list of subtitle cues used to build the file

    Raises:
        ValueError: If the requested file_format is not supported.
        FileNotFoundError: If the video path does not exist.
    """
    fmt = (file_format or "").strip().lower()
    if fmt not in ("srt", "vtt"):
        raise ValueError("Unsupported file_format. Only 'srt' and 'vtt' are supported.")
    vp = Path(video_path)
    if not vp.exists():
        raise FileNotFoundError(f"Video not found at path: {video_path}")

    # 1) Transcribe
    detected_lang, segments = _transcribe_video_stub(video_path)

    # 2) Translate if needed
    target_lang = (language or detected_lang).lower()
    if target_lang != detected_lang.lower():
        segments = _translate_segments_stub(segments, target_lang)

    # 3) Build cues
    cues = _segments_to_cues(segments, target_lang)

    # 4) Generate in requested format and write
    unique = uuid.uuid4().hex
    base_name = f"temp_{unique}_generated_{target_lang}.{fmt}"
    if fmt == "srt":
        content = _format_srt(cues)
    else:
        content = _format_vtt(cues)

    file_path = _write_processed(base_name, content)
    return {
        "file_path": file_path,
        "format": fmt,
        "language": target_lang,
        "cues": cues,
    }
