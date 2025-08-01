import os
from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, status, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from typing import List, Optional
from jose import JWTError, jwt
from datetime import datetime, timedelta
import logging

from auth import (
    authenticate_user, create_access_token, get_current_user, get_admin_user, User, Token, get_password_hash
)
from database import (
    get_db, create_user, get_user_by_username, JobCreate, get_job, list_jobs, create_job, update_job_status,
    list_users, list_files, create_file_entry, get_file_by_id
)
from job_processor import (
    process_upload_job, process_sync_job, process_generation_job, process_translation_job, process_compliance_job
)
from subtitle_processor import (
    detect_subtitle_format, validate_subtitle_file
)
from file_utils import (
    save_upload_file, get_file_path, delete_file_if_exists
)
from config import (
    settings, ACCESS_TOKEN_EXPIRE_MINUTES, ALGORITHM
)

# PUBLIC_INTERFACE
app = FastAPI(
    title="BackendService - Subtitle Sync Platform",
    description="API for subtitle-audio sync, subtitle generation, translation, validation, compliance, and management.",
    version="1.0.0",
    openapi_tags=[
        {'name': 'user', 'description': 'User-level API'},
        {'name': 'admin', 'description': 'Admin/audit/compliance endpoints'},
        {'name': 'external', 'description': 'API for external apps/integrations'},
        {'name': 'jobs', 'description': 'Async job management'},
        {'name': 'files', 'description': 'Upload/Download and file management'},
    ]
)

# CORS config for frontend/external API use
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOW_ORIGINS or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Set up centralized logging
logger = logging.getLogger("uvicorn")
logger.setLevel(logging.INFO)

# --- User Authentication Endpoints ---

# PUBLIC_INTERFACE
@app.post("/auth/register", summary="Register new User", tags=["user"], response_model=User)
async def register_user(
    username: str = Form(..., description="Unique username"),
    password: str = Form(..., description="Password"),
    db=Depends(get_db)
):
    """Register new user account."""
    if get_user_by_username(db, username):
        raise HTTPException(status_code=409, detail="Username already taken.")
    user = create_user(db, username=username, hashed_password=get_password_hash(password))
    return user

# PUBLIC_INTERFACE
@app.post('/auth/login', summary="Login and get JWT access token", tags=["user"], response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db=Depends(get_db)):
    """Authenticate and return a JWT token for use in further requests."""
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# --- Core API Endpoints ---

