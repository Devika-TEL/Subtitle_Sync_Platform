import pytest

try:
    from BackendService.subtitle_alignment import align_subtitles
except Exception:
    from subtitle_alignment import align_subtitles  # type: ignore


def mk_seg(s, e, t):
    return {"start": s, "end": e, "text": t}


def mk_sub(i, s, e, t="hello", fmt="srt"):
    return {"index": i, "start": s, "end": e, "text": t, "format": fmt}


# PUBLIC_INTERFACE
def test_no_empty_cues_when_transcript_blank_start():
    """
    When transcript has blank text at the beginning and subtitles also blank,
    the algorithm should not emit an empty cue (drop) and retain first intended
    subtitle text later.
    """
    transcript = [mk_seg(0.0, 1.0, ""), mk_seg(1.0, 2.0, "Second line")]
    subs = [
        mk_sub(1, 0.0, 0.5, ""),   # blank at start
        mk_sub(2, 1.0, 1.8, "Deuxième ligne"),  # first real intended text
    ]
    out = align_subtitles(transcript, subs, cross_lingual=True)
    # No empty text cues in output
    assert all(s.get("text", "").strip() != "" for s in out)
    # First non-empty subtitle text is preserved
    assert out[0]["text"] == "Deuxième ligne"


# PUBLIC_INTERFACE
def test_preserve_first_subtitle_text_if_transcript_empty_text():
    """
    If the transcript text is empty but the subtitle has text, we must retain the subtitle text.
    """
    transcript = [mk_seg(0.0, 1.0, "")]
    subs = [mk_sub(1, 0.0, 0.8, "Hello world")]
    out = align_subtitles(transcript, subs, cross_lingual=False)
    assert out[0]["text"] == "Hello world"
