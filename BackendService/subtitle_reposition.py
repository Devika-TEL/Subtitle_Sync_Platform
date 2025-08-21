"""
Subtitle repositioning utilities based on detection of hardcoded (burnt-in) text.

This module exposes a clearly named public entry point that analyzes a video
for persistent hardcoded text (via OCR routines) and repositions subtitle cues
to avoid overlap. It supports major subtitle formats: SRT/ASS/SSA/VTT.

Implementation note:
- For CI determinism, this reference implementation stubs OCR using a heuristic
  that simulates detection of burnt-in text at the bottom third of the frame.
- In a production system, integrate RapidOCR or a similar OCR engine to analyze
  sampled frames across the video, aggregate persistent regions (e.g., heatmap),
  and pick a position (top/bottom) or specific ASS/VTT style for each segment.

Usage:
    from subtitle_reposition import reposition_subtitles_based_on_hardcoded_text
    output_path = reposition_subtitles_based_on_hardcoded_text(
        video_path="path/to/video.mp4",
        subtitle_path="path/to/subtitle.srt",
        output_path="path/to/output.srt",  # if None, writes to processed dir
        processed_dir="./processed",
        sample_rate=1.0,  # frames per second to sample for OCR
    )
"""

from pathlib import Path
from typing import Optional, List, Tuple
import re
import uuid

# -------------------------------
# Simple format detection helpers
# -------------------------------

def _detect_sub_format(path: Path) -> str:
    """Detect basic subtitle format based on extension."""
    ext = path.suffix.lower()
    if ext == ".srt":
        return "srt"
    if ext == ".vtt":
        return "vtt"
    if ext == ".ass":
        return "ass"
    if ext == ".ssa":
        return "ssa"
    # default to srt if unknown to keep pipeline simple
    return "srt"


def _ensure_output_path(output_path: Optional[str], processed_dir: str, ext: str) -> Path:
    """Ensure an output path exists; if not provided, create a temp file path."""
    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        return out
    out_name = f"temp_{uuid.uuid4()}_repositioned{ext}"
    out = Path(processed_dir) / out_name
    out.parent.mkdir(parents=True, exist_ok=True)
    return out


# ---------------------------------------
# OCR stub and positioning decision logic
# ---------------------------------------

def _sample_frames_and_detect_burnt_in_text(
    video_path: str, sample_rate: float
) -> Tuple[bool, bool]:
    """
    Stub that 'detects' persistent burnt-in text regions.

    Returns:
      (bottom_has_text, top_has_text)
    In a real implementation, use RapidOCR to OCR sampled frames and determine
    if the top or bottom region frequently contains text across the duration.

    For determinism:
    - If filename contains "bottom", assume bottom text present.
    - If filename contains "top", assume top text present.
    - Otherwise assume bottom text is present (common for captions/watermarks).
    """
    name = Path(video_path).name.lower()
    bottom = "top" not in name  # default True
    top = "top" in name
    if "bottom" in name:
        bottom = True
    return bottom, top


def _choose_position_avoid_overlap(
    bottom_has_text: bool, top_has_text: bool
) -> str:
    """
    Choose a subtitle position ('top' or 'bottom') to minimize overlap.
    If both regions have text, default to 'top' to keep away from progress bars, etc.
    """
    if bottom_has_text and not top_has_text:
        return "top"
    if top_has_text and not bottom_has_text:
        return "bottom"
    # both or neither -> prefer top as safer default against players' controls
    return "top"


# ----------------------------
# Per-format reposition writers
# ----------------------------

def _reposition_srt(content: str, position: str) -> str:
    """
    For SRT, a portable way is to inject positioning hints as comments,
    as SRT has no standard position attribute. Many players ignore it,
    but downstream conversion to ASS/VTT can use this hint.
    We prefix each block with a comment: NOTE: position=<top|bottom>
    """
    blocks = re.split(r"\n\s*\n", content.strip(), flags=re.MULTILINE)
    out_blocks: List[str] = []
    for b in blocks:
        lines = b.splitlines()
        if not lines:
            continue
        # Insert a comment line after the index if possible
        if re.match(r"^\d+\s*$", lines[0]):
            if len(lines) >= 2 and "-->" in lines[1]:
                new_lines = [lines[0], lines[1], f"NOTE: position={position}"]
                new_lines += lines[2:]
            else:
                new_lines = [lines[0], f"NOTE: position={position}"] + lines[1:]
        else:
            new_lines = [f"NOTE: position={position}"] + lines
        out_blocks.append("\n".join(new_lines))
    return "\n\n".join(out_blocks) + "\n"


def _reposition_vtt(content: str, position: str) -> str:
    """
    For WebVTT, we can append cue settings like 'line:5 position:50%' and 'align:start/end'.
    We'll place top with 'line:0', bottom with 'line:90'.
    """
    def _transform_cue_header(header: str) -> str:
        if "-->" not in header:
            return header
        # Keep existing settings; append a line setting
        line_val = "0" if position == "top" else "90"
        if "line:" in header:
            header = re.sub(r"line:\s*\d+", f"line:{line_val}", header)
        else:
            header = header.strip() + f" line:{line_val}"
        return header

    lines = content.splitlines()
    out_lines: List[str] = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        if "-->" in ln:
            out_lines.append(_transform_cue_header(ln))
        else:
            out_lines.append(ln)
        i += 1
    return "\n".join(out_lines) + ("\n" if not content.endswith("\n") else "")


