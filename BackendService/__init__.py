# Re-export public interfaces for easier imports from BackendService package

# PUBLIC_INTERFACE
def align_subtitles_to_transcript(transcript, subtitles, **kwargs):
    """Public re-export of subtitle alignment.

    PUBLIC_INTERFACE
    Align subtitles to transcript using the public strategy.
    Parameters:
        transcript: iterable of segments (dicts or strings)
        subtitles: iterable of cues (dicts or strings)
        kwargs: optional tuning parameters forwarded to implementation
    Returns:
        List of aligned cue dicts.
    """
    from .subtitle_alignment_public import align_subtitles_to_transcript as _align
    return _align(transcript, subtitles, **kwargs)
