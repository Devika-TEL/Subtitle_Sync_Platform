import os
from fastapi import (
    FastAPI, 
    File, 
    UploadFile, 
    BackgroundTasks, 
    Depends, 
    HTTPException, 
    status,
    Query,
    Security,
    Request
)
from fastapi.security import OAuth2PasswordBearer, SecurityScopes
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union
from uuid import UUID, uuid4
from enum import Enum
from starlette.responses import FileResponse, JSONResponse

# External module imports (assume partial implementation, stubs for core logic)
from auth import get_current_user, User, Role
from file_utils import allowed_video_types, allowed_subtitle_types
from job_processor import submit_job, get_job_status, get_job_result, list_jobs, cancel_job
from subtitle_processor import (
    check_quality, auto_correct_subtitles, generate_subtitles_llm, 
    translate_subtitles, validate_subtitle_format, convert_subtitle_format,
    get_supported_languages, get_supported_formats, compliance_report
)
from subtitle_correction import detect_and_fix_errors
from database import (
    log_audit, get_audit_logs, log_compliance, get_compliance_reports,
    get_monitoring_stats
)
from config import get_settings

# CONFIGURATION
settings = get_settings()

# PROJECT METADATA AND TAGS
tags_metadata = [
    {"name": "UserUpload", "description": "Endpoints for end-user file upload and download"},
    {"name": "SubtitleProcessing", "description": "Endpoints for processing/auto-correct/subtitle generation"},
    {"name": "Translation", "description": "Endpoints for multi-language subtitle translation"},
    {"name": "JobManagement", "description": "Endpoints for managing and tracking jobs"},
    {"name": "Admin", "description": "Admin endpoints: audit logs, compliance, system monitoring"},
    {"name": "ExternalAPI", "description": "API access for programmatic/external app integrations"}
]

app = FastAPI(
    title="Audio-Subtitle-Sync Backend Service",
    description="Core backend for subtitle-audio sync, subtitle generation/translation, compliance, and more.",
    version="1.0.0",
    openapi_tags=tags_metadata
)

# CORS (adjust as needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# === MODELS ===

class UploadResponse(BaseModel):
    job_id: UUID = Field(..., description="Asynchronous Job ID")
    message: str = Field(..., description="Acknowledgement message")

class JobStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"

class JobInfo(BaseModel):
    job_id: UUID
    status: JobStatus
    progress: Optional[int] = Field(None, description="Progress percentage (if applicable)")
    result_url: Optional[str] = Field(None, description="Downloadable result file if completed")
    detail: Optional[str] = Field(None, description="Detailed status or error")

class QualityCheckResult(BaseModel):
    compliant: bool
    issues: List[str]
    auto_corrected: Optional[bool] = None
    download_url: Optional[str] = None

class SubtitleFormat(str, Enum):
    srt = "srt"
    vtt = "vtt"
    ass = "ass"
    # Extendable for more formats

class SubtitleActionRequest(BaseModel):
    job_id: UUID
    target_language: Optional[str] = None
    format: Optional[SubtitleFormat] = None

class ComplianceReport(BaseModel):
    compliant: bool
    issues: List[str]
    details: Optional[Dict[str, Any]]

class AuditLogEntry(BaseModel):
    timestamp: str
    user: str
    action: str
    metadata: Optional[Dict[str, Any]]

class MonitoringStats(BaseModel):
    uptime: float
    cpu_usage: float
    queue_length: int
    disk_space: float

# === DEPENDENCY INJECTION, ROLE CHECKS ===

# PUBLIC_INTERFACE
def require_role(required: Role):
    """Dependency to require a user role"""
    def checker(user: User = Depends(get_current_user)):
        if user.role != required:
            raise HTTPException(status_code=403, detail="Insufficient privileges")
        return user
    return checker

# === ENDPOINTS ===

# --- Upload Endpoints (User & API) ---

# PUBLIC_INTERFACE
@app.post(
    "/upload/video", 
    response_model=UploadResponse, 
    summary="Upload a video file",
    tags=["UserUpload", "ExternalAPI"]
)
async def upload_video(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    background_tasks: BackgroundTasks = Depends()
):
    """
    Upload a video file for subtitle processing.
    """
    # Validate video type and handle uploads
    if not allowed_video_types(file.filename):
        raise HTTPException(400, "Unsupported video file type")
    job_id = uuid4()
    await submit_job(file=file, job_id=job_id, user=user, task_type="video_upload", background_tasks=background_tasks)
    log_audit(user.username, "upload_video", {"filename": file.filename, "job_id": str(job_id)})
    return UploadResponse(job_id=job_id, message="Video uploaded and processing started.")