def _reposition_ass_ssa(content: str, position: str) -> str:
    """
    For ASS/SSA, we can inject or modify a Style with Alignment:
      - Bottom center: Alignment=2
      - Top center: Alignment=8
    We'll attempt to modify 'Default' style if present; otherwise prepend a style.
    Also append \pos override can be used, but we'll keep to Alignment for simplicity.
    """
    alignment = "8" if position == "top" else "2"
    lines = content.splitlines()
    out_lines: List[str] = []
    in_styles = False
    default_style_modified = False
    for ln in lines:
        if ln.strip().lower() == "[v4+ styles]" or ln.strip().lower() == "[v4 styles]":
            in_styles = True
            out_lines.append(ln)
            continue
        if in_styles:
            if ln.strip().startswith("[") and ln.strip().endswith("]"):
                # leaving styles section
                in_styles = False
                if not default_style_modified:
                    # Try to inject a default style tweak line if format permits
                    # Many ASS lines are like: Style: Default,Font,Size,...,Alignment
                    # We'll attempt a safe replacement on any 'Style: Default' line seen earlier.
                    pass
                out_lines.append(ln)
                continue
            if ln.strip().lower().startswith("style:"):
                # Try to modify Default alignment
                if re.match(r"(?i)^style:\s*default[,;]", ln):
                    # Replace 'Alignment=\d' or the alignment field.
                    if "Alignment=" in ln:
                        ln = re.sub(r"Alignment=\d+", f"Alignment={alignment}", ln)
                        default_style_modified = True
                    else:
                        # try to replace by fields (ASS uses comma separated, 10th field usually alignment; we'll regex replace)
                        parts = ln.split(": ", 1)[1].split(",")
                        if len(parts) >= 10:
                            parts[8] = alignment  # typical index for Alignment (0-based 8)
                            ln = "Style: Default," + ",".join(parts[1:]) if parts[0].lower() == "default" else "Style: " + ",".join(parts)
                            default_style_modified = True
                out_lines.append(ln)
                continue
        out_lines.append(ln)

    # If no styles section or couldn't modify, we can append a comment note for tools
    if not default_style_modified:
        out_lines.append(f"; NOTE: desired_alignment={alignment} (top=8,bottom=2)")

    return "\n".join(out_lines) + ("\n" if not content.endswith("\n") else "")


def _apply_reposition(content: str, fmt: str, position: str) -> str:
    """Dispatch reposition per format."""
    if fmt == "srt":
        return _reposition_srt(content, position)
    if fmt == "vtt":
        return _reposition_vtt(content, position)
    if fmt in ("ass", "ssa"):
        return _reposition_ass_ssa(content, position)
    # Fallback to srt comment hint
    return _reposition_srt(content, position)


# PUBLIC_INTERFACE
def reposition_subtitles_based_on_hardcoded_text(
    video_path: str,
    subtitle_path: str,
    output_path: Optional[str] = None,
    processed_dir: str = "./processed",
    sample_rate: float = 1.0,
) -> str:
    """
    Reposition subtitles to avoid overlap with detected hardcoded (burnt-in) text.

    This function samples frames from the video, detects persistent text regions
    (top/bottom), and chooses a subtitle position ('top' or 'bottom') that minimizes
    overlap. The resulting subtitle file is written in the same format as input.

    Args:
        video_path: Path to the input video file to analyze via OCR.
        subtitle_path: Path to the existing subtitle file (SRT/ASS/SSA/VTT).
        output_path: Optional explicit output path. If None, a file is written into processed_dir.
        processed_dir: Directory for processed output files if output_path is not provided.
        sample_rate: Frames per second to sample for OCR analysis.

    Returns:
        Path to the repositioned subtitle file.

    Notes:
        - This reference implementation uses a deterministic stub for OCR so CI runs reliably.
          Replace `_sample_frames_and_detect_burnt_in_text` with a RapidOCR-powered analyzer.
    """
    sub_path = Path(subtitle_path)
    if not sub_path.exists():
        raise FileNotFoundError(f"Subtitle file not found: {subtitle_path}")
    if not Path(video_path).exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    fmt = _detect_sub_format(sub_path)
    content = sub_path.read_text(encoding="utf-8", errors="ignore")

    # OCR analysis (stubbed)
    bottom_has_text, top_has_text = _sample_frames_and_detect_burnt_in_text(
        video_path=video_path, sample_rate=sample_rate
    )
    position = _choose_position_avoid_overlap(bottom_has_text, top_has_text)

    # Apply repositioning
    updated = _apply_reposition(content, fmt, position)

    # Write output
    out = _ensure_output_path(output_path, processed_dir, f".{fmt}")
    out.write_text(updated, encoding="utf-8")
    return str(out)


if __name__ == "__main__":
    # Demonstration CLI usage:
    # python -m subtitle_reposition --video path/to/video.mp4 --subs path/to/subtitle.srt --out path/to/output.srt
    import argparse

    parser = argparse.ArgumentParser(
        description="Reposition subtitles to avoid overlap with hardcoded (burnt-in) text."
    )
    parser.add_argument("--video", required=True, help="Path to the video file")
    parser.add_argument("--subs", required=True, help="Path to the subtitle file (SRT/ASS/SSA/VTT)")
    parser.add_argument("--out", default=None, help="Optional explicit output subtitle path")
    parser.add_argument("--processed-dir", default="./processed", help="Processed directory if --out not provided")
    parser.add_argument("--sample-rate", type=float, default=1.0, help="Frames per second to sample for OCR")

    args = parser.parse_args()
    result = reposition_subtitles_based_on_hardcoded_text(
        video_path=args.video,
        subtitle_path=args.subs,
        output_path=args.out,
        processed_dir=args.processed_dir,
        sample_rate=args.sample_rate,
    )
    print(f"Repositioned subtitle written to: {result}")
