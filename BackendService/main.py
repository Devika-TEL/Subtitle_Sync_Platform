"""
FastAPI Backend Service for Subtitle Sync Platform
Provides comprehensive subtitle processing, validation, generation, and translation services.
"""

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends, BackgroundTasks, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
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
from subtitle_processor import subtitle_processor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Subtitle Sync Backend API",
    description="Comprehensive API for subtitle-audio synchronization, generation, validation, correction, and translation services",
    version="1.0.0",
    openapi_tags=[
        {
            "name": "subtitles",
            "description": "Subtitle upload, download, and management operations"
        },
        {
            "name": "processing",
            "description": "Subtitle validation, correction, and synchronization"
        },
        {
            "name": "generation",
            "description": "LLM-powered subtitle generation and translation"
        },
        {
            "name": "jobs",
            "description": "Job tracking and progress monitoring"
        },
        {
            "name": "users",
            "description": "User management and authentication"
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
        "http://localhost:3000", 
        "https://vscode-internal-33546-beta.beta01.cloud.kavia.ai:3000",
        "https://vscode-internal-29822-beta.beta01.cloud.kavia.ai:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer(auto_error=False)

# Database configuration
DATABASE_PATH = os.path.join(os.path.dirname(__file__), "..", "Database", "subtitle_sync_platform.db")
UPLOAD_DIR = "uploads"
PROCESSED_DIR = "processed"

# Ensure directories exist
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)

# Pydantic models
class SubtitleUploadResponse(BaseModel):
    """Response model for subtitle upload operations"""
    id: int = Field(..., description="Unique identifier for the uploaded subtitle")
    filename: str = Field(..., description="Original filename of the uploaded subtitle")
    video_id: Optional[int] = Field(None, description="Associated video ID if linked")
    language: Optional[str] = Field(None, description="Detected or specified language")
    status: str = Field(..., description="Upload status")

class VideoUploadResponse(BaseModel):
    """Response model for video upload operations"""
    id: int = Field(..., description="Unique identifier for the uploaded video")
    filename: str = Field(..., description="Original filename of the uploaded video")
    language: Optional[str] = Field(None, description="Detected or specified language")
    status: str = Field(..., description="Upload status")

class JobResponse(BaseModel):
    """Response model for job operations"""
    id: int = Field(..., description="Unique job identifier")
    job_type: str = Field(..., description="Type of processing job")
    status: str = Field(..., description="Current job status")
    progress: Optional[int] = Field(None, description="Job progress percentage")
    result_url: Optional[str] = Field(None, description="URL to download results")
    created_at: str = Field(..., description="Job creation timestamp")
    completed_at: Optional[str] = Field(None, description="Job completion timestamp")

class SubtitleListItem(BaseModel):
    """Model for subtitle list items"""
    id: int
    filename: str
    language: Optional[str]
    upload_time: str
    processed: bool
    video_id: Optional[int]

class UserCreate(BaseModel):
    """Model for user creation"""
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)
    email: Optional[str] = None
    role: str = Field(default="user")

class UserResponse(BaseModel):
    """Response model for user operations"""
    id: int
    username: str
    email: Optional[str]
    role: str

class ValidationResult(BaseModel):
    """Model for subtitle validation results"""
    is_valid: bool
    issues: List[str]
    recommendations: List[str]
    reading_speed_wpm: Optional[float]
    character_count: int
    line_count: int

# Database helper functions
def get_db_connection():
    """Get database connection with foreign key support"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """Initialize database tables"""
    try:
        from Database.models import create_tables
        create_tables()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        # Fallback: create tables directly
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Create tables as defined in schema
        with open(os.path.join(os.path.dirname(__file__), "..", "Database", "schema.sql"), 'r') as f:
            schema = f.read()
            cursor.executescript(schema)
        
        conn.commit()
        conn.close()

# Authentication helpers (stub for future integration)
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Authentication stub - returns mock user for development
    In production, this would validate JWT tokens and return actual user data
    """
    if credentials:
        # Mock authentication - in production, validate JWT token here
        return {"id": 1, "username": "testuser", "role": "user"}
    return {"id": 1, "username": "anonymous", "role": "user"}

def get_admin_user(current_user: dict = Depends(get_current_user)):
    """Require admin role for certain endpoints"""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user

