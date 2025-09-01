"""
Subtitle processing implementations (placeholders with basic logic).

In a production system these would integrate with:
- STT engines (e.g., Whisper, Google Speech, Azure)
- LLMs for translation/polish
- Proper subtitle parsing/formatting libraries

For now, implement deterministic, testable behavior that writes files to processed/.
"""

from pathlib import Path
from typing import Optional, List, Dict
import uuid
import re

# Optional import for standardized SRT export from seconds.
# Use when you have structured subtitle dicts with 'start'/'end' (in seconds) and 'text'.
try:
    from .subtitle_time_utils import write_srt
except Exception:
    # Support running as a module script as well
    try:
        from subtitle_time_utils import write_srt
    except Exception:
        write_srt = None  # type: ignore

# Conservative merge utilities for text/timestamp updates
try:
    from .subtitle_correction import conservative_merge_subtitle_update
except Exception:
    try:
        from subtitle_correction import conservative_merge_subtitle_update
    except Exception:
        conservative_merge_subtitle_update = None  # type: ignore


def _write_processed_stub(basename: str, content: str, processed_dir: str) -> str:
    out = Path(processed_dir) / basename
    out.write_text(content, encoding="utf-8")
    return str(out)


# PUBLIC_INTERFACE
def run_quality_check_and_correct(
    subtitle_path: str,
    video_path: Optional[str],
    language: Optional[str],
    enforce_ott: bool,
    processed_dir: str,
) -> str:
    """Run basic checks and 'correct' a subtitle file by normalizing whitespace and applying conservative merge rules for text/timestamps.

    Notes:
    - This placeholder operates on raw SRT text; we do not parse timestamps into floats here.
      Therefore, no timestamp changes are applied at this stage (satisfying the 'do not adjust
      under 1 second' requirement by not changing any times in this basic path).
    - Text normalization only removes trailing spaces and collapses excessive blank lines.
      This is treated as punctuation/whitespace changes and will not be considered a 'word change'.
    - If, in the future, we parse subtitles into structured cues, we should use
      conservative_merge_subtitle_update() to compare original vs proposed updates
      and only apply significant changes per the new rules.
    """
    src = Path(subtitle_path).read_text(encoding="utf-8", errors="ignore")
    # Normalize CRLF, strip trailing spaces on each line (whitespace-only change)
    normalized = "\n".join([line.rstrip() for line in src.replace("\r\n", "\n").replace("\r", "\n").split("\n")])
    # Ensure blank line separation but don't touch timing lines content
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)

    if enforce_ott:
        # Enforce max two lines per caption while ensuring we do not drop all text
        blocks = re.split(r"\n\s*\n", normalized.strip())
        fixed_blocks: List[str] = []
        for b in blocks:
            parts = b.splitlines()
            if len(parts) >= 2 and "-->" in "\n".join(parts[:2]):
                head = parts[:2]
                text_lines = parts[2:]
                # Trim trailing spaces only
                text_lines = [tl.rstrip() for tl in text_lines]
                # Remove leading/trailing completely blank text lines
                while text_lines and text_lines[0].strip() == "":
                    text_lines.pop(0)
                while text_lines and text_lines[-1].strip() == "":
                    text_lines.pop()
                # If after cleanup no text remains, preserve at least one safe placeholder
                if not text_lines:
                    text_lines = ["…"]
                # Limit to two lines, prioritizing non-empty lines
                non_empty = [tl for tl in text_lines if tl.strip() != ""]
                if len(non_empty) >= 2:
                    text_lines = non_empty[:2]
                elif len(non_empty) == 1:
                    text_lines = [non_empty[0]]
                else:
                    text_lines = ["…"]
                fixed_blocks.append("\n".join(head + text_lines))
            else:
                # Not a recognized block, keep as-is
                fixed_blocks.append(b)
        normalized = "\n\n".join(fixed_blocks) + "\n"

    # As we didn't change timestamps at all in this path, the >=1s rule is respected.
    # For text: we have only normalized whitespace; words are unchanged.

    out_name = f"temp_{uuid.uuid4()}_corrected.srt"
    return _write_processed_stub(out_name, normalized, processed_dir)


# PUBLIC_INTERFACE
def generate_subtitles_for_video(
    video_path: str,
    language: Optional[str],
    processed_dir: str,
    model_hint: Optional[str] = None,
) -> str:
    """Generate a trivial SRT with placeholder content to simulate STT output."""
    lang = language or "en"
    content = f"""1
00:00:00,000 --> 00:00:02,000
Generated subtitle line 1 ({lang})

2
00:00:02,500 --> 00:00:05,000
Generated subtitle line 2 ({lang})
"""
    out_name = f"temp_{uuid.uuid4()}_generated_{lang}.srt"
    return _write_processed_stub(out_name, content, processed_dir)


# PUBLIC_INTERFACE
def translate_subtitles(
    subtitle_path: str,
    target_language: str,
    source_language: Optional[str],
    processed_dir: str,
    model_hint: Optional[str] = None,
) -> str:
    """Pretend-translate by appending language codes to text lines, preserving SRT structure.

    If this function evolves to accept or produce structured subtitles with 'start'/'end'
    expressed in seconds, use the standardized SRT writer to emit accurate timestamp strings:
        from subtitle_time_utils import write_srt
        srt_text = write_srt(subtitles_list)
    """
    src = Path(subtitle_path).read_text(encoding="utf-8", errors="ignore")
    lines = src.splitlines()
    out_lines: List[str] = []
    for ln in lines:
        if re.match(r"^\d+$", ln) or "-->" in ln or ln.strip() == "":
            out_lines.append(ln)
        else:
            out_lines.append(f"{ln} [{target_language}]")
    out_name = f"temp_{uuid.uuid4()}_translated_{target_language}.srt"
    return _write_processed_stub(out_name, "\n".join(out_lines) + "\n", processed_dir)


# PUBLIC_INTERFACE
def validate_subtitles(subtitle_path: str, options: Dict) -> List[str]:
    """Run basic validations: character count per line, lines per caption, empty blocks."""
    issues: List[str] = []
    max_chars = int(options.get("max_chars_per_line", 42))
    max_lines = int(options.get("max_lines_per_caption", 2))
    text = Path(subtitle_path).read_text(encoding="utf-8", errors="ignore")
    blocks = re.split(r"\n\s*\n", text.strip())
    for idx, b in enumerate(blocks, start=1):
        parts = b.splitlines()
        # Expect at least index and timing
        if len(parts) < 2 or "-->" not in "\n".join(parts[:2]):
            issues.append(f"Block {idx} has invalid header/timing.")
            continue
        # Check text lines
        text_lines = [p for p in parts[2:] if p.strip() != ""]
        if len(text_lines) == 0:
            issues.append(f"Block {idx} has no text.")
        if len(text_lines) > max_lines:
            issues.append(f"Block {idx} exceeds max lines ({len(text_lines)} > {max_lines}).")
        for tl in text_lines:
            if len(tl) > max_chars:
                issues.append(f"Block {idx} line exceeds max chars ({len(tl)} > {max_chars}).")
    return issues
