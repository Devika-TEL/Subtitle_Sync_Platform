"""
File utilities for upload handling and subtitle format helpers.
"""

from pathlib import Path
from typing import Optional, Iterable
import os


ALLOWED_SUB_EXTS = {".srt", ".vtt", ".ass", ".ssa", ".sbv", ".txt"}


# PUBLIC_INTERFACE
def ensure_dir(path: Path | str) -> None:
    """Ensure a directory exists (mkdir -p behavior)."""
    Path(path).mkdir(parents=True, exist_ok=True)


# PUBLIC_INTERFACE
def save_temp_upload(data: bytes, dst_dir: Path | str, suffix: str = "") -> Path:
    """Save bytes to a temporary file in the destination directory."""
    ensure_dir(dst_dir)
    p = Path(dst_dir) / f"temp_{os.urandom(6).hex()}{suffix}"
    p.write_bytes(data)
    return p


# PUBLIC_INTERFACE
def allowed_subtitle_extension(filename: Optional[str]) -> bool:
    """Check if file extension is a permitted subtitle extension."""
    if not filename:
        return False
    return Path(filename).suffix.lower() in ALLOWED_SUB_EXTS


# PUBLIC_INTERFACE
def guess_subtitle_format(path: Path | str) -> str:
    """Guess subtitle format from extension and rudimentary inspection."""
    p = Path(path)
    ext = p.suffix.lower()
    if ext == ".srt":
        return "srt"
    if ext == ".vtt":
        return "vtt"
    if ext in {".ass", ".ssa"}:
        return "ass/ssa"
    if ext == ".sbv":
        return "sbv"
    if ext == ".txt":
        # naive check for SRT-like numbered blocks
        try:
            head = p.read_text(errors="ignore").splitlines()[:5]
            if head and head[0].strip().isdigit():
                return "srt-txt"
        except Exception:
            pass
        return "plain"
    return "unknown"