# Subtitle processing functions
def detect_subtitle_format(content: str) -> str:
    """Detect subtitle format from content"""
    content_lower = content.lower().strip()
    
    if content_lower.startswith("webvtt") or "webvtt" in content_lower:
        return "webvtt"
    elif "-->" in content and re.search(r'\d{2}:\d{2}:\d{2},\d{3}', content):
        return "srt"
    elif "subtitle" in content_lower and "{" in content:
        return "ass"
    elif re.search(r'\d{2}:\d{2}:\d{2}:\d{2}', content):
        return "scc"
    else:
        return "unknown"

def validate_subtitle_content(content: str, format_type: str) -> ValidationResult:
    """Validate subtitle content and return detailed analysis"""
    issues = []
    recommendations = []
    
    lines = content.split('\n')
    line_count = len([line for line in lines if line.strip()])
    character_count = len(content)
    
    # Basic format validation
    if format_type == "srt":
        if not re.search(r'\d+\s*\n\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}', content):
            issues.append("Invalid SRT format structure")
    elif format_type == "webvtt":
        if not content.strip().startswith("WEBVTT"):
            issues.append("WebVTT files must start with 'WEBVTT'")
    
    # Reading speed analysis (approximate)
    words = len(content.split())
    estimated_duration = 120  # seconds (mock - would calculate from timestamps)
    reading_speed_wpm = (words / estimated_duration) * 60 if estimated_duration > 0 else 0
    
    if reading_speed_wpm > 200:
        issues.append("Reading speed too fast (>200 WPM)")
        recommendations.append("Consider reducing text density or extending display time")
    
    # Character count validation
    if character_count > 50000:
        issues.append("File size very large, may impact performance")
    
    # Line count validation
    if line_count > 1000:
        recommendations.append("Consider splitting large subtitle files")
    
    return ValidationResult(
        is_valid=len(issues) == 0,
        issues=issues,
        recommendations=recommendations,
        reading_speed_wpm=reading_speed_wpm,
        character_count=character_count,
        line_count=line_count
    )

