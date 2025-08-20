"""
FastAPI Backend Service for Subtitle Sync Platform
Provides comprehensive subtitle processing, validation, generation, and translation services.
"""

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends, BackgroundTasks, Query, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union
import sqlite3
import os
import tempfile
import shutil
import json
import uuid
import asyncio
from datetime import datetime, timedelta
import logging
from pathlib import Path
import subprocess
import re
import hashlib
import jwt
from subtitle_processor import subtitle_processor
from middleware import FileSizeMiddleware, CORSHeadersMiddleware
from auth import UserAuth, session_manager
from database import db_manager, get_db_connection
from job_processor import job_processor
from file_utils import file_manager
from subtitle_repositioning_code import process_subtitle

# Configure comprehensive logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('backend.log')
    ]
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    root_path="/proxy/8000",
    title="Subtitle Sync Backend API",
    description="Comprehensive API for subtitle-audio synchronization, generation, validation, correction, and translation services. Frontend dashboard available at: https://vscode-internal-29567-beta.beta01.cloud.kavia.ai:3001",
    version="1.0.0",
    openapi_tags=[
        {
            "name": "processing",
            "description": "Subtitle upload, processing, correction, and generation operations"
        },
        {
            "name": "subtitles",
            "description": "Subtitle file management, download, and translation operations"
        },
        {
            "name": "jobs",
            "description": "Job tracking and progress monitoring"
        },
        {
            "name": "auth",
            "description": "User authentication and registration"
        },
        {
            "name": "admin",
            "description": "Administrative operations and audit logs"
        }
    ]
)

# CORS middleware for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://vscode-internal-29567-beta.beta01.cloud.kavia.ai:3000",
        "https://vscode-internal-29567-beta.beta01.cloud.kavia.ai:3001", 
        "http://localhost:3000",
        "http://localhost:3001",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)

# Add custom middlewares
app.add_middleware(CORSHeadersMiddleware)
app.add_middleware(FileSizeMiddleware, max_upload_size=2 * 1024 * 1024 * 1024)  # 2GB limit

# Security
security = HTTPBearer(auto_error=False)

# Database configuration
DATABASE_PATH = os.path.join(os.path.dirname(__file__), "..", "Database", "subtitle_sync_platform.db")
UPLOAD_DIR = "uploads"
PROCESSED_DIR = "processed"

# Ensure directories exist
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)

# JWT configuration
JWT_SECRET = os.getenv("JWT_SECRET", "your-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"

# Pydantic models
class UserRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., regex=r'^[^@]+@[^@]+\.[^@]+$')
    password: str = Field(..., min_length=6)
    role: str = Field(default="user")

class UserLogin(BaseModel):
    email: str
    password: str

class JobStatus(BaseModel):
    id: str
    status: str
    progress: int = 0
    message: str = ""
    result_url: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

class SubtitleFile(BaseModel):
    id: int
    filename: str
    language: str
    size: int = 0
    created_at: datetime
    processed: bool = False
    video_id: Optional[int] = None

class TranslationRequest(BaseModel):
    target_language: str = Field(..., min_length=2, max_length=5)

# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests and responses"""
    start_time = datetime.now()
    
    # Log request details
    logger.info(f"REQUEST: {request.method} {request.url.path} - "
                f"Query: {dict(request.query_params)} - "
                f"Client: {request.client.host if request.client else 'unknown'}")
    
    # Process request
    response = await call_next(request)
    
    # Calculate processing time
    process_time = (datetime.now() - start_time).total_seconds()
    
    # Log response details
    logger.info(f"RESPONSE: {request.method} {request.url.path} - "
                f"Status: {response.status_code} - "
                f"Time: {process_time:.3f}s")
    
    # Add processing time header
    response.headers["X-Process-Time"] = str(process_time)
    
    return response

