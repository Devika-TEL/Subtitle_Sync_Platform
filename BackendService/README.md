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

### Correction and Alignment with Optional Gemini SDK

The standalone alignment module (BackendService/subtitle_alignment_standalone.py) supports optional integration with the official Google Gemini SDK (google-generativeai). No raw HTTP requests are used—only SDK calls.

Enable Gemini usage by configuring the following environment variables (provided by the orchestrator; do not edit .env here):
- GEMINI_ENABLED=1
- GEMINI_API_KEY=<your-google-api-key>
- GEMINI_MODEL_NAME=gemini-1.5-flash   # or gemini-1.5-pro, etc.

Behavior:
- If the SDK is installed and environment is enabled, subtitle text correction may use Gemini for conservative grammar/punctuation improvements while respecting OTT constraints.
- Alignment scoring can optionally consult Gemini for a small semantic similarity hint when hybrid mode is enabled.
- If the SDK is not installed or env is not set, the module continues using only local heuristics.

Note:
- To install the SDK in your environment: pip install google-generativeai
- The code will gracefully skip Gemini usage if the SDK is missing; no runtime error will be raised.

Notes:
- Transcript-aware alignment uses token-based similarity (and optionally RapidFuzz/sentence-transformers if installed locally).
- Text correction uses local normalization, optional spaCy entity protection, and language-tool-python where available. If optional packages are missing, it falls back to heuristics.
- Language support varies with available tokenizers/models. Languages with complex segmentation may see limited improvements under heuristic fallback.

Example (local):
python BackendService/subtitle_alignment_standalone.py

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
