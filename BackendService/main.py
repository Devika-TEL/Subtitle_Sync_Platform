"""
FastAPI Backend Service for Subtitle-Audio Synchronization Platform.

This service provides endpoints for:
- Subtitle quality check and auto-correction
- Subtitle generation from video
- Subtitle translation
- Subtitle validation and format conversion
- Job status querying and file retrieval

The service is configured via environment variables (see config.py).

Developer note:
- A programmatic utility is available in subtitle_reposition.py for repositioning subtitles
  to avoid hardcoded text using OCR-based analysis. See README for usage.
"""

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from typing import Optional, List, Dict
from pydantic import BaseModel, Field
import os
import uuid
import shutil
from pathlib import Path

from config import get_settings, Settings
from middleware import add_process_time_header
from file_utils import (
    save_temp_upload,
    ensure_dir,
    allowed_subtitle_extension,
    guess_subtitle_format,
)
from subtitle_processor import (
    run_quality_check_and_correct,
    generate_subtitles_for_video,
    translate_subtitles,
    validate_subtitles,
)
from subtitle_correction import apply_additional_compliance_fixes
from job_processor import JobQueue, JobStatus
# Removed transcript alignment endpoint to decouple from web layer.

# Initialize FastAPI app with metadata and tags for OpenAPI docs
app = FastAPI(
    title="Subtitle Sync Platform - Backend Service",
    description=(
        "Backend API for subtitle-audio synchronization, subtitle generation, "
        "translation, and validation. Supports multiple formats and languages. "
        "Use these endpoints from the Frontend Web Dashboard or programmatically."
    ),
    version="1.0.0",
    openapi_tags=[
        {"name": "health", "description": "Health and service metadata"},
        {"name": "subtitles", "description": "Subtitle processing operations"},
        {"name": "jobs", "description": "Asynchronous job management"},
        {"name": "files", "description": "Access processed files"},
        {"name": "test", "description": "Simple testing utilities for connectivity"},
    ],
)

# CORS configuration via env
settings: Settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add process time header middleware
app.middleware("http")(add_process_time_header)

# Ensure working directories
ensure_dir(settings.UPLOAD_DIR)
ensure_dir(settings.PROCESSED_DIR)
ensure_dir(settings.WORK_DIR)

# Initialize an in-memory job queue (can be replaced with Redis/RQ, Celery, etc.)
job_queue = JobQueue(process_dir=settings.PROCESSED_DIR)


class LanguagePair(BaseModel):
    source: str = Field(..., description="Source language code (ISO-639-1) e.g., 'en'")
    target: str = Field(..., description="Target language code (ISO-639-1) e.g., 'es'")


class GenerationRequest(BaseModel):
    language: Optional[str] = Field(
        None, description="Language code for generation (defaults to auto-detect)"
    )
    translate_to: Optional[List[str]] = Field(
        None,
        description="Optional list of language codes to also translate generated subtitles into",
    )
    model_hint: Optional[str] = Field(
        None, description="Optional model hint for LLM/STT provider"
    )


class TranslationRequest(BaseModel):
    source_language: Optional[str] = Field(
        None, description="Source language code if known, otherwise auto-detect"
    )
    target_language: str = Field(..., description="Target language code (ISO-639-1)")
    model_hint: Optional[str] = Field(
        None, description="Optional model hint for translation provider"
    )


class ValidationOptions(BaseModel):
    max_chars_per_line: Optional[int] = Field(
        42, description="Maximum characters per line to validate against"
    )
    max_lines_per_caption: Optional[int] = Field(
        2, description="Maximum number of lines per caption"
    )
    min_caption_duration_ms: Optional[int] = Field(
        800, description="Minimum caption duration in milliseconds"
    )
    max_caption_duration_ms: Optional[int] = Field(
        8000, description="Maximum caption duration in milliseconds"
    )
    reading_speed_cps: Optional[int] = Field(
        17, description="Reading speed threshold in characters per second"
    )
    frame_rate: Optional[float] = Field(
        None, description="Frame rate to validate against if applicable"
    )
    language: Optional[str] = Field(
        None, description="Language code for spell/grammar checks, if used"
    )


class ValidationResponse(BaseModel):
    valid: bool = Field(..., description="Whether the subtitle file passed validation")
    issues: List[str] = Field(..., description="List of validation issues found, if any")
    format: Optional[str] = Field(None, description="Detected or specified subtitle format")


class JobResponse(BaseModel):
    job_id: str = Field(..., description="Identifier for the queued job")
    status: str = Field(..., description="Initial job status (e.g., QUEUED)")


class JobStatusResponse(BaseModel):
    job_id: str = Field(..., description="Job identifier")
    status: str = Field(..., description="Current job status")
    message: Optional[str] = Field(None, description="Optional status message")
    result_files: Optional[List[str]] = Field(
        None, description="List of file paths (relative) produced by the job"
    )