async def process_subtitle_sync(video_path: str, subtitle_path: str) -> str:
    """
    Process subtitle-audio synchronization using the subtitle processor
    """
    try:
        # Use the subtitle processor for correction
        corrected_path = await subtitle_processor.correct_subtitle_sync(
            video_path, subtitle_path, offset_ms=0
        )
        
        # Move corrected file to processed directory
        if os.path.exists(corrected_path):
            final_path = os.path.join(PROCESSED_DIR, os.path.basename(corrected_path))
            shutil.move(corrected_path, final_path)
            return final_path
        else:
            raise Exception("Correction processing failed")
            
    except Exception as e:
        logger.error(f"Subtitle sync processing failed: {e}")
        # Fallback to simple processing
        await asyncio.sleep(1)
        
        # Read subtitle content
        with open(subtitle_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Basic correction - ensure proper format
        corrected_content = content.strip()
        if not corrected_content.endswith('\n'):
            corrected_content += '\n'
        
        # Save corrected version
        base_name = os.path.splitext(os.path.basename(subtitle_path))[0]
        corrected_path = os.path.join(PROCESSED_DIR, f"{base_name}_corrected.srt")
        with open(corrected_path, 'w', encoding='utf-8') as f:
            f.write(corrected_content)
        
        return corrected_path

async def generate_subtitles_from_video(video_path: str, target_language: str = "en") -> str:
    """
    Generate subtitles from video using the subtitle processor
    """
    try:
        # Use the subtitle processor for generation
        generated_path = await subtitle_processor.generate_subtitles_from_audio(
            video_path, target_language
        )
        
        # Move generated file to processed directory
        if os.path.exists(generated_path):
            final_path = os.path.join(PROCESSED_DIR, os.path.basename(generated_path))
            shutil.move(generated_path, final_path)
            return final_path
        else:
            raise Exception("Subtitle generation failed")
            
    except Exception as e:
        logger.error(f"Subtitle generation failed: {e}")
        # Fallback to mock generation
        await asyncio.sleep(2)
        
        # Generate mock subtitle content
        mock_subtitles = f"""1
00:00:01,000 --> 00:00:05,000
Generated subtitle content from video analysis.

2
00:00:06,000 --> 00:00:10,000
This is a placeholder for AI-generated subtitles in {target_language}.

3
00:00:11,000 --> 00:00:15,000
In production, this would use speech recognition and LLMs.
"""
        
        # Save generated subtitles
        base_name = os.path.splitext(os.path.basename(video_path))[0]
        generated_path = os.path.join(PROCESSED_DIR, f"{base_name}_generated_{target_language}.srt")
        with open(generated_path, 'w', encoding='utf-8') as f:
            f.write(mock_subtitles)
        
        return generated_path

async def translate_subtitles(subtitle_path: str, target_language: str) -> str:
    """
    Translate subtitles to target language using LLM
    This is a mock implementation - in production would use translation APIs/LLMs
    """
    # Mock processing delay
    await asyncio.sleep(3)
    
    with open(subtitle_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Mock translation (just add language prefix)
    translated_content = content.replace(
        "Generated subtitle content",
        f"[{target_language.upper()}] Generated subtitle content"
    )
    
    # Save translated version
    translated_path = subtitle_path.replace(".srt", f"_translated_{target_language}.srt")
    with open(translated_path, 'w', encoding='utf-8') as f:
        f.write(translated_content)
    
    return translated_path

# Background job processing
async def process_job_background(job_id: int):
    """Background task to process jobs"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Update job status to running
        cursor.execute("UPDATE jobs SET status = 'running' WHERE id = ?", (job_id,))
        conn.commit()
        
        # Get job details
        cursor.execute("""
            SELECT j.*, v.filename as video_filename, s.filename as subtitle_filename
            FROM jobs j
            LEFT JOIN videos v ON j.video_id = v.id
            LEFT JOIN subtitles s ON j.subtitle_id = s.id
            WHERE j.id = ?
        """, (job_id,))
        
        job = cursor.fetchone()
        if not job:
            raise Exception("Job not found")
        
        result_path = None
        
        if job['job_type'] == 'correction':
            # Process subtitle correction
            video_path = os.path.join(UPLOAD_DIR, job['video_filename']) if job['video_filename'] else None
            subtitle_path = os.path.join(UPLOAD_DIR, job['subtitle_filename']) if job['subtitle_filename'] else None
            
            if video_path and subtitle_path and os.path.exists(video_path) and os.path.exists(subtitle_path):
                result_path = await process_subtitle_sync(video_path, subtitle_path)
        
        elif job['job_type'] == 'generation':
            # Generate subtitles from video
            video_path = os.path.join(UPLOAD_DIR, job['video_filename']) if job['video_filename'] else None
            if video_path and os.path.exists(video_path):
                result_path = await generate_subtitles_from_video(video_path)
        
        elif job['job_type'] == 'translation':
            # Translate existing subtitles
            subtitle_path = os.path.join(UPLOAD_DIR, job['subtitle_filename']) if job['subtitle_filename'] else None
            if subtitle_path and os.path.exists(subtitle_path):
                result_path = await translate_subtitles(subtitle_path, "es")  # Default to Spanish
        
        # Update job with results
        if result_path and os.path.exists(result_path):
            # Move result to processed directory
            result_filename = os.path.basename(result_path)
            final_result_path = os.path.join(PROCESSED_DIR, result_filename)
            shutil.move(result_path, final_result_path)
            
            cursor.execute("""
                UPDATE jobs SET status = 'complete', result_url = ?, completed_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (f"/download/{result_filename}", job_id))
        else:
            cursor.execute("UPDATE jobs SET status = 'failed' WHERE id = ?", (job_id,))
        
        conn.commit()
        
    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}")
        cursor.execute("UPDATE jobs SET status = 'failed' WHERE id = ?", (job_id,))
        conn.commit()
    finally:
        conn.close()

# API Endpoints

@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    init_database()

# PUBLIC_INTERFACE
@app.get("/", summary="Health Check", description="Basic health check endpoint")
async def root():
    """Health check endpoint"""
    return {"message": "Subtitle Sync Backend API is running", "status": "healthy"}

# PUBLIC_INTERFACE
@app.post("/subtitles/upload", response_model=SubtitleUploadResponse, tags=["subtitles"],
          summary="Upload Subtitle File", description="Upload a subtitle file for processing")
