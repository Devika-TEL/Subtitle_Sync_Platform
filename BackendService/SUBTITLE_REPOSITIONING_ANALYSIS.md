# Subtitle Repositioning Module Analysis and Integration Guide

This document analyzes the newly added subtitle repositioning code located at:
- BackendService/subtitle_repositioning_code.py

It summarizes functionality, structure, integration readiness with the BackendService FastAPI app, identifies issues and improvements, and proposes an integration plan.

## Executive Summary

- Purpose: Reposition subtitles (top/bottom) to avoid overlapping with burnt‑in text in the video by running OCR on sampled frames near each subtitle segment’s time range.
- Approach: Uses RapidOCR (ONNXRuntime) to detect text bounding boxes per sampled frames, heuristically decides if lower portion contains text, and then:
  - For SRT input: writes a new ASS file inserting proper alignment tags per cue.
  - For ASS/SSA input: updates alignment tags per dialogue line.
  - For VTT input: adjusts the “line:” cue position percentage.
- Status: Not integrated into FastAPI; direct imports will currently fail due to missing optional dependencies and an invalid import (`call_demeter`). There are several correctness, portability, and performance issues that should be addressed before integration.
- Integration options:
  1) A dedicated route: POST /reposition to upload video + subtitle and return repositioned subtitle.
  2) An optional post‑processing step after correction/generation in the existing workflow.

## File Overview

- subtitle_repositioning_code.py
  - External dependencies: cv2 (OpenCV), numpy, pysrt, rapidocr_onnxruntime (RapidOCR), re, logging, and `call_demeter.llm` (unused but imported).
  - Global state:
    - `engine = RapidOCR()` instantiated at import time.
    - Global counter `a` used for saved visualization frame naming.
  - Key functions:
    - OCR and pre-processing:
      - `detect_using_rapidocr(img)` → returns list of detections with fields {box, text, score}, saves visualization images for each processed frame.
      - Several image pre-processing helpers (`preprocess_threshold`, `preprocess_using_blackout`, `preprocess`, `preprocess_adaptive_threshold`) — currently not actively used (the code passes the raw frame).
    - Decision:
      - `decide_subtitle_position(filtered_detections_list, frame_height, bottom_threshold_ratio=0.75)` → returns "top" if any detection’s average Y is below/above threshold (default bottom 75% boundary), else "bottom".
      - `get_position_for_segment(video_path, start_sec, end_sec, min_frames=3)` → samples frames between start/end times, runs OCR per frame, then decides top/bottom.
    - Writers (format-specific):
      - `reposition_srt(video_path, srt_path, output_ass_path, min_frames=3)` → converts to ASS file with alignment tags {\\an8} (top) or {\\an2} (bottom) per cue.
      - `reposition_ass(video_path, ass_path, output_ass_path)`
      - `reposition_ssa(video_path, ssa_path, output_ssa_path)`
      - `reposition_vtt(video_path, vtt_path, output_vtt_path)` → modifies "line:" property to 0% (top) or 80% (bottom).
    - Orchestrator:
      - `process_subtitle(video_path, subtitle_path)` → dispatches to proper reposition function based on extension and returns new output path.

## Functional Flow

1) For each subtitle cue time range:
   - Derive start_sec and end_sec.
   - Sample `min_frames` frames across this range.
   - Run OCR (RapidOCR) per frame and collect bounding boxes.
   - If any detected text boxes average Y position is within the lower portion of the frame (avg Y > 0.75 * height), choose "top"; otherwise "bottom".
2) Update the subtitle output accordingly:
   - SRT input → generate ASS output with alignment tag embedded in Dialogue.
   - ASS/SSA input → replace alignment tag in Dialogue lines (regex).
   - VTT input → adjust "line:" property in cue line.

## Architectural Fit and Integration Points