# PUBLIC_INTERFACE
@app.post(
    "/upload/subtitle",
    response_model=UploadResponse,
    summary="Upload a subtitle file",
    tags=["UserUpload", "ExternalAPI"]
)
async def upload_subtitle(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    background_tasks: BackgroundTasks = Depends()
):
    """
    Upload a subtitle file for validation, correction, or translation.
    """
    if not allowed_subtitle_types(file.filename):
        raise HTTPException(400, "Unsupported subtitle file type")
    job_id = uuid4()
    await submit_job(file=file, job_id=job_id, user=user, task_type="subtitle_upload", background_tasks=background_tasks)
    log_audit(user.username, "upload_subtitle", {"filename": file.filename, "job_id": str(job_id)})
    return UploadResponse(job_id=job_id, message="Subtitle uploaded and processing started.")

# --- Processing & Quality Check Endpoints ---

# PUBLIC_INTERFACE
@app.post(
    "/process/quality_check",
    response_model=QualityCheckResult,
    summary="Perform subtitle-audio quality check and correction",
    tags=["SubtitleProcessing", "ExternalAPI"]
)
async def process_quality_check(
    job_id: UUID,
    auto_correct: bool = Query(False, description="Auto-correct detected issues"),
    user: User = Depends(get_current_user),
    background_tasks: BackgroundTasks = Depends()
):
    """
    Run quality check on submitted subtitle with its video. Optionally auto-correct issues.
    """
    result = check_quality(job_id)
    if auto_correct and result["issues"]:
        background_tasks.add_task(auto_correct_subtitles, job_id=job_id, user=user)
        result["auto_corrected"] = True
        log_audit(user.username, "auto_correct_requested", {"job_id": str(job_id)})
    else:
        result["auto_corrected"] = False
    log_audit(user.username, "quality_check", {"job_id": str(job_id), "issues": result.get("issues", [])})
    return QualityCheckResult(**result)

# PUBLIC_INTERFACE
@app.post(
    "/process/generate_subtitles",
    response_model=UploadResponse,
    summary="Generate subtitles using LLM from uploaded video",
    tags=["SubtitleProcessing", "ExternalAPI"]
)
async def generate_subtitles(
    job_id: UUID, 
    language: str = Query(..., description="Target language code for subtitle generation"),
    user: User = Depends(get_current_user),
    background_tasks: BackgroundTasks = Depends()
):
    """
    Trigger subtitle generation with LLM service.
    """
    background_tasks.add_task(generate_subtitles_llm, job_id=job_id, language=language, user=user)
    log_audit(user.username, "generate_subtitles_llm", {"job_id": str(job_id), "language": language})
    return UploadResponse(job_id=job_id, message="Subtitle generation started.")

# PUBLIC_INTERFACE
@app.post(
    "/process/translate",
    response_model=UploadResponse,
    summary="Translate subtitles to selected language",
    tags=["Translation", "ExternalAPI"]
)
async def translate_subtitle(
    req: SubtitleActionRequest,
    user: User = Depends(get_current_user),
    background_tasks: BackgroundTasks = Depends()
):
    """
    Translate subtitle in job to another language (async).
    """
    if req.target_language not in get_supported_languages():
        raise HTTPException(400, "Unsupported target language")
    background_tasks.add_task(translate_subtitles, job_id=req.job_id, target_language=req.target_language, user=user)
    log_audit(user.username, "translate_subtitles", {"job_id": str(req.job_id), "target_language": req.target_language})
    return UploadResponse(job_id=req.job_id, message=f"Translation to {req.target_language} started.")

# --- Subtitle Management & Download ---

# PUBLIC_INTERFACE
@app.get(
    "/subtitle/download/{job_id}",
    summary="Download processed/corrected/generated subtitle file",
    tags=["UserUpload", "ExternalAPI"]
)
async def download_subtitle(job_id: UUID, user: User = Depends(get_current_user)):
    """
    Download output subtitle file for a given job.
    """
    file_path = get_job_result(job_id)
    if file_path is None or not os.path.exists(file_path):
        raise HTTPException(404, "Subtitle file not ready or missing")
    log_audit(user.username, "download_subtitle", {"job_id": str(job_id)})
    return FileResponse(file_path, media_type='text/plain', filename=os.path.basename(file_path))