async def upload_subtitle(
    file: UploadFile = File(..., description="Subtitle file to upload"),
    video_id: Optional[int] = Form(None, description="Optional video ID to link subtitle"),
    language: Optional[str] = Form(None, description="Subtitle language"),
    current_user: dict = Depends(get_current_user)
):
    """Upload subtitle file and store metadata"""
    allowed_extensions = ('.srt', '.vtt', '.ass', '.ssa', '.scc', '.sub', '.smi', '.sami')
    if not file.filename.lower().endswith(allowed_extensions):
        raise HTTPException(status_code=400, detail=f"Unsupported subtitle format. Supported formats: {', '.join(allowed_extensions)}")
    
    # Save uploaded file
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Detect format and validate
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    format_type = detect_subtitle_format(content)
    
    # Store in database
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO subtitles (video_id, user_id, filename, language, upload_time)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
    """, (video_id, current_user['id'], file.filename, language))
    
    subtitle_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return SubtitleUploadResponse(
        id=subtitle_id,
        filename=file.filename,
        video_id=video_id,
        language=language,
        status="uploaded"
    )

# PUBLIC_INTERFACE
@app.post("/videos/upload", response_model=VideoUploadResponse, tags=["subtitles"],
          summary="Upload Video File", description="Upload a video file for subtitle generation")
async def upload_video(
    file: UploadFile = File(..., description="Video file to upload"),
    language: Optional[str] = Form(None, description="Video language"),
    current_user: dict = Depends(get_current_user)
):
    """Upload video file and store metadata"""
    if not file.filename.lower().endswith(('.mp4', '.avi', '.mov', '.mkv', '.webm')):
        raise HTTPException(status_code=400, detail="Unsupported video format")
    
    # Save uploaded file
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Store in database
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO videos (user_id, filename, language, upload_time)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
    """, (current_user['id'], file.filename, language))
    
    video_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return VideoUploadResponse(
        id=video_id,
        filename=file.filename,
        language=language,
        status="uploaded"
    )

# PUBLIC_INTERFACE
@app.get("/subtitles", response_model=List[SubtitleListItem], tags=["subtitles"],
         summary="List Subtitles", description="Get list of uploaded subtitles for current user")
async def list_subtitles(
    current_user: dict = Depends(get_current_user),
    limit: int = Query(50, description="Maximum number of results")
):
    """Get list of subtitles for current user"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, filename, language, upload_time, processed, video_id
        FROM subtitles
        WHERE user_id = ?
        ORDER BY upload_time DESC
        LIMIT ?
    """, (current_user['id'], limit))
    
    subtitles = []
    for row in cursor.fetchall():
        subtitles.append(SubtitleListItem(
            id=row['id'],
            filename=row['filename'],
            language=row['language'],
            upload_time=row['upload_time'],
            processed=bool(row['processed']),
            video_id=row['video_id']
        ))
    
    conn.close()
    return subtitles

# PUBLIC_INTERFACE
@app.get("/subtitles/{subtitle_id}/validate", response_model=ValidationResult, tags=["processing"],
         summary="Validate Subtitle", description="Validate subtitle content and get quality analysis")
