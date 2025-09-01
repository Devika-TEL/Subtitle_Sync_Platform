"""
Endpoint helpers for transcript-driven subtitle alignment and correction.

This module adds a PUBLIC_INTERFACE function and helpers for:
- Parsing SRT files into generic cues [{index, start, end, text, format}]
- Formatting cues back to SRT
- An orchestrator function that accepts a transcript (JSON structure or plain text) and a subtitle file (SRT),
  aligns and corrects them using the existing aligner, and writes an output file within processed directory
  named "subtitle_alignment_simple.srt" for easy standalone testing.

It is decoupled from FastAPI so it can be imported and tested programmatically.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Tuple, Any, Union, Optional
import re
import json

from .config import get_settings
from .subtitle_alignment_simple import align_subtitles_to_transcript
from .subtitle_correction import correct_subtitle_text


_TIME_RE = re.compile(
    r"(?P<h>\d{2}):(?P<m>\d{2}):(?P<s>\d{2})[,.](?P<ms>\d{3})"
)

def _parse_ts_to_seconds(ts: str) -> float:
    m = _TIME_RE.match(ts.strip())
    if not m:
        return 0.0
    h = int(m.group("h"))
    mi = int(m.group("m"))
    s = int(m.group("s"))
    ms = int(m.group("ms"))
    return h * 3600 + mi * 60 + s + ms / 1000.0

def _format_seconds_to_srt(seconds: float) -> str:
    ms = int(round(max(0.0, float(seconds)) * 1000))
    h = ms // 3_600_000
    ms %= 3_600_000
    m = ms // 60_000
    ms %= 60_000
    s = ms // 1000
    ms %= 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def _parse_srt(content: str) -> List[Dict]:
    """
    Parse SRT content into generic cues list.

    Returns:
        List of dicts: { index, start, end, text, format: 'srt' }
    """
    # Normalize newlines
    text = content.replace("\r\n", "\n").replace("\r", "\n")
    blocks = re.split(r"\n\s*\n", text.strip())
    cues: List[Dict] = []
    for block in blocks:
        lines = block.splitlines()
        if not lines:
            continue
        # Optional index on first line
        idx_line = lines[0].strip()
        cur = 1
        try:
            idx = int(idx_line)
            # Next should be time line
        except Exception:
            idx = len(cues) + 1
            cur = 0
        # Find timing line
        if cur >= len(lines):
            continue
        timing_line = lines[cur].strip()
        cur += 1
        if "-->" not in timing_line:
            # Not valid SRT block
            continue
        parts = [p.strip() for p in timing_line.split("-->")]
        if len(parts) != 2:
            continue
        start = _parse_ts_to_seconds(parts[0])
        end = _parse_ts_to_seconds(parts[1])
        if end < start:
            end = start
        # Remaining lines are text (preserve as-is)
        text_lines = lines[cur:] if cur < len(lines) else []
        text_join = "\n".join([t for t in text_lines]).strip()
        cues.append({
            "index": idx,
            "start": float(start),
            "end": float(end),
            "text": text_join,
            "format": "srt",
        })
    # Reindex sequentially
    for i, c in enumerate(cues, start=1):
        c["index"] = i
    return cues

def _compose_srt(cues: List[Dict]) -> str:
    """
    Compose SRT text from generic cues.
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

