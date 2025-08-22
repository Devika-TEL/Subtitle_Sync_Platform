# Backend Service - Subtitle Sync Platform

FastAPI service providing endpoints for subtitle quality check, generation, translation, and validation.

## Run locally

1. Create a Python venv and install dependencies:
   pip install -r requirements.txt

2. Set environment variables (or create a .env in your orchestrated environment):
   - BACKEND_HOST (default: 0.0.0.0)
   - BACKEND_PORT (default: 8000)
   - DEBUG (default: false)
   - CORS_ALLOW_ORIGINS (default: *)
   - UPLOAD_DIR (default: ./uploads)
   - PROCESSED_DIR (default: ./processed)
   - WORK_DIR (default: ./work)
   - LLM_PROVIDER (optional)
   - LLM_API_KEY (optional)
   - STT_PROVIDER (optional)
   - STT_API_KEY (optional)

3. Start the service:
   python start.py

4. Open the docs:
   http://localhost:8000/docs

## Endpoints

- GET /health
- POST /subtitles/quality-check
- POST /subtitles/generate
- POST /subtitles/translate
- POST /subtitles/validate
- GET /jobs/{job_id}
- GET /files/{filename}
- GET /docs/websocket

## Notes

- This reference implementation uses an in-memory job queue for demo purposes.
- Subtitle processing functions are deterministic stubs for CI and can be replaced with integrations to real STT/LLM and subtitle libraries later.
- For the standalone subtitle generation script (standalone_subtitle_generation.py), translations are performed using Google Gemini when the target language differs from the detected language. You must set GEMINI_API_KEY in your environment or .env for translation to work. Example .env:
  GEMINI_API_KEY=your_api_key_here

## Programmatic API: Reposition Subtitles to Avoid Hardcoded Text

A new utility entry point is available for developers who want to programmatically reposition subtitles to avoid overlap with burnt-in (hardcoded) text:

- Function: reposition_subtitles_based_on_hardcoded_text(video_path, subtitle_path, output_path=None, processed_dir="./processed", sample_rate=1.0)
- Supported Formats: SRT, ASS/SSA, VTT
- Behavior:
  - Analyzes the video for persistent hardcoded text and chooses a safer subtitle position (top/bottom) per file.
  - SRT: Inserts a comment hint "NOTE: position=<top|bottom>" within each block (portable hint). 
  - VTT: Adds/updates cue settings (e.g., line:0 for top, line:90 for bottom).
  - ASS/SSA: Attempts to adjust style alignment (top=8, bottom=2); if style update is not possible, appends a note comment.

Example usage:
```python
from subtitle_reposition import reposition_subtitles_based_on_hardcoded_text

output_path = reposition_subtitles_based_on_hardcoded_text(
    video_path="input.mp4",
    subtitle_path="captions.srt",
    output_path=None,            # write into processed dir
    processed_dir="./processed",
    sample_rate=1.0,             # FPS for OCR sampling (stubbed here)
)
print("Repositioned file at:", output_path)
```

Command-line:
```bash
python -m Subtitle_Sync_Platform.BackendService.subtitle_reposition --video input.mp4 --subs captions.ass --processed-dir ./processed
```

Implementation note: The OCR routine is stubbed for CI determinism. Replace it with RapidOCR-based frame analysis in production.