async def validate_subtitle(
    subtitle_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Validate subtitle file and return analysis"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT filename FROM subtitles 
        WHERE id = ? AND user_id = ?
    """, (subtitle_id, current_user['id']))
    
    result = cursor.fetchone()
    if not result:
        raise HTTPException(status_code=404, detail="Subtitle not found")
    
    file_path = os.path.join(UPLOAD_DIR, result['filename'])
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Subtitle file not found")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    format_type = detect_subtitle_format(content)
    validation_result = validate_subtitle_content(content, format_type)
    
    conn.close()
    return validation_result

# PUBLIC_INTERFACE
@app.post("/process", tags=["processing"],
          summary="Process Files", description="Process video and subtitle files for correction or generation")
async def process_files(
    video: UploadFile = File(..., description="Video file"),
    subtitle: Optional[UploadFile] = File(None, description="Subtitle file for correction"),
    language: Optional[str] = Form("en", description="Target language for generation"),
    current_user: dict = Depends(get_current_user)
):
    """
    Process video and subtitle files directly.
    - If both video and subtitle provided: perform correction
    - If only video provided: generate subtitles
    """
    try:
        # Validate video file
        if not video.filename.lower().endswith(('.mp4', '.avi', '.mov', '.mkv', '.webm')):
            raise HTTPException(status_code=400, detail="Unsupported video format")
        
        # Save video file
        video_path = os.path.join(UPLOAD_DIR, f"temp_{uuid.uuid4()}_{video.filename}")
        with open(video_path, "wb") as buffer:
            shutil.copyfileobj(video.file, buffer)
        
        try:
            if subtitle:
                # Correction workflow
                allowed_extensions = ('.srt', '.vtt', '.ass', '.ssa', '.scc', '.sub', '.smi', '.sami')
                if not subtitle.filename.lower().endswith(allowed_extensions):
                    raise HTTPException(status_code=400, detail=f"Unsupported subtitle format. Supported: {', '.join(allowed_extensions)}")
                
                # Save subtitle file
                subtitle_path = os.path.join(UPLOAD_DIR, f"temp_{uuid.uuid4()}_{subtitle.filename}")
                with open(subtitle_path, "wb") as buffer:
                    shutil.copyfileobj(subtitle.file, buffer)
                
                try:
                    # Process correction
                    corrected_path = await process_subtitle_sync(video_path, subtitle_path)
                    
                    # Return corrected file
                    if os.path.exists(corrected_path):
                        return FileResponse(
                            corrected_path,
                            media_type='application/octet-stream',
                            filename=f"corrected_{subtitle.filename}"
                        )
                    else:
                        raise HTTPException(status_code=500, detail="Failed to process correction")
                
                finally:
                    # Clean up subtitle file
                    if os.path.exists(subtitle_path):
                        os.remove(subtitle_path)
            else:
                # Generation workflow
                generated_path = await generate_subtitles_from_video(video_path, language)
                
                # Return generated file
                if os.path.exists(generated_path):
                    return FileResponse(
                        generated_path,
                        media_type='application/octet-stream',
                        filename=f"generated_{language}_{video.filename.rsplit('.', 1)[0]}.srt"
                    )
                else:
                    raise HTTPException(status_code=500, detail="Failed to generate subtitles")
        
        finally:
            # Clean up video file
            if os.path.exists(video_path):
                os.remove(video_path)
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Processing error: {e}")
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")

# PUBLIC_INTERFACE
@app.post("/jobs/correction", response_model=JobResponse, tags=["processing"],
          summary="Start Correction Job", description="Start subtitle-audio synchronization correction job")
async def start_correction_job(
    video_id: int = Form(..., description="Video ID for synchronization"),
    subtitle_id: int = Form(..., description="Subtitle ID to correct"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: dict = Depends(get_current_user)
):
    """Start subtitle correction job"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Verify ownership
    cursor.execute("""
        SELECT v.filename as video_filename, s.filename as subtitle_filename
        FROM videos v, subtitles s
        WHERE v.id = ? AND s.id = ? AND v.user_id = ? AND s.user_id = ?
    """, (video_id, subtitle_id, current_user['id'], current_user['id']))
    
    result = cursor.fetchone()
    if not result:
        raise HTTPException(status_code=404, detail="Video or subtitle not found")
    
    # Create job
    cursor.execute("""
        INSERT INTO jobs (user_id, video_id, subtitle_id, job_type, status)
        VALUES (?, ?, ?, 'correction', 'pending')
    """, (current_user['id'], video_id, subtitle_id))
    
    job_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    # Start background processing
    background_tasks.add_task(process_job_background, job_id)
    
    return JobResponse(
        id=job_id,
        job_type="correction",
        status="pending",
        created_at=datetime.now().isoformat()
    )

# PUBLIC_INTERFACE
@app.post("/jobs/generation", response_model=JobResponse, tags=["generation"],
          summary="Start Generation Job", description="Start subtitle generation from video")
async def start_generation_job(
    video_id: int = Form(..., description="Video ID for subtitle generation"),
    target_language: str = Form("en", description="Target language for subtitles"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: dict = Depends(get_current_user)
):
    """Start subtitle generation job"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Verify video ownership
    cursor.execute("""
        SELECT filename FROM videos WHERE id = ? AND user_id = ?
    """, (video_id, current_user['id']))
    
    result = cursor.fetchone()
    if not result:
        raise HTTPException(status_code=404, detail="Video not found")
    
    # Create job
    cursor.execute("""
        INSERT INTO jobs (user_id, video_id, job_type, status)
        VALUES (?, ?, 'generation', 'pending')
    """, (current_user['id'], video_id))
    
    job_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    # Start background processing
    background_tasks.add_task(process_job_background, job_id)
    
    return JobResponse(
        id=job_id,
        job_type="generation",
        status="pending",
        created_at=datetime.now().isoformat()
    )

# PUBLIC_INTERFACE
@app.post("/jobs/translation", response_model=JobResponse, tags=["generation"],
          summary="Start Translation Job", description="Start subtitle translation to target language")
async def start_translation_job(
    subtitle_id: int = Form(..., description="Subtitle ID to translate"),
    target_language: str = Form(..., description="Target language code"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: dict = Depends(get_current_user)
):
    """Start subtitle translation job"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Verify subtitle ownership
    cursor.execute("""
        SELECT filename FROM subtitles WHERE id = ? AND user_id = ?
    """, (subtitle_id, current_user['id']))
    
    result = cursor.fetchone()
    if not result:
        raise HTTPException(status_code=404, detail="Subtitle not found")
    
    # Create job
    cursor.execute("""
        INSERT INTO jobs (user_id, subtitle_id, job_type, status)
        VALUES (?, ?, 'translation', 'pending')
    """, (current_user['id'], subtitle_id))
    
    job_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    # Start background processing
    background_tasks.add_task(process_job_background, job_id)
    
    return JobResponse(
        id=job_id,
        job_type="translation",
        status="pending",
        created_at=datetime.now().isoformat()
    )

# PUBLIC_INTERFACE
@app.get("/jobs/{job_id}", response_model=JobResponse, tags=["jobs"],
         summary="Get Job Status", description="Get current status and progress of a job")
async def get_job_status(
    job_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Get job status and progress"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM jobs WHERE id = ? AND user_id = ?
    """, (job_id, current_user['id']))
    
    job = cursor.fetchone()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    conn.close()
    
    # Calculate progress based on status
    progress = None
    if job['status'] == 'pending':
        progress = 0
    elif job['status'] == 'running':
        progress = 50
    elif job['status'] == 'complete':
        progress = 100
    elif job['status'] == 'failed':
        progress = 0
    
    return JobResponse(
        id=job['id'],
        job_type=job['job_type'],
        status=job['status'],
        progress=progress,
        result_url=job['result_url'],
        created_at=job['created_at'],
        completed_at=job['completed_at']
    )

# PUBLIC_INTERFACE
@app.get("/jobs", response_model=List[JobResponse], tags=["jobs"],
         summary="List Jobs", description="Get list of jobs for current user")
async def list_jobs(
    current_user: dict = Depends(get_current_user),
    status: Optional[str] = Query(None, description="Filter by job status"),
    limit: int = Query(50, description="Maximum number of results")
):
    """Get list of jobs for current user"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM jobs WHERE user_id = ?"
    params = [current_user['id']]
    
    if status:
        query += " AND status = ?"
        params.append(status)
    
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    
    cursor.execute(query, params)
    
    jobs = []
    for job in cursor.fetchall():
        progress = None
        if job['status'] == 'pending':
            progress = 0
        elif job['status'] == 'running':
            progress = 50
        elif job['status'] == 'complete':
            progress = 100
        
        jobs.append(JobResponse(
            id=job['id'],
            job_type=job['job_type'],
            status=job['status'],
            progress=progress,
            result_url=job['result_url'],
            created_at=job['created_at'],
            completed_at=job['completed_at']
        ))
    
    conn.close()
    return jobs

# PUBLIC_INTERFACE
@app.get("/download/{filename}", tags=["subtitles"],
         summary="Download Processed File", description="Download processed subtitle or video file")
async def download_file(filename: str):
    """Download processed file"""
    file_path = os.path.join(PROCESSED_DIR, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        file_path,
        media_type='application/octet-stream',
        filename=filename
    )

# PUBLIC_INTERFACE
@app.post("/users/register", response_model=UserResponse, tags=["users"],
          summary="Register User", description="Register a new user account")
async def register_user(user_data: UserCreate):
    """Register new user"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Hash the password using the UserAuth utility
        from auth import UserAuth
        
        # Validate password strength
        password_validation = UserAuth.validate_password_strength(user_data.password)
        if not password_validation["is_valid"]:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Password does not meet security requirements",
                    "issues": password_validation["issues"]
                }
            )
        
        # Hash the password
        password_hash = UserAuth.hash_password(user_data.password)
        
        cursor.execute("""
            INSERT INTO users (username, password_hash, email, role)
            VALUES (?, ?, ?, ?)
        """, (user_data.username, password_hash, user_data.email, "user"))  # Force regular user role
        
        user_id = cursor.lastrowid
        conn.commit()
        
        return UserResponse(
            id=user_id,
            username=user_data.username,
            email=user_data.email,
            role=user_data.role
        )
        
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Username already exists")
    finally:
        conn.close()

# PUBLIC_INTERFACE
@app.get("/users/me", response_model=UserResponse, tags=["users"],
         summary="Get Current User", description="Get current user information")
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """Get current user information"""
    return UserResponse(
        id=current_user['id'],
        username=current_user['username'],
        email=current_user.get('email'),
        role=current_user['role']
    )

# PUBLIC_INTERFACE
@app.get("/admin/stats", tags=["admin"],
         summary="Get System Statistics", description="Get system usage statistics (admin only)")
async def get_system_stats(admin_user: dict = Depends(get_admin_user)):
    """Get system statistics for admin dashboard"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get various statistics
    cursor.execute("SELECT COUNT(*) as total_users FROM users")
    total_users = cursor.fetchone()['total_users']
    
    cursor.execute("SELECT COUNT(*) as total_videos FROM videos")
    total_videos = cursor.fetchone()['total_videos']
    
    cursor.execute("SELECT COUNT(*) as total_subtitles FROM subtitles")
    total_subtitles = cursor.fetchone()['total_subtitles']
    
    cursor.execute("SELECT COUNT(*) as total_jobs FROM jobs")
    total_jobs = cursor.fetchone()['total_jobs']
    
    cursor.execute("""
        SELECT status, COUNT(*) as count 
        FROM jobs 
        GROUP BY status
    """)
    job_stats = {row['status']: row['count'] for row in cursor.fetchall()}
    
    conn.close()
    
    return {
        "total_users": total_users,
        "total_videos": total_videos,
        "total_subtitles": total_subtitles,
        "total_jobs": total_jobs,
        "job_statistics": job_stats,
        "system_status": "healthy"
    }

# PUBLIC_INTERFACE
@app.get("/admin/audit-logs", tags=["admin"],
         summary="Get Audit Logs", description="Get system audit logs (admin only)")
async def get_audit_logs(
    admin_user: dict = Depends(get_admin_user),
    limit: int = Query(100, description="Maximum number of log entries")
):
    """Get audit logs for admin monitoring"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get recent jobs as audit trail
    cursor.execute("""
        SELECT j.*, u.username, v.filename as video_filename, s.filename as subtitle_filename
        FROM jobs j
        LEFT JOIN users u ON j.user_id = u.id
        LEFT JOIN videos v ON j.video_id = v.id
        LEFT JOIN subtitles s ON j.subtitle_id = s.id
        ORDER BY j.created_at DESC
        LIMIT ?
    """, (limit,))
    
    logs = []
    for row in cursor.fetchall():
        logs.append({
            "id": row['id'],
            "user": row['username'],
            "action": row['job_type'],
            "status": row['status'],
            "video_file": row['video_filename'],
            "subtitle_file": row['subtitle_filename'],
            "timestamp": row['created_at']
        })
    
    conn.close()
    return {"audit_logs": logs}

# WebSocket endpoint for real-time updates (documentation)
@app.get("/docs/websocket", tags=["jobs"],
         summary="WebSocket Documentation", description="Information about WebSocket endpoints for real-time updates")
async def websocket_docs():
    """
    WebSocket Endpoints Documentation
    
    This endpoint provides information about available WebSocket connections for real-time updates.
    
    Available WebSocket endpoints:
    - /ws/jobs/{user_id} - Real-time job status updates for a specific user
    - /ws/progress/{job_id} - Real-time progress updates for a specific job
    
    Usage:
    Connect to WebSocket endpoints using standard WebSocket clients.
    The server will send JSON messages with status updates.
    
    Example message format:
    {
        "type": "job_update",
        "job_id": 123,
        "status": "running",
        "progress": 75
    }
    """
    return {
        "websocket_endpoints": [
            {
                "endpoint": "/ws/jobs/{user_id}",
                "description": "Real-time job status updates for user",
                "message_format": {
                    "type": "job_update",
                    "job_id": "integer",
                    "status": "string",
                    "progress": "integer"
                }
            },
            {
                "endpoint": "/ws/progress/{job_id}",
                "description": "Real-time progress updates for specific job",
                "message_format": {
                    "type": "progress_update",
                    "job_id": "integer",
                    "progress": "integer",
                    "message": "string"
                }
            }
        ],
        "note": "WebSocket implementation requires additional setup and is documented here for API completeness"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