- Current FastAPI app (BackendService/main.py) provides processing endpoints but does not import or use this module.
- Natural integration points:
  - After correction step in `SubtitleProcessor.correct_subtitles(...)`: optionally call repositioning to emit a repositioned output (ASS or format-preserving as feasible).
  - A new dedicated endpoint e.g. POST /reposition to upload (video + subtitle) and return repositioned subtitle file.
  - A background job task variant registered via the existing job processor if reposition should be asynchronous.

## Issues and Improvements

Severity high (must fix before integration):
- Import errors:
  - `from call_demeter import llm` — this module does not exist in the repo, causing ImportError on import. The `filter_detections` function immediately returns and never uses `llm`, but importing the module will still fail. Make this optional or remove it.
- Dependencies not declared:
  - requirements.txt is missing: opencv-python-headless (or opencv-python), numpy, rapidocr-onnxruntime (and its runtime e.g., onnxruntime or as installed by the package). Without these, any import/use will fail.
- OS path separators:
  - Visualization saving uses raw Windows-style paths like `rf"rapid_ocr_frames\\result_{a}.jpg"`. On Linux, this inserts a literal backslash in file name and the directory may not exist. Use `os.path.join`, forward slashes, and ensure directories exist.
- Thread-safety and import-time side effects:
  - Global `engine = RapidOCR()` and global counter `a` are not thread-safe. In a web server with concurrency, this can cause issues. Initialize engine per request or guard with locks; avoid global mutable counters.
- get_position_for_segment bug(s):
  - Calls `filter_detections(detections=filtered_detections_per_frame, frame=frame)` after loop; `frame` is out of scope if the loop never ran or if a read failed — leads to NameError.
  - `filter_detections` returns immediately and is effectively a no-op, so this call is useless and may crash.
- Performance considerations:
  - Running OCR per segment can be extremely slow on long subtitle files. Consider caching frame OCR results by time and re-using across overlapping segments.
- Logging configuration:
  - `logging.basicConfig(...)` called within the module at import time can override global logging config for the app. Use module-level logger and respect the app’s logging settings.

Severity medium:
- VTT time parsing:
  - Current computation for converting cue times to seconds is fragile and likely incorrect in edge cases (milliseconds handling and reversed enumerate math). Use a robust parser for HH:MM:SS.mmm or leverage datetime/timedelta parsing.
- Output format behavior:
  - For SRT input, the module always outputs ASS (.ass). Some workflows expect format-preserving repositioning. Consider preserving original format where possible (e.g., SRT → SRT via custom tags or conversion choices documented).
- Directory management:
  - Ensure visualization output directory (e.g., processed/ocr_frames) exists; make saving visualizations configurable or disable by default in production.

Nice-to-have:
- Configurability:
  - Expose parameters (min_frames, bottom_threshold_ratio, OCR settings, visualization on/off) via function args or environment variables.
- Pre-processing tuning:
  - The module includes multiple pre-processing options but currently uses the raw frame. Add a configurable path to select the best preprocessing pipeline depending on video characteristics.
- Error handling and fallbacks:
  - If OCR fails, define a fallback strategy (e.g., default to bottom), and log appropriately without crashing the request.
- Unit tests:
  - Add tests for timestamp parsing, alignment replacement logic, and decision logic for several synthetic cases.

## Dependency Checklist (to add in BackendService/requirements.txt)

- numpy
- opencv-python-headless (prefer headless for servers) or opencv-python
- rapidocr-onnxruntime
- onnxruntime (if not pulled in transitively; check RapidOCR package requirements)
- pysrt (already present)
- pillow (if required by RapidOCR imaging pipeline; often installed transitively)

Note: Use versions compatible with the project’s Python version and CI environment. For production containers, opencv-python-headless is preferred.

## Suggested API Integration (FastAPI)

Option A: Dedicated endpoint for repositioning

- Endpoint: POST /reposition
- Params: UploadFile video (required), UploadFile subtitle (required), int min_frames (optional, default 3)
- Behavior: Saves uploads to UPLOAD_DIR, calls `process_subtitle(video_path, subtitle_path)` from the module, returns FileResponse of the repositioned subtitle.