def _normalize_transcript_input(transcript_content: str) -> List[Dict]:
    """
    Accepts either:
      - JSON string of whisper-like dict {"segments": [{"text","start","end"}, ...]} or a list of segments
      - Plain text: split into naive segments with guessed duration based on sentence boundaries.

    Returns:
        List[Dict] with keys: text, start, end
    """
    # Try JSON first
    try:
        parsed = json.loads(transcript_content)
        if isinstance(parsed, dict) and isinstance(parsed.get("segments"), list):
            segs_in = parsed["segments"]
        elif isinstance(parsed, list):
            segs_in = parsed
        else:
            segs_in = []
        segments: List[Dict] = []
        for s in segs_in:
            if not isinstance(s, dict):
                continue
            txt = str(s.get("text", "") or "")
            st = s.get("start", 0.0)
            en = s.get("end", 0.0)
            # Allow possible timecode strings
            if isinstance(st, str):
                st = _parse_ts_to_seconds(st)
            if isinstance(en, str):
                en = _parse_ts_to_seconds(en)
            st = float(st or 0.0)
            en = float(en or st)
            if en < st:
                en = st
            segments.append({"text": txt, "start": st, "end": en})
        if segments:
            return segments
    except Exception:
        pass

    # Fallback: plain-text transcript. Split on sentence boundaries and spread over time heuristically.
    raw = (transcript_content or "").strip()
    if not raw:
        return []
    # Very naive sentence split
    parts = re.split(r"(?<=[.!?])\s+", raw)
    segments: List[Dict] = []
    cur = 0.0
    for p in parts:
        txt = p.strip()
        if not txt:
            continue
        # heuristic: 15 chars/s -> duration
        dur = max(0.6, len(txt) / 15.0)
        segments.append({"text": txt, "start": cur, "end": cur + dur})
        cur += dur + 0.1
    return segments

# PUBLIC_INTERFACE
def align_and_correct_from_files(
    *,
    transcript_content: str,
    subtitle_path: str,
    language: Optional[str] = None,
    processed_dir: Optional[str] = None,
) -> str:
    """Align and correct a subtitle file using a provided transcript content.

    PUBLIC_INTERFACE
    Args:
        transcript_content: The transcript in JSON (preferred) or plain text form. JSON can be
                            a Whisper-like dict with "segments" or a list of {text,start,end}.
        subtitle_path: Path to the subtitle file (SRT). Other formats may be supported later.
        language: Optional language code; used for text correction.
        processed_dir: Directory to write the output "subtitle_alignment_simple.srt".
                       If None, uses settings.PROCESSED_DIR.

    Returns:
        The absolute path to the written file named "subtitle_alignment_simple.srt" in processed_dir.
    """
    settings = get_settings()
    out_dir = Path(processed_dir or settings.PROCESSED_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Read SRT and parse cues
    content = Path(subtitle_path).read_text(encoding="utf-8", errors="ignore")
    cues = _parse_srt(content)

    # Normalize transcript
    transcript_segments = _normalize_transcript_input(transcript_content)

    # Align
    aligned_cues = align_subtitles_to_transcript(
        transcript=transcript_segments,
        subtitles=cues,
        enable_hybrid=settings.ALIGNMENT_EMBEDDINGS_ENABLED,
        embedding_model_name=settings.ALIGNMENT_MODEL_NAME,
        fuzzy_weights=settings.FUZZY_WEIGHTS,
        default_chars_per_sec=settings.DEFAULT_CHARS_PER_SEC,
        max_cue_duration=float(settings.MAX_CUE_DURATION_MS) / 1000.0,
        delayed_start_threshold=float(settings.DELAY_THRESHOLD_MS) / 1000.0,
    )

    # Correct text lines minimally to fix typos/spacing, preserving language-agnostic approach
    lang = (language or "").strip().lower() or "auto"
    final_cues: List[Dict] = []
    for cue in aligned_cues:
        fixed = correct_subtitle_text(
            text=cue.get("text", ""),
            lang=lang if lang != "auto" else None,
            protect_entities=True,
            sentence_case=False,  # avoid aggressive casing that could break some languages
            use_language_tool=True,
            max_chars_per_line=42,
            max_lines=2,
        )
        new_cue = dict(cue)
        new_cue["text"] = fixed
        final_cues.append(new_cue)

    # Compose SRT and write output
    srt_out = _compose_srt(final_cues)
    out_path = out_dir / "subtitle_alignment_simple.srt"
    out_path.write_text(srt_out, encoding="utf-8")
    return str(out_path)
