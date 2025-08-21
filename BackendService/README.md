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
