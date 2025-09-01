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

### Gemini LLM Integration (optional)

We now support optional Gemini (Google Generative AI) usage for transcript-aware subtitle correction within the standalone alignment module.

Where it’s used:
- BackendService/subtitle_alignment_standalone.py
  - Function write_corrected_alignment(...) will attempt an LLM correction pass for each aligned cue if GEMINI_API_KEY is set. If the key is not set or the API call fails, it falls back gracefully to local heuristics and grammar/punctuation fixes.

How to enable:
- Set the environment variable GEMINI_API_KEY with your real key (do not commit secrets).
- No code changes required.

Example (local):
export GEMINI_API_KEY="your-real-api-key"
python BackendService/subtitle_alignment_standalone.py

Implementation details:
- The module uses a minimal requests-based REST call to:
  https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=$GEMINI_API_KEY
- Request includes a concise prompt with a transcript excerpt and the current cue text. The LLM is instructed to return ONLY the corrected subtitle text.
- Safe by default: if requests is not available or any error occurs, the function returns None and the pipeline continues without LLM output.

Security:
- No secrets are hardcoded. Ensure GEMINI_API_KEY is supplied at runtime via environment or your deployment’s secret manager.

### Alignment modes and configuration

The alignment utility supports two modes:
- Simple (default): fast, no heavy dependencies. Uses token Jaccard similarity.
- Advanced (hybrid): combines RapidFuzz and sentence-transformers semantic similarity, with robust timing correction.

Toggles are read from env via config.py or can be passed directly to the function:
- ALIGNMENT_EMBEDDINGS_ENABLED=true|false
- ALIGNMENT_MODEL_NAME=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
- FUZZY_W_PARTIAL=0.4
- FUZZY_W_TOKEN=0.4
- FUZZY_W_EMB=0.2
- DEFAULT_CHARS_PER_SEC=15
- MAX_CUE_DURATION_MS=6000
- DELAY_THRESHOLD_MS=500

Programmatic usage:
```python
from Subtitle_Sync_Platform.BackendService.subtitle_alignment_simple import align_subtitles_to_transcript

aligned = align_subtitles_to_transcript(
    transcript_segments,
    subtitle_cues,
    enable_hybrid=True,  # or set env ALIGNMENT_EMBEDDINGS_ENABLED=1
    embedding_model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    fuzzy_weights={"rapidfuzz_partial":0.4,"rapidfuzz_token":0.4,"embedding":0.2},
    default_chars_per_sec=15.0,
    max_cue_duration=6.0,
    delayed_start_threshold=0.5,
)
```

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