def _save_upload(file: UploadFile, dst_dir: str) -> Path:
    """
    Internal helper to save an UploadFile to a destination directory with a temp name.
    """
    ensure_dir(dst_dir)
    suffix = Path(file.filename or "").suffix
    temp_name = f"temp_{uuid.uuid4().hex}{suffix}"
    dst_path = Path(dst_dir) / temp_name
    with open(dst_path, "wb") as out:
        shutil.copyfileobj(file.file, out)
    return dst_path


@app.get("/health", tags=["health"], summary="Health check", description="Service liveness and configuration sanity probe.")
# PUBLIC_INTERFACE
def health() -> Dict[str, str]:
    """Return basic health info and environment-driven configuration status."""
    return {
        "status": "ok",
        "service": "Subtitle Sync Backend",
        "version": app.version,
        "upload_dir": str(settings.UPLOAD_DIR),
        "processed_dir": str(settings.PROCESSED_DIR),
    }


@app.post(
    "/subtitles/quality-check",
    tags=["subtitles"],
    summary="Run quality check and auto-correct a subtitle file",
    description="Upload a subtitle file with an optional related video file to perform quality checks and automatic corrections. Returns a job id.",
    response_model=JobResponse,
)
# PUBLIC_INTERFACE
async def subtitles_quality_check(
    subtitle_file: UploadFile = File(..., description="Subtitle file to validate and correct"),
    video_file: Optional[UploadFile] = File(None, description="Optional video for reference-based checks"),
    language: Optional[str] = Form(None, description="Language code if known"),
    enforce_ott_compliance: bool = Form(True, description="Apply OTT compliance rules"),
):
    """Enqueue a job to run quality checks and corrections on the provided subtitle file."""
    if not allowed_subtitle_extension(subtitle_file.filename):
        raise HTTPException(status_code=400, detail="Unsupported subtitle file extension.")

    # Save uploads
    sub_path = _save_upload(subtitle_file, settings.UPLOAD_DIR)
    vid_path = _save_upload(video_file, settings.UPLOAD_DIR) if video_file else None
    detected_format = guess_subtitle_format(sub_path)

    def job_fn():
        corrected = run_quality_check_and_correct(
            subtitle_path=str(sub_path),
            video_path=str(vid_path) if vid_path else None,
            language=language,
            enforce_ott=enforce_ott_compliance,
            processed_dir=str(settings.PROCESSED_DIR),
        )
        # Optional post-correction compliance adjustments
        final_path = apply_additional_compliance_fixes(corrected, processed_dir=str(settings.PROCESSED_DIR))
        return [os.path.relpath(final_path, settings.PROCESSED_DIR)]

    job_id = job_queue.enqueue(job_fn, description="quality_check", meta={"format": detected_format, "language": language})
    return JobResponse(job_id=job_id, status=JobStatus.QUEUED.value)


@app.post(
    "/subtitles/generate",
    tags=["subtitles"],
    summary="Generate subtitles from a video",
    description="Upload a video to generate subtitles. Optionally specify generation language and translations to produce.",
    response_model=JobResponse,
)
# PUBLIC_INTERFACE
async def subtitles_generate(
    video_file: UploadFile = File(..., description="Video file to generate subtitles from"),
    language: Optional[str] = Form(None, description="Language code for generation (auto-detect if omitted)"),
    translate_to: Optional[str] = Form(None, description="Comma-separated list of target languages for translation"),
    model_hint: Optional[str] = Form(None, description="Optional model hint for STT/LLM"),
):
    """Enqueue a job to generate subtitles in the requested language and optional translations."""
    vid_path = _save_upload(video_file, settings.UPLOAD_DIR)
    translate_list = [x.strip() for x in (translate_to or "").split(",") if x.strip()]

    def job_fn():
        generated_path = generate_subtitles_for_video(
            video_path=str(vid_path),
            language=language,
            processed_dir=str(settings.PROCESSED_DIR),
            model_hint=model_hint,
        )
        result_files = [os.path.relpath(generated_path, settings.PROCESSED_DIR)]
        # Translations
        for tgt in translate_list:
            translated = translate_subtitles(
                subtitle_path=generated_path,
                target_language=tgt,
                source_language=language,
                processed_dir=str(settings.PROCESSED_DIR),
                model_hint=model_hint,
            )
            result_files.append(os.path.relpath(translated, settings.PROCESSED_DIR))
        return result_files

    job_id = job_queue.enqueue(job_fn, description="generate", meta={"language": language, "translate_to": translate_list})
    return JobResponse(job_id=job_id, status=JobStatus.QUEUED.value)