# PUBLIC_INTERFACE
@app.post(
    "/subtitle/convert_format",
    response_model=UploadResponse,
    summary="Convert subtitle file format",
    tags=["SubtitleProcessing"]
)
async def convert_format(
    req: SubtitleActionRequest,
    user: User = Depends(get_current_user),
    background_tasks: BackgroundTasks = Depends()
):
    """
    Convert subtitle to requested format.
    """
    if req.format not in get_supported_formats():
        raise HTTPException(400, "Unsupported subtitle format")
    background_tasks.add_task(convert_subtitle_format, job_id=req.job_id, target_format=req.format, user=user)
    log_audit(user.username, "convert_subtitle_format", {"job_id": str(req.job_id), "format": req.format})
    return UploadResponse(job_id=req.job_id, message=f"Conversion to {req.format} started.")

# --- Asynchronous Job Management ---

# PUBLIC_INTERFACE
@app.get(
    "/jobs/status/{job_id}",
    response_model=JobInfo,
    summary="Get job processing status",
    tags=["JobManagement", "ExternalAPI"]
)
async def job_status(job_id: UUID, user: User = Depends(get_current_user)):
    """
    Get the current status of an asynchronous processing job.
    """
    status_info = get_job_status(job_id)
    if not status_info:
        raise HTTPException(404, "Job not found")
    return JobInfo(**status_info)

# PUBLIC_INTERFACE
@app.get(
    "/jobs/list",
    response_model=List[JobInfo],
    summary="List all jobs for current user",
    tags=["JobManagement"]
)
async def list_my_jobs(user: User = Depends(get_current_user)):
    """
    List all jobs submitted by the current user.
    """
    return list_jobs(user=user)

# PUBLIC_INTERFACE
@app.post(
    "/jobs/cancel",
    summary="Cancel an ongoing job (if possible)",
    response_model=UploadResponse,
    tags=["JobManagement"]
)
async def cancel_my_job(job_id: UUID, user: User = Depends(get_current_user)):
    """
    Attempt to cancel a job owned by the requesting user.
    """
    cancelled = cancel_job(job_id, user=user)
    if not cancelled:
        raise HTTPException(400, "Unable to cancel the job.")
    log_audit(user.username, "cancel_job", {"job_id": str(job_id)})
    return UploadResponse(job_id=job_id, message="Job cancelled.")

# --- Admin & Compliance ---

# PUBLIC_INTERFACE
@app.get(
    "/admin/audit_logs",
    response_model=List[AuditLogEntry],
    summary="Retrieve system audit logs",
    tags=["Admin"]
)
async def get_audit_log_api(admin: User = Depends(require_role(Role.admin))):
    """
    Admin endpoint to retrieve audit logs (restricted access).
    """
    return get_audit_logs()

# PUBLIC_INTERFACE
@app.get(
    "/admin/compliance",
    response_model=List[ComplianceReport],
    summary="Compliance reports & issues",
    tags=["Admin"]
)
async def get_compliance_reports_api(admin: User = Depends(require_role(Role.admin))):
    """
    List compliance issues and reports for audit purposes.
    """
    return get_compliance_reports()

# PUBLIC_INTERFACE
@app.get(
    "/admin/monitoring",
    response_model=MonitoringStats,
    summary="System monitoring and health check",
    tags=["Admin"]
)
async def system_monitoring(admin: User = Depends(require_role(Role.admin))):
    """
    Current system health metrics and stats.
    """
    return get_monitoring_stats()

# --- Utils ---

# PUBLIC_INTERFACE
@app.get(
    "/formats/list",
    response_model=List[str],
    summary="Supported subtitle formats",
    tags=["SubtitleProcessing"]
)
async def get_formats():
    """
    List all supported subtitle formats.
    """
    return get_supported_formats()

# PUBLIC_INTERFACE
@app.get(
    "/languages/list",
    response_model=List[str],
    summary="Supported languages for subtitle generation & translation",
    tags=["Translation"]
)
async def get_languages():
    """
    List all supported subtitle languages.
    """
    return get_supported_languages()

# --- OpenAPI Helper for WebSocket (future) ---
@app.get(
    "/help/websocket",
    summary="Usage note: WebSocket endpoints (if enabled in future)",
    tags=["ExternalAPI"]
)
async def websocket_usage_help():
    return JSONResponse({
        "note": "There are currently no websocket endpoints enabled. All processing is asynchronous and accessible via REST endpoints. Future releases may include websocket connections for real-time event updates."
    })