# Authentication helpers
def create_jwt_token(user_data: dict) -> str:
    """Create JWT token for user"""
    payload = {
        "user_id": user_data.get("id"),
        "email": user_data.get("email"),
        "exp": datetime.utcnow() + timedelta(days=7)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def verify_jwt_token(token: str) -> dict:
    """Verify and decode JWT token"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Optional[dict]:
    """Get current authenticated user"""
    if not credentials:
        return None
    
    try:
        payload = verify_jwt_token(credentials.credentials)
        return payload
    except HTTPException:
        return None

# File processing helpers
def generate_job_id() -> str:
    """Generate unique job ID"""
    return str(uuid.uuid4())

def save_uploaded_file(file: UploadFile, directory: str) -> str:
    """Save uploaded file and return path"""
    file_id = str(uuid.uuid4())
    file_extension = os.path.splitext(file.filename)[1]
    filename = f"{file_id}_{file.filename}"
    file_path = os.path.join(directory, filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    return file_path

async def process_subtitle_task(job_id: str, video_path: str, subtitle_path: str = None, language: str = "en"):
    """Background task for processing subtitles"""
    try:
        # Update job status to processing
        job_processor.update_job_status(job_id, "processing", 25, "Processing files...")
        
        if subtitle_path:
            # Correction workflow
            logger.info(f"Starting subtitle correction for job {job_id}")
            result_path = subtitle_processor.correct_subtitles(video_path, subtitle_path)
            job_processor.update_job_status(job_id, "processing", 75, "Finalizing correction...")
        else:
            # Generation workflow
            logger.info(f"Starting subtitle generation for job {job_id}")
            result_path = subtitle_processor.generate_subtitles(video_path, language)
            job_processor.update_job_status(job_id, "processing", 75, "Finalizing generation...")
        
        # Save result to database
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE jobs SET status = ?, result_url = ?, completed_at = ? WHERE id = ?",
            ("completed", result_path, datetime.now(), job_id)
        )
        conn.commit()
        conn.close()
        
        job_processor.update_job_status(job_id, "completed", 100, "Processing completed successfully")
        logger.info(f"Job {job_id} completed successfully")
        
    except Exception as e:
        logger.error(f"Job {job_id} failed: {str(e)}")
        job_processor.update_job_status(job_id, "failed", 0, f"Processing failed: {str(e)}")
        
        # Update database
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE jobs SET status = ?, completed_at = ? WHERE id = ?",
            ("failed", datetime.now(), job_id)
        )
        conn.commit()
        conn.close()

# API Endpoints

@app.get("/", tags=["general"])
async def root():
    """
    Root endpoint - API health check and information
    """
    return {
        "message": "Subtitle Sync Backend API",
        "version": "1.0.0",
        "status": "operational",
        "endpoints": {
            "docs": "/docs",
            "openapi": "/openapi.json",
            "frontend": "https://vscode-internal-29567-beta.beta01.cloud.kavia.ai:3001"
        }
    }

@app.post("/process", tags=["processing"])
async def process_files(
    background_tasks: BackgroundTasks,
    video: UploadFile = File(..., description="Video file for processing"),
    subtitle: Optional[UploadFile] = File(None, description="Subtitle file for correction (optional)"),
    language: str = Form("en", description="Target language for subtitle generation")
):
    """
    Process video and subtitle files for correction or generation
    
    - **video**: Video file (required)
    - **subtitle**: Subtitle file (optional - if provided, correction mode)
    - **language**: Target language for generation (default: en)
    
    Returns either direct processed file or job ID for tracking
    """
    try:
        logger.info(f"Processing request: video={video.filename}, subtitle={subtitle.filename if subtitle else None}, language={language}")
        
        # Validate video file
        if not video.content_type.startswith('video/'):
            raise HTTPException(status_code=422, detail="Invalid video file format")
        
        # Validate subtitle file if provided
        if subtitle:
            allowed_extensions = ['.srt', '.vtt', '.ass', '.ssa', '.scc', '.sub', '.smi']
            file_ext = os.path.splitext(subtitle.filename)[1].lower()
            if file_ext not in allowed_extensions:
                raise HTTPException(status_code=422, detail=f"Invalid subtitle file format. Allowed: {', '.join(allowed_extensions)}")
        
        # Save uploaded files
        video_path = save_uploaded_file(video, UPLOAD_DIR)
        subtitle_path = save_uploaded_file(subtitle, UPLOAD_DIR) if subtitle else None
        
        # Create job record
        job_id = generate_job_id()
        job_type = "correction" if subtitle else "generation"
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO jobs (id, job_type, status, created_at)
            VALUES (?, ?, ?, ?)
        """, (job_id, job_type, "queued", datetime.now()))
        conn.commit()
        conn.close()
        
        # Start background processing
        background_tasks.add_task(process_subtitle_task, job_id, video_path, subtitle_path, language)
        
        # For now, return job ID for tracking
        job_processor.update_job_status(job_id, "queued", 0, "Job queued for processing")
        
        return {
            "job_id": job_id,
            "status": "queued",
            "message": f"{'Correction' if subtitle else 'Generation'} job started"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Process files error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")

@app.get("/jobs/{job_id}/status", tags=["jobs"])
async def get_job_status(job_id: str):
    """
    Get status of a processing job
    
    - **job_id**: Unique job identifier
    
    Returns current job status, progress, and result information
    """
    try:
        # Get status from job processor
        status = job_processor.get_job_status(job_id)
        if not status:
            # Check database
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
            job = cursor.fetchone()
            conn.close()
            
            if not job:
                raise HTTPException(status_code=404, detail="Job not found")
            
            return {
                "id": job["id"],
                "status": job["status"],
                "progress": 100 if job["status"] == "completed" else 0,
                "message": f"Job {job['status']}",
                "result_url": job["result_url"],
                "created_at": job["created_at"],
                "completed_at": job["completed_at"]
            }
        
        return status
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get job status error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get job status")

@app.get("/subtitles", tags=["subtitles"])
async def get_subtitle_files(current_user: dict = Depends(get_current_user)):
    """
    Get list of user's subtitle files
    
    Returns array of subtitle file objects with metadata
    """
    try:
        # For now, return all processed files (in production, filter by user)
        processed_files = []
        
        if os.path.exists(PROCESSED_DIR):
            for filename in os.listdir(PROCESSED_DIR):
                file_path = os.path.join(PROCESSED_DIR, filename)
                if os.path.isfile(file_path):
                    stat = os.stat(file_path)
                    processed_files.append({
                        "id": hash(filename) % 10000,  # Simple ID generation
                        "filename": filename,
                        "language": "en",  # Default language
                        "size": stat.st_size,
                        "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                        "processed": True
                    })
        
        return processed_files
        
    except Exception as e:
        logger.error(f"Get subtitle files error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get subtitle files")

@app.get("/subtitles/{file_id}/download", tags=["subtitles"])
async def download_subtitle_file(file_id: int, current_user: dict = Depends(get_current_user)):
    """
    Download a subtitle file by ID
    
    - **file_id**: File identifier
    
    Returns the subtitle file as a download
    """
    try:
        # Find file by ID (simple implementation)
        if os.path.exists(PROCESSED_DIR):
            for filename in os.listdir(PROCESSED_DIR):
                if hash(filename) % 10000 == file_id:
                    file_path = os.path.join(PROCESSED_DIR, filename)
                    if os.path.isfile(file_path):
                        return FileResponse(
                            path=file_path,
                            filename=filename,
                            media_type='text/plain'
                        )
        
        raise HTTPException(status_code=404, detail="File not found")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Download file error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to download file")

@app.post("/subtitles/{file_id}/translate", tags=["subtitles"])
async def request_translation(
    file_id: int,
    translation_request: TranslationRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """
    Request translation of a subtitle file
    
    - **file_id**: Source file identifier
    - **target_language**: Target language code
    
    Returns translation job information
    """
    try:
        # Find source file
        source_file = None
        if os.path.exists(PROCESSED_DIR):
            for filename in os.listdir(PROCESSED_DIR):
                if hash(filename) % 10000 == file_id:
                    source_file = os.path.join(PROCESSED_DIR, filename)
                    break
        
        if not source_file:
            raise HTTPException(status_code=404, detail="Source file not found")
        
        # Create translation job
        job_id = generate_job_id()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO jobs (id, job_type, status, created_at)
            VALUES (?, ?, ?, ?)
        """, (job_id, "translation", "queued", datetime.now()))
        conn.commit()
        conn.close()
        
        # For now, just return job info (translation would be implemented later)
        return {
            "job_id": job_id,
            "status": "queued",
            "message": f"Translation to {translation_request.target_language} queued",
            "target_language": translation_request.target_language
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Request translation error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to request translation")

@app.post("/auth/register", tags=["auth"])
async def register_user(user_data: UserRegister):
    """
    Register a new user account
    
    - **username**: Unique username (3-50 characters)
    - **email**: Valid email address
    - **password**: Password (minimum 6 characters)
    - **role**: User role (default: user)
    
    Returns user information and authentication token
    """
    try:
        # Hash password
        password_hash = hashlib.sha256(user_data.password.encode()).hexdigest()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if user already exists
        cursor.execute("SELECT id FROM users WHERE email = ? OR username = ?", 
                      (user_data.email, user_data.username))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="User already exists")
        
        # Create user
        cursor.execute("""
            INSERT INTO users (username, email, password_hash, role)
            VALUES (?, ?, ?, ?)
        """, (user_data.username, user_data.email, password_hash, user_data.role))
        
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # Create user object
        user = {
            "id": user_id,
            "username": user_data.username,
            "email": user_data.email,
            "role": user_data.role
        }
        
        # Generate token
        token = create_jwt_token(user)
        
        logger.info(f"User registered: {user_data.username} ({user_data.email})")
        
        return {
            "user": user,
            "token": token,
            "message": "Registration successful"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        raise HTTPException(status_code=500, detail="Registration failed")

@app.post("/auth/login", tags=["auth"])
async def login_user(credentials: UserLogin):
    """
    Authenticate user and return access token
    
    - **email**: User email address
    - **password**: User password
    
    Returns authentication token and user information
    """
    try:
        # Hash provided password
        password_hash = hashlib.sha256(credentials.password.encode()).hexdigest()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, username, email, role, password_hash
            FROM users WHERE email = ?
        """, (credentials.email,))
        
        user_row = cursor.fetchone()
        conn.close()
        
        if not user_row or user_row["password_hash"] != password_hash:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        # Create user object
        user = {
            "id": user_row["id"],
            "username": user_row["username"],
            "email": user_row["email"],
            "role": user_row["role"]
        }
        
        # Generate token
        token = create_jwt_token(user)
        
        logger.info(f"User logged in: {user['username']} ({user['email']})")
        
        return {
            "user": user,
            "token": token,
            "message": "Login successful"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(status_code=500, detail="Login failed")

@app.get("/health", tags=["general"])
async def health_check():
    """
    Health check endpoint for monitoring
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }

@app.post(
    "/reposition",
    tags=["processing"],
    summary="Reposition subtitles to avoid burnt-in text",
    description="Accepts a video and a subtitle file (.srt, .ass, .ssa, .vtt), runs OCR on sampled frames to detect burnt-in text, and returns a new subtitle file with cues repositioned (top/bottom) to avoid overlap."
)
async def reposition_subtitles(
    video: UploadFile = File(..., description="Video file for analysis (required)"),
    subtitle: UploadFile = File(..., description="Subtitle file to reposition (.srt, .ass, .ssa, .vtt)"),
    min_frames: int = Form(3, description="Number of frames to sample per subtitle segment for OCR decision")
):
    """
    Reposition subtitles to avoid overlapping with burnt-in text in the video.

    Parameters:
    - video: UploadFile (required). The video file used to detect burnt-in text.
    - subtitle: UploadFile (required). The subtitle file (.srt, .ass, .ssa, .vtt) to be repositioned.
    - min_frames: int (optional). Number of frames to sample per subtitle segment for OCR-based top/bottom decision. Default is 3.

    Returns:
    - FileResponse: The repositioned subtitle file. For SRT inputs, output will be an ASS file; other formats are updated in-place where possible.
    """
    try:
        # Validate video
        if not video.content_type or not video.content_type.startswith("video/"):
            raise HTTPException(status_code=422, detail="Invalid video file format")

        # Validate subtitle extension
        allowed_extensions = ['.srt', '.vtt', '.ass', '.ssa']
        sub_ext = os.path.splitext(subtitle.filename)[1].lower()
        if sub_ext not in allowed_extensions:
            raise HTTPException(status_code=422, detail=f"Invalid subtitle file format. Allowed: {', '.join(allowed_extensions)}")

        # Save uploads
        video_path = save_uploaded_file(video, UPLOAD_DIR)
        subtitle_path = save_uploaded_file(subtitle, UPLOAD_DIR)

        # Process repositioning
        result_path = process_subtitle(video_path, subtitle_path, min_frames=min_frames)

        # Return file response
        return FileResponse(
            path=result_path,
            filename=os.path.basename(result_path),
            media_type="text/plain"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Repositioning failed")
        raise HTTPException(status_code=500, detail=f"Repositioning failed: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
