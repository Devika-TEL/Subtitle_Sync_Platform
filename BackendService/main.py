import os
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from uuid import uuid4
from pathlib import Path

app = FastAPI(
    title="Subtitle Sync Platform Backend",
    description="APIs for subtitle correction and generation workflows, powered by LLM",
    version="0.1.0",
    openapi_tags=[
        {"name": "Correction", "description": "Subtitle correction and compliance check endpoints"},
        {"name": "Generation", "description": "Subtitle and subtitle translation generation endpoints"},
    ],
)

# Enable CORS for local and production frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Set to specific domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

UPLOAD_BASE = Path(os.getenv("UPLOAD_DIR", "uploads"))
UPLOAD_BASE.mkdir(parents=True, exist_ok=True)

def save_upload_file(upload_file: UploadFile, subdir: Path, filename: Optional[str] = None) -> Path:
    """Utility to save UploadFile to disk and return path."""
    final_filename = filename or upload_file.filename or f"uploaded_{uuid4().hex}"
    out_path = subdir / final_filename
    with out_path.open("wb") as buffer:
        buffer.write(upload_file.file.read())
    return out_path

# PUBLIC_INTERFACE
@app.post("/api/correction", tags=["Correction"], summary="Upload video & subtitle for correction", status_code=201)
async def correction_upload(
    video_file: UploadFile = File(..., description="Video file for subtitle correction."),
    subtitle_file: UploadFile = File(..., description="Subtitle file to be checked and corrected."),
):
    """
    Accepts a video file and a subtitle file, saves files, and starts subtitle correction workflow.
    Returns a job identifier for status tracking.

    Args:
        video_file: UploadFile (required) - Video file for correction
        subtitle_file: UploadFile (required) - Subtitle file to check
    
    Returns:
        JSON object containing job_id and message
    """
    job_id = uuid4().hex
    job_dir = UPLOAD_BASE / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    video_path = save_upload_file(video_file, job_dir, "video" + Path(video_file.filename).suffix)
    subtitle_path = save_upload_file(subtitle_file, job_dir, "subtitle" + Path(subtitle_file.filename).suffix)

    # Placeholder: Call to correction logic/queue, LLM etc.
    # e.g., enqueue_correction_task(job_id, video_path, subtitle_path)
    # [LLM and compliance business logic to be implemented here]

    return JSONResponse({
        "job_id": job_id,
        "status": "PENDING",
        "message": "Files uploaded. Correction job queued.",
        "video_path": str(video_path),
        "subtitle_path": str(subtitle_path)
    }, status_code=status.HTTP_201_CREATED)

# PUBLIC_INTERFACE
@app.post("/api/generation", tags=["Generation"], summary="Upload video for subtitle generation", status_code=201)
async def generation_upload(
    video_file: UploadFile = File(..., description="Video file for generating subtitles."),
    language: str = Form(..., description="Output subtitle language (ISO code, e.g., 'en', 'es')."),
):
    """
    Accepts a video file and language code, stores them, and starts subtitle generation workflow.
    Returns a job identifier for tracking.

    Args:
        video_file: UploadFile (required) - Video file for subtitle generation
        language: str (required) - Target output language code
    
    Returns:
        JSON object containing job_id and message
    """
    job_id = uuid4().hex
    job_dir = UPLOAD_BASE / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    video_path = save_upload_file(video_file, job_dir, "video" + Path(video_file.filename).suffix)

    # Save the language selection in a metadata file
    meta_path = job_dir / "job_meta.txt"
    meta_path.write_text(f"language={language}")

    # Placeholder: Call to generation logic/queue, LLM etc.
    # e.g., enqueue_generation_task(job_id, video_path, language)
    # [LLM subtitle/translation logic to be implemented here]

    return JSONResponse({
        "job_id": job_id,
        "status": "PENDING",
        "message": "File uploaded. Generation job queued.",
        "video_path": str(video_path),
        "requested_language": language,
    }, status_code=status.HTTP_201_CREATED)

# PUBLIC_INTERFACE
@app.get("/api/health", tags=["Utility"], summary="Health check", description="Returns 200 OK if backend is live.")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}

# PUBLIC_INTERFACE
@app.get("/api/openapi.json", include_in_schema=False)
async def custom_openapi():
    """Serve OpenAPI spec at the canonical path for tools."""
    return app.openapi()

# --- LLM Integration Points ---
def placeholder_llm_integration(*args, **kwargs):
    """
    Placeholder for future LLM functionality.
    Implement subtitle correction/generation logic using LLMs here.
    """
    pass