Example outline (do not paste as-is without addressing the issues above and adding dependencies):

```python
# In BackendService/main.py
from fastapi import UploadFile, File, Form, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from subtitle_repositioning_code import process_subtitle  # Ensure module is fixed and dependencies installed

@app.post("/reposition", tags=["processing"], summary="Reposition subtitles to avoid burnt-in text")
async def reposition_subtitles(
    video: UploadFile = File(..., description="Video file"),
    subtitle: UploadFile = File(..., description="Subtitle file (.srt/.ass/.ssa/.vtt)"),
    min_frames: int = Form(3)
):
    try:
        if not video.content_type.startswith('video/'):
            raise HTTPException(status_code=422, detail="Invalid video file format")

        video_path = save_uploaded_file(video, UPLOAD_DIR)
        subtitle_path = save_uploaded_file(subtitle, UPLOAD_DIR)

        result_path = process_subtitle(video_path, subtitle_path)

        return FileResponse(
            path=result_path,
            filename=os.path.basename(result_path),
            media_type="text/plain"
        )
    except Exception as e:
        logger.exception("Repositioning failed")
        raise HTTPException(status_code=500, detail=f"Repositioning failed: {e}")
```

Option B: Integrate as a post-correction step

- In `SubtitleProcessor.correct_subtitles(...)`, after writing corrected SRT, optionally run reposition if flag is set:
```python
from subtitle_repositioning_code import process_subtitle

if enable_repositioning:
    result_path = process_subtitle(video_path, output_path)  # output_path is the corrected subtitle path
else:
    result_path = output_path
```
- Add config/flag to opt-in repositioning.

Option C: Background job type

- Create a new job type "reposition" reusing job_processor and the DB schema.
- Similar to existing /process route, queue the job and run repositioning in background.

## Required Fixes Before Integration

1) Remove or guard the `call_demeter.llm` import:
   - Make `filter_detections` either a no-op without importing `llm`, or import inside function with try/except and only run if configured.
2) Add missing dependencies to requirements and ensure CI/containers install them.
3) Replace all hard-coded backslashes and ensure output directories exist:
   - Use `os.path.join("processed", "rapid_ocr_frames", f"result_{a}.jpg")` and create the directory if not exists.
4) Avoid import-time side effects:
   - Do not call `logging.basicConfig(...)` within library modules used by FastAPI.
   - Initialize `RapidOCR()` within a function or a lightweight singleton guarded by a lock.
5) Fix `get_position_for_segment`:
   - Remove or correct `filter_detections` call and ensure variables are in scope.
   - Add error handling when frames cannot be read.
6) Improve VTT time parsing:
   - Implement a robust HH:MM:SS.mmm parser and handle cue settings reliably when adding `line:` attributes.
7) Performance optimizations (recommended):
   - Cache OCR results by timestamp and reuse across segments.
   - Consider downsampling frames and/or limiting OCR to ROIs (e.g., bottom region only).

## How to Use the Module (after fixes)

Programmatic usage:
```python
from subtitle_repositioning_code import process_subtitle

output_file = process_subtitle(video_path="/path/to/video.mp4",
                               subtitle_path="/path/to/subtitle.srt")
print("Repositioned file:", output_file)
```

FastAPI route usage (Option A above): POST /reposition with multipart form uploading video and subtitle, receive repositioned subtitle file in the response.

## Risks and Considerations

- Licensing: Validate RapidOCR and ONNXRuntime licenses for your deployment.
- Resource usage: OCR is compute-heavy; running OCR per cue may become a bottleneck for long videos. Prefer batch OCR and caching.
- Output format expectations: SRT input becomes ASS output in the current implementation, which may not align with downstream requirements. Consider format-preserving behavior or clarify expectations in API docs.

## Conclusion

The module provides a solid starting point for automatic subtitle repositioning using OCR but requires targeted fixes and dependency updates before integration. After addressing the issues and adding a simple API route, it can be integrated either as a standalone endpoint or as an optional post-processing step in existing workflows.