@app.post(
    "/subtitles/translate",
    tags=["subtitles"],
    summary="Translate a subtitle file",
    description="Upload an existing subtitle file and request translation into a target language.",
    response_model=JobResponse,
)
# PUBLIC_INTERFACE
async def subtitles_translate(
    subtitle_file: UploadFile = File(..., description="Subtitle file to translate"),
    target_language: str = Form(..., description="Target language code"),
    source_language: Optional[str] = Form(None, description="Source language code if known"),
    model_hint: Optional[str] = Form(None, description="Optional model hint"),
):
    """Enqueue a job to translate a subtitle file into a target language."""
    if not allowed_subtitle_extension(subtitle_file.filename):
        raise HTTPException(status_code=400, detail="Unsupported subtitle file extension.")
    sub_path = _save_upload(subtitle_file, settings.UPLOAD_DIR)

    def job_fn():
        out_path = translate_subtitles(
            subtitle_path=str(sub_path),
            target_language=target_language,
            source_language=source_language,
            processed_dir=str(settings.PROCESSED_DIR),
            model_hint=model_hint,
        )
        return [os.path.relpath(out_path, settings.PROCESSED_DIR)]

    job_id = job_queue.enqueue(job_fn, description="translate", meta={"target": target_language, "source": source_language})
    return JobResponse(job_id=job_id, status=JobStatus.QUEUED.value)


@app.post(
    "/subtitles/validate",
    tags=["subtitles"],
    summary="Validate a subtitle file",
    description="Upload a subtitle file and validate it against configurable constraints and OTT rules.",
    response_model=ValidationResponse,
)
# PUBLIC_INTERFACE
async def subtitles_validate(
    subtitle_file: UploadFile = File(..., description="Subtitle file to validate"),
    max_chars_per_line: int = Form(42),
    max_lines_per_caption: int = Form(2),
    min_caption_duration_ms: int = Form(800),
    max_caption_duration_ms: int = Form(8000),
    reading_speed_cps: int = Form(17),
    frame_rate: Optional[float] = Form(None),
    language: Optional[str] = Form(None),
):
    """Validate a subtitle file with configurable parameters."""
    if not allowed_subtitle_extension(subtitle_file.filename):
        raise HTTPException(status_code=400, detail="Unsupported subtitle file extension.")
    sub_path = _save_upload(subtitle_file, settings.UPLOAD_DIR)
    detected_format = guess_subtitle_format(sub_path)

    issues = validate_subtitles(
        subtitle_path=str(sub_path),
        options=dict(
            max_chars_per_line=max_chars_per_line,
            max_lines_per_caption=max_lines_per_caption,
            min_caption_duration_ms=min_caption_duration_ms,
            max_caption_duration_ms=max_caption_duration_ms,
            reading_speed_cps=reading_speed_cps,
            frame_rate=frame_rate,
            language=language,
        ),
    )
    return ValidationResponse(valid=len(issues) == 0, issues=issues, format=detected_format)


@app.get(
    "/jobs/{job_id}",
    tags=["jobs"],
    summary="Get job status",
    description="Retrieve the status and results (if any) of a previously submitted job.",
    response_model=JobStatusResponse,
)
# PUBLIC_INTERFACE
def get_job_status(job_id: str):
    """Return the status of the job and any produced files."""
    status = job_queue.get_status(job_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatusResponse(
        job_id=job_id,
        status=status.status.value,
        message=status.message,
        result_files=status.result_files,
    )


@app.get(
    "/files/{filename}",
    tags=["files"],
    summary="Download a processed file",
    description="Download a file produced by a job. The filename should be obtained from the job status result_files.",
)
# PUBLIC_INTERFACE
def download_file(filename: str):
    """Send a processed file from the processed directory."""
    safe_path = Path(settings.PROCESSED_DIR) / filename
    if not safe_path.exists() or not safe_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path=str(safe_path), filename=safe_path.name, media_type="text/plain")


@app.get(
    "/docs/websocket",
    tags=["health"],
    summary="WebSocket usage note",
    description="Currently, this service does not expose WebSocket endpoints. For real-time updates, poll the job status endpoint or integrate a message broker.",
)
# PUBLIC_INTERFACE
def websocket_usage_note():
    """Provide documentation about real-time update strategy."""
    return {"websocket": "not-available", "strategy": "use /jobs/{job_id} polling for updates."}





@app.get(
    "/api/hello",
    tags=["test"],
    summary="Test connectivity endpoint",
    description="A simple endpoint to verify frontend-backend connectivity. Returns a static message.",
    response_description="A JSON object containing a hello message",
)
# PUBLIC_INTERFACE
def hello() -> Dict[str, str]:
    """Return a static hello message for quick connectivity testing.

    Returns:
        Dict[str, str]: JSON object with 'message': 'hello'
    """
    return {"message": "hello"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
