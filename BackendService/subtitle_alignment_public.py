# PUBLIC_INTERFACE
def subtitle_alignment(transcript, subtitles):
    """Align and correct subtitles based on a Whisper-like transcript.

    PUBLIC_INTERFACE
    This is the primary public entry point for aligning existing subtitle cues to the given transcript.
    It preserves the input format and metadata where possible and updates text and timing for accuracy.

    Args:
        transcript: dict with key 'segments' as a list of segments:
            Each segment has: {'start': float, 'end': float, 'text': str}
        subtitles: list of cue dicts (normalized),
            Each cue has: {'start': float, 'end': float, 'text': str|list[str], 'format': str, 'index'?: int, 'raw'?: dict}

    Returns:
        list: corrected and aligned list of subtitle cues in the same normalized structure.

    Raises:
        TypeError: if inputs are not of expected types.

    Notes:
        - This function delegates to correct_subtitles implemented in subtitle_alignment.py.
        - It exists to provide a stable, explicitly named public API as referenced by external callers/tests.
    """
    from .subtitle_alignment import correct_subtitles  # local import to avoid circulars
    if not isinstance(transcript, dict):
        raise TypeError("transcript must be a dict with 'segments'")
    if not isinstance(subtitles, list):
        raise TypeError("subtitles must be a list")

    return correct_subtitles(transcript, subtitles)
