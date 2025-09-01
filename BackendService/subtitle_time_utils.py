"""
Time conversion and SRT export utilities for subtitles.

This module centralizes the logic for converting between seconds (float)
and SRT timestamp strings, and for exporting a list of subtitle dictionaries
into valid SRT text.

CRITICAL UNITS NOTE:
- All timing values handled by this module are in seconds (float).
- Do NOT pass milliseconds to these functions. If your input times are in
  milliseconds, convert them by dividing by 1000.0 before calling these
  utilities. Example: seconds = ms / 1000.0

Design decisions:
- Clamp negative times to 0.0 to avoid negative timestamps in output.
- Properly round milliseconds and carry to seconds/minutes/hours when needed.
- Enforce that each cue has end >= start + minimal duration to avoid zero-length cues.
- Provide parsing from SRT timestamp to seconds for completeness and potential use.

Public interfaces are marked with PUBLIC_INTERFACE as required.
"""

from __future__ import annotations

from typing import List, Dict, Tuple
import re
import math


_SRT_TS_RE = re.compile(
    r"^(?P<h>\d{2}):(?P<m>\d{2}):(?P<s>\d{2}),(?P<ms>\d{3})$"
)

_MIN_DURATION = 0.1  # minimal cue duration enforced in write_srt
_MIN_GAP = 0.0       # no gap enforced here; writers can enforce if needed


def _clamp_non_negative(t: float) -> float:
    """Clamp negative seconds to zero."""
    try:
        return max(0.0, float(t))
    except Exception:
        return 0.0


def _split_hmsms(total_seconds: float) -> Tuple[int, int, int, int]:
    """
    Convert seconds (float) to (hours, minutes, seconds, milliseconds)
    with proper rounding and carry handling.
    """
    t = _clamp_non_negative(total_seconds)
    # Round to nearest millisecond to avoid 59.999999 -> 60.000 issues
    ms_total = int(round(t * 1000.0))
    ms = ms_total % 1000
    sec_total = ms_total // 1000
    s = sec_total % 60
    min_total = sec_total // 60
    m = min_total % 60
    h = min_total // 60
    return h, m, s, ms


def _format_2d(n: int) -> str:
    return f"{n:02d}"


def _format_3d(n: int) -> str:
    return f"{n:03d}"


# PUBLIC_INTERFACE
def seconds_to_srt_timestamp(seconds: float) -> str:
    """Convert seconds (float) to SRT timestamp format 'HH:MM:SS,mmm'."""
    h, m, s, ms = _split_hmsms(seconds)
    return f"{_format_2d(h)}:{_format_2d(m)}:{_format_2d(s)},{_format_3d(ms)}"


# PUBLIC_INTERFACE
def srt_timestamp_to_seconds(ts: str) -> float:
    """Convert an SRT timestamp 'HH:MM:SS,mmm' to seconds (float)."""
    m = _SRT_TS_RE.match(ts.strip())
    if not m:
        raise ValueError(f"Invalid SRT timestamp: {ts!r}")
    h = int(m.group("h"))
    mi = int(m.group("m"))
    s = int(m.group("s"))
    ms = int(m.group("ms"))
    return float(h) * 3600.0 + float(mi) * 60.0 + float(s) + float(ms) / 1000.0


def _normalize_cue_times(start: float, end: float) -> Tuple[float, float]:
    """Ensure non-negative times and minimum duration (seconds)."""
    s = _clamp_non_negative(start)
    e = _clamp_non_negative(end if end is not None else s + _MIN_DURATION)
    if e <= s:
        e = s + _MIN_DURATION
    return s, e


def _looks_like_milliseconds(values: List[float]) -> bool:
    """
    Heuristic: detect if provided times likely represent milliseconds.
    Returns True if median value is large (e.g., > 3000) and min>100 suggesting ms scale.
    This is for diagnostics only; we DO NOT auto-convert.
    """
    if not values:
        return False
    try:
        arr = sorted(abs(float(v)) for v in values if v is not None)
        if not arr:
            return False
        median = arr[len(arr)//2]
        mn = arr[0]
        return (median > 3000.0) and (mn > 100.0)
    except Exception:
        return False


# PUBLIC_INTERFACE
def write_srt(subtitles: List[Dict]) -> str:
    """
    Convert a list of subtitle dicts into SRT text.

    Each item in `subtitles` should contain:
      - 'start' (float seconds),
      - 'end' (float seconds),
      - 'text' (string),
      - optional 'index' (int)

    Returns:
      str: full SRT file content with trailing newline.
    """
    def _sanitize_text_lines(raw_text: str) -> List[str]:
        """
        Preserve original text content as much as possible while ensuring we never
        emit an empty cue. Strategy:
        - Split by lines preserving internal newlines.
        - Trim trailing spaces on each line only (do not strip leading words).
        - Drop leading/trailing blank lines.
        - Collapse multiple consecutive blank lines to a single blank line.
        - Enforce max 2 lines (SRT OTT friendly) while preferring non-empty lines.
        - If all lines are empty/whitespace, return a single placeholder "…".
        """
        if raw_text is None:
            return ["…"]
        # Split to lines
        lines = str(raw_text).splitlines()
        # Trim trailing spaces only
        lines = [ln.rstrip() for ln in lines]
        # Remove leading/trailing blank lines
        while lines and lines[0].strip() == "":
            lines.pop(0)
        while lines and lines[-1].strip() == "":
            lines.pop()
        # Collapse multiple blank lines
        collapsed: List[str] = []
        blank = False
        for ln in lines:
            if ln.strip() == "":
                if not blank:
                    collapsed.append("")
                    blank = True
            else:
                collapsed.append(ln)
                blank = False
        # If after cleanup nothing remains, ensure a non-empty placeholder
        if not collapsed:
            return ["…"]
        # Enforce up to 2 lines, giving preference to non-empty ones
        non_empty = [ln for ln in collapsed if ln.strip() != ""]
        if len(non_empty) >= 2:
            return non_empty[:2]
        if len(non_empty) == 1:
            # include one blank if there was structure, else just single line
            return [non_empty[0]]
        # No non-empty but we have blanks -> fallback
        return ["…"]

    blocks: List[str] = []
    for idx, item in enumerate(subtitles, start=1):
        start_f = float(item.get("start", 0.0))
        end_f = float(item.get("end", start_f + _MIN_DURATION))
        text = item.get("text", "")
        s, e = _normalize_cue_times(start_f, end_f)

        # Format timestamps accurately
        sh = seconds_to_srt_timestamp(s)
        eh = seconds_to_srt_timestamp(e)

        # Enforce at least 1 index line, 1 timing line, then text
        block_lines = [
            str(item.get("index", idx)),
            f"{sh} --> {eh}",
        ]
        # Sanitize text lines to avoid empty cues
        safe_text_lines = _sanitize_text_lines(text)
        block_lines.extend(safe_text_lines)

        blocks.append("\n".join(block_lines))

    return "\n\n".join(blocks) + "\n"