# PUBLIC_INTERFACE
@app.post("/upload/video", summary="Upload Video", tags=["files"])
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Video File"),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """
    Upload a video file to start a new subtitle processing job.
    """
    file_id, file_path = save_upload_file(file, "videos")
    job = create_job(db, JobCreate(user_id=current_user.id, file_id=file_id, type="video_upload"))
    background_tasks.add_task(process_upload_job, job.id, file_path, db)
    return {"job_id": job.id, "status": "processing started"}

# PUBLIC_INTERFACE
@app.post("/upload/subtitle", summary="Upload Subtitle", tags=["files"])
async def upload_subtitle(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Subtitle File (SRT, VTT, etc.)"),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """
    Upload a subtitle file for validation, correction, or further processing.
    """
    file_id, file_path = save_upload_file(file, "subtitles")
    job = create_job(db, JobCreate(user_id=current_user.id, file_id=file_id, type="subtitle_upload"))
    background_tasks.add_task(process_sync_job, job.id, file_path, db)
    return {"job_id": job.id, "status": "processing started"}

# PUBLIC_INTERFACE
@app.post("/jobs/subtitle/generate", summary="Generate Subtitles with LLM", tags=["jobs"])
async def generate_subtitles(
    background_tasks: BackgroundTasks,
    video_file_id: str = Form(..., description="FileID for video"),
    language: str = Form(..., description="Target language for subtitle"),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """
    Request subtitle generation in a chosen language using LLM.
    """
    job = create_job(db, JobCreate(user_id=current_user.id, file_id=video_file_id, type="generate_subtitle"))
    background_tasks.add_task(process_generation_job, job.id, video_file_id, language, db)
    return {"job_id": job.id, "status": "generation started"}

# PUBLIC_INTERFACE
@app.post("/jobs/subtitle/translate", summary="Translate Subtitles to Another Language", tags=["jobs"])
async def translate_subtitles(
    background_tasks: BackgroundTasks,
    subtitle_file_id: str = Form(..., description="FileID for subtitle"),
    target_language: str = Form(..., description="Target language"),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """
    Translate subtitle file to another language using LLM.
    """
    job = create_job(db, JobCreate(user_id=current_user.id, file_id=subtitle_file_id, type="translate_subtitle"))
    background_tasks.add_task(process_translation_job, job.id, subtitle_file_id, target_language, db)
    return {"job_id": job.id, "status": "translation started"}

# PUBLIC_INTERFACE
@app.post("/jobs/compliance/check", summary="Run Compliance Check", tags=["jobs"])
async def compliance_check(
    background_tasks: BackgroundTasks,
    subtitle_file_id: str = Form(..., description="FileID for subtitle"),
    platform: Optional[str] = Form(None, description="Compliance platform/standard"),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """
    Run compliance checks on subtitle file (OTT/accessibility).
    """
    job = create_job(db, JobCreate(user_id=current_user.id, file_id=subtitle_file_id, type="compliance_check"))
    background_tasks.add_task(process_compliance_job, job.id, subtitle_file_id, platform, db)
    return {"job_id": job.id, "status": "compliance check started"}

# PUBLIC_INTERFACE
@app.get("/jobs/{job_id}/status", summary="Check Job Status", tags=["jobs"])
async def job_status(job_id: str, current_user: User = Depends(get_current_user), db=Depends(get_db)):
    """
    Retrieve job status and logs.
    """
    job = get_job(db, job_id)
    if not job or job.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job_id": job.id, "status": job.status, "result": job.result, "logs": job.logs}

# PUBLIC_INTERFACE
@app.get("/files/{file_id}/download", summary="Download Processed File", tags=["files"])
async def download_file(file_id: str, current_user: User = Depends(get_current_user), db=Depends(get_db)):
    """
    Download a processed subtitle or video file.
    """
    f = get_file_by_id(db, file_id)
    if not f or (f.user_id != current_user.id and current_user.role != "admin"):
        raise HTTPException(status_code=404, detail="File not found")
    file_path = get_file_path(f.path)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=410, detail="File no longer available")
    return FileResponse(file_path, filename=os.path.basename(file_path))

# --- Admin/Audit/Compliance Endpoints ---

# PUBLIC_INTERFACE
@app.get("/admin/audit/jobs", summary="List All Jobs (Admin)", tags=["admin"])
async def admin_list_jobs(current_user: User = Depends(get_admin_user), db=Depends(get_db)):
    """
    Admin: List all jobs in the system, for audit/compliance.
    """
    jobs = list_jobs(db)
    return jobs

# PUBLIC_INTERFACE
@app.get("/admin/audit/users", summary="List All Users (Admin)", tags=["admin"])
async def admin_list_users(current_user: User = Depends(get_admin_user), db=Depends(get_db)):
    """
    Admin: List all users in the system.
    """
    users = list_users(db)
    return users

# PUBLIC_INTERFACE
@app.get("/admin/audit/files", summary="List All Files (Admin)", tags=["admin"])
async def admin_list_files(current_user: User = Depends(get_admin_user), db=Depends(get_db)):
    """
    Admin: List all uploaded and processed files.
    """
    files = list_files(db)
    return files

# PUBLIC_INTERFACE
@app.get("/health", summary="Healthcheck endpoint", tags=["user"])
async def healthcheck():
    return {"status": "ok", "message": "BackendService is running."}

# --- External API Hook Example ---

# PUBLIC_INTERFACE
@app.post("/external/webhook", summary="External API Hook", tags=["external"])
async def external_webhook(event: dict):
    """
    Accept event hooks from external apps/services (for demo).
    """
    logger.info(f"Received external event: {event}")
    return {"result": "ok"}

# --- OpenAPI and WebSocket Usage Docs ---

# PUBLIC_INTERFACE
@app.get("/docs/ws", summary="WebSocket Usage Help", tags=["user"])
def websocket_docs():
    """
    WebSocket usage is currently not implemented. Poll /jobs/{job_id}/status for job updates.
    """
    return {
        "message": "WebSocket real-time updates not yet supported. Poll /jobs/{job_id}/status for async job updates.",
        "supported": False
    }

# --- Error handler example ---

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Unhandled Error: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"message": "Internal server error."}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
