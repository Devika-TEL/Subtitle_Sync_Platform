# Subtitle Repositioning Integration Plan (FastAPI)

This document outlines how to integrate the newly added subtitle repositioning module (subtitle_repositioning_code.py) into the BackendService FastAPI app without modifying core processing flows until optional integration is enabled.

## Overview

- Goal: Provide an endpoint to reposition subtitle cues to avoid burnt-in text via OCR-based top/bottom alignment decisions.
- Inputs: Video file and a subtitle file (.srt, .ass, .ssa, .vtt).
- Output: A new subtitle file with updated alignment/position (format-specific).

## Requirements and Dependencies

Add these to BackendService/requirements.txt (not yet installed here):
- numpy
- opencv-python-headless (preferred for servers) or opencv-python
- rapidocr-onnxruntime
- onnxruntime (if not installed transitively via rapidocr-onnxruntime)
- pysrt (already present)

Notes:
- On servers and CI, prefer opencv-python-headless.
- RapidOCR initialization should not run at import-time in a multi-worker server; consider lazy init in a function.

## Endpoint Design

- Method: POST
- Path: /reposition
- Tags: ["processing"]
- Request: Multipart form data
  - video: UploadFile (required)
  - subtitle: UploadFile (required; allowed: .srt, .ass, .ssa, .vtt)
  - min_frames: integer (optional, default: 3)
- Response: FileResponse with repositioned subtitle file.

OpenAPI summary/description:
- Summary: Reposition subtitles to avoid burnt-in text
- Description: Runs OCR on sampled frames within each subtitle cue time range to decide whether to place cue at top or bottom. Outputs format-appropriate position adjustments.

## Sample Implementation Outline

Pseudocode (after module fixes described in analysis document):

```python
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from subtitle_repositioning_code import process_subtitle
import os

router = APIRouter(tags=["processing"])

@router.post("/reposition", summary="Reposition subtitles to avoid burnt-in text")
async def reposition_subtitles(
    video: UploadFile = File(..., description="Video file"),
    subtitle: UploadFile = File(..., description="Subtitle file (.srt/.ass/.ssa/.vtt)"),
    min_frames: int = Form(3)
):
    # Validate content types and extensions
    # Save to UPLOAD_DIR
    # Call process_subtitle(video_path, subtitle_path)
    # Return FileResponse with the output file
    ...
```

Integration in main.py:
- Import router and include_router(router) on app.

## Pre-Integration Fixes (Module)

Before importing subtitle_repositioning_code in a FastAPI context:
1) Remove or guard `from call_demeter import llm` import. It’s not present in this repo and causes ImportError.
2) Replace Windows path string literals for visualization outputs:
   - Use `os.path.join` and ensure directory exists.
   - Disable visualization by default in production.
3) Avoid `logging.basicConfig(...)` in the module; rely on FastAPI app logging.
4) Make OCR engine initialization lazy and thread-safe; avoid global mutable state (counter `a`).
5) Fix `get_position_for_segment` to avoid referencing undefined `frame` after loop; handle zero-frame scenarios gracefully.
6) Improve VTT time parsing into a robust HH:MM:SS.mmm → seconds converter.

## Edge Cases and Error Handling

- Unsupported formats: Return 422 with clear message.
- OCR failures: Default to bottom position or configurable fallback; log warning.
- Long videos with many cues: OCR can be slow; consider:
  - Caching OCR detections by frame index or timestamp.
  - Sampling fewer frames or only bottom ROI.
  - A background job path if request timeouts are a risk.

## Performance Tips

- Downsample frames (resize) to speed up OCR without losing layout precision.
- Use caching across overlapping cues (adjacent cues often share nearby frames).
- Consider enabling GPU acceleration if available (validating RapidOCR support).

## Output Format Considerations

- Current SRT input produces ASS output (.ass). If format preservation is required, document that behavior or implement an SRT-preserving path.
- ASS/SSA handling updates `{\\anX}` tags in Dialogue lines.
- VTT handling updates/sets `line:` settings.

## Security and Limits

- Enforce file size and extension limits (reuse existing middlewares and config).
- Sanitize and isolate user uploads to UPLOAD_DIR.

## Testing Checklist

- Unit tests:
  - Timestamp parsing and conversion to seconds.
  - Alignment tag replacement logic for ASS/SSA.
  - VTT `line:` replacement and insertion.
  - Decision function top/bottom behavior for various bounding boxes.
- Integration tests:
  - POST /reposition happy path for each format.
  - Large files and long videos with appropriate timeouts or background jobs.
