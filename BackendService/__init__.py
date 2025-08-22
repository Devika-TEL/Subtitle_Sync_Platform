# Re-export public interfaces for easier imports from BackendService package

# PUBLIC_INTERFACE
def subtitle_alignment(transcript, subtitles):
    """Public re-export of subtitle alignment.

    PUBLIC_INTERFACE
    See BackendService.subtitle_alignment_public.subtitle_alignment for details.
    """
    from .subtitle_alignment_public import subtitle_alignment as _subtitle_alignment
    return _subtitle_alignment(transcript, subtitles)
