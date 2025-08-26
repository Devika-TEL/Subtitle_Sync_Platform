# Re-export public interfaces for easier imports from BackendService package

# PUBLIC_INTERFACE
def align_subtitles_to_transcript(transcript, subtitles, **kwargs):
    """Public re-export of subtitle alignment.

    PUBLIC_INTERFACE
    Align subtitles to transcript using the simple strategy.

    Parameters:
        transcript: iterable/list of segments (dicts or strings)
        subtitles: iterable/list of cues (dicts or strings)
        kwargs: optional tuning parameters forwarded to implementation

    Returns:
        List of aligned cue dicts.
    """
    # Import from the retained simple alignment module
    from .subtitle_alignment_simple import align_subtitles_to_transcript as _align
    return _align(transcript, subtitles, **kwargs)
