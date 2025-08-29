import math
import pytest

# Import in both package and script contexts
try:
    from BackendService.subtitle_time_utils import write_srt, srt_timestamp_to_seconds
except Exception:
    from subtitle_time_utils import write_srt, srt_timestamp_to_seconds  # type: ignore


# PUBLIC_INTERFACE
def test_write_srt_spreads_across_two_minutes():
    """Ensure SRT timestamps are formatted in seconds and cover the full 2-minute duration."""
    # Create 6 subtitles spanning 0 to 120 seconds (2 minutes) evenly
    total_duration = 120.0
    n = 6
    dur = total_duration / n  # 20s each
    subs = []
    for i in range(n):
        start = i * dur
        end = start + dur - 0.5  # leave small gap
        subs.append({"index": i + 1, "start": start, "end": end, "text": f"line {i+1}"})

    srt_text = write_srt(subs)
    # Parse back the first and last cue times
    blocks = [b for b in srt_text.strip().split("\n\n") if b.strip()]
    assert len(blocks) == n
    first_lines = blocks[0].splitlines()
    last_lines = blocks[-1].splitlines()
    assert "-->" in first_lines[1]
    assert "-->" in last_lines[1]

    def parse_range(line: str):
        l, r = line.split("-->")
        return srt_timestamp_to_seconds(l.strip()), srt_timestamp_to_seconds(r.strip())

    first_start, _ = parse_range(first_lines[1])
    _, last_end = parse_range(last_lines[1])

    # Start should be ~0, end should be close to the total 120s
    assert math.isclose(first_start, 0.0, abs_tol=0.01)
    # Because we subtracted a 0.5s gap from each, the last end will be < 120 but > 115
    assert last_end > 115.0
    assert last_end <= 120.0

    # Round-trip check for a few arbitrary times
    ts = "00:01:23,456"
    secs = srt_timestamp_to_seconds(ts)
    # 1*60 + 23 + 0.456 = 83.456
    assert math.isclose(secs, 83.456, rel_tol=1e-9, abs_tol=1e-9)
