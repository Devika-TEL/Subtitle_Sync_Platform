import math
import pytest

# Import module in both package and script contexts
try:
    from BackendService.subtitle_alignment import align_subtitles
except Exception:
    from subtitle_alignment import align_subtitles  # type: ignore


def mk_seg(s, e, t):
    return {"start": s, "end": e, "text": t}


def mk_sub(i, s, e, t="hello", fmt="srt"):
    return {"index": i, "start": s, "end": e, "text": t, "format": fmt}


# PUBLIC_INTERFACE
def test_preserve_good_cues_only_adjust_bad_ones():
    """
    Ensure the algorithm preserves already-correct cues and adjusts only mis-timed ones.

    Scenario:
    - Transcript has 3 segments.
    - Subtitles: 1 and 3 are correct; 2 is slightly off (early).
    - Regression bug previously made 1 and 3 shift towards start due to cascaded enforcement.
    """
    transcript = [
        mk_seg(1.0, 2.0, "A"),
        mk_seg(3.0, 4.0, "B"),
        mk_seg(5.0, 6.0, "C"),
    ]
    subs = [
        mk_sub(1, 1.0, 1.9, "A"),
        mk_sub(2, 2.6, 3.3, "B"),  # slightly early start; still overlaps but needs minor adjustment
        mk_sub(3, 5.0, 5.9, "C"),
    ]
    out = align_subtitles(transcript, subs, cross_lingual=True)

    # Cue 1 and 3 should remain approximately where they were
    assert math.isclose(out[0]["start"], 1.0, abs_tol=0.15)
    assert math.isclose(out[0]["end"], 1.9, abs_tol=0.25)

    assert math.isclose(out[2]["start"], 5.0, abs_tol=0.15)
    assert math.isclose(out[2]["end"], 5.9, abs_tol=0.25)

    # Cue 2 should not be snapped to segment start but may be minimally shifted forward
    assert out[1]["start"] >= 2.6
    assert out[1]["start"] < 3.2
    assert out[1]["end"] > out[1]["start"]


# PUBLIC_INTERFACE
def test_sparse_transcript_no_bunching_at_zero():
    """
    With an empty transcript, ensure distribution across a synthetic horizon and no clustering at 0.
    """
    subs = [
        mk_sub(1, 0.0, 0.8, "x"),
        mk_sub(2, 0.9, 1.7, "y"),
        mk_sub(3, 1.8, 2.6, "z"),
    ]
    out = align_subtitles([], subs, cross_lingual=True)
    # Ensure not all cues are at 0 and they are in increasing order
    assert out[0]["start"] >= 0.0
    assert out[1]["start"] > out[0]["start"]
    assert out[2]["start"] > out[1]["start"]


# PUBLIC_INTERFACE
def test_cross_lingual_preserves_text():
    """
    In cross-lingual mode, content text should not be replaced by transcript text.
    """
    transcript = [mk_seg(1.0, 2.0, "EN text")]
    subs = [mk_sub(1, 1.0, 1.8, "FR texte")]
    out = align_subtitles(transcript, subs, cross_lingual=True)
    assert out[0]["text"] == "FR texte"


# PUBLIC_INTERFACE
def test_alignment_no_time_compression_over_two_minutes():
    """
    Ensure alignment does not compress a 2-minute range into a few seconds.
    We simulate a transcript spanning ~0..120s and subtitles roughly matching.
    """
    # Create a transcript covering 0..120s with 12 segments of 10s each
    transcript = []
    for i in range(12):
        s = i * 10.0
        e = s + 10.0
        transcript.append(mk_seg(s, e, f"T{i+1}"))

    # Subtitles roughly aligned with small jitter, spanning the same window
    subs = []
    for i in range(12):
        s = i * 10.0 + (0.2 if i % 2 == 0 else 0.0)
        e = s + 8.0
        subs.append(mk_sub(i + 1, s, e, f"S{i+1}"))

    out = align_subtitles(transcript, subs, cross_lingual=True)
    assert len(out) == 12
    # Start near 0 and end should be close to 120 (allowing for caps/gaps)
    assert out[0]["start"] >= 0.0
    assert out[-1]["end"] > 100.0
    assert out[-1]["end"] <= 125.0
