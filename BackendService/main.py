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
from middleware import FileSizeMiddleware, CORSHeadersMiddleware
from auth import UserAuth, session_manager

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
    title="Subtitle Sync Backend API",
    description="Comprehensive API for subtitle-audio synchronization, generation, validation, correction, and translation services. Frontend dashboard available at: https://vscode-internal-29567-beta.beta01.cloud.kavia.ai:3001",
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

# CORS middleware for frontend integration - comprehensive configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", 
        "http://localhost:3001",  # Backend port for potential cross-origin requests
        "http://localhost:3002",  # Local port 3002
        # Current frontend URL - primary deployment
        "https://vscode-internal-29567-beta.beta01.cloud.kavia.ai:3001",
        "https://vscode-internal-29567-beta.beta01.cloud.kavia.ai:3000",
        "https://vscode-internal-29567-beta.beta01.cloud.kavia.ai",
        # Legacy URLs for backward compatibility
        "https://vscode-internal-29910-beta.beta01.cloud.kavia.ai:3000",
        "https://vscode-internal-29910-beta.beta01.cloud.kavia.ai:3001",
        "https://vscode-internal-29910-beta.beta01.cloud.kavia.ai:3002",
        "https://vscode-internal-29910-beta.beta01.cloud.kavia.ai",
        "https://vscode-internal-33546-beta.beta01.cloud.kavia.ai:3000",
        "https://vscode-internal-29822-beta.beta01.cloud.kavia.ai:3000",
        "https://vscode-internal-27641-beta.beta01.cloud.kavia.ai:3000",
        "https://vscode-internal-32497-beta.beta01.cloud.kavia.ai:3000",
        "https://vscode-internal-32497-beta.beta01.cloud.kavia.ai:3002"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,  # Cache preflight requests for 1 hour
)

# Add custom middlewares - order matters: CORS headers middleware first, then file size
app.add_middleware(CORSHeadersMiddleware)
app.add_middleware(FileSizeMiddleware, max_upload_size=2 * 1024 * 1024 * 1024)  # 2GB limit

# Request logging middleware
@app.middleware("http")
async def log_requests(request, call_next):
    """Log all incoming requests and responses"""
    start_time = datetime.now()
    
    # Log request details
    logger.info(f"REQUEST: {request.method} {request.url.path} - "
                f"Query: {dict(request.query_params)} - "
                f"Headers: {dict(request.headers)}")
    
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
        # First, ensure the database directory exists
        db_dir = os.path.join(os.path.dirname(__file__), "..", "Database")
        os.makedirs(db_dir, exist_ok=True)
        
        # Check if tables already exist
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='subtitles'")
        subtitles_table_exists = cursor.fetchone() is not None
        conn.close()
        
        if subtitles_table_exists:
            logger.info("Database tables already exist - skipping initialization")
            return
        
        logger.info("Database tables missing - initializing...")
        
        # Try to import from Database module
        import sys
        database_path = os.path.join(os.path.dirname(__file__), "..", "Database")
        if database_path not in sys.path:
            sys.path.append(database_path)
        
        try:
            from models import create_tables
            # Modify create_tables to use the correct database path
            original_cwd = os.getcwd()
            os.chdir(database_path)
            create_tables()
            os.chdir(original_cwd)
            logger.info("Database initialized successfully using models.py")
        except Exception as models_error:
            logger.warning(f"Failed to initialize using models.py: {models_error}")
            
            # Fallback: create tables directly using schema
            conn = get_db_connection()
            cursor = conn.cursor()
            
            schema_path = os.path.join(os.path.dirname(__file__), "..", "Database", "schema.sql")
            if os.path.exists(schema_path):
                with open(schema_path, 'r') as f:
                    schema = f.read()
                    cursor.executescript(schema)
                logger.info("Database initialized successfully using schema.sql")
            else:
                # Create basic tables if schema file doesn't exist
                logger.info("Creating basic database schema...")
                cursor.executescript("""
                    CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE NOT NULL,
                        email TEXT UNIQUE,
                        password_hash TEXT NOT NULL,
                        role TEXT DEFAULT 'user',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                    
                    CREATE TABLE IF NOT EXISTS videos (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        filename TEXT NOT NULL,
                        language TEXT,
                        upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        original BOOLEAN DEFAULT 1,
                        FOREIGN KEY (user_id) REFERENCES users (id)
                    );
                    
                    CREATE TABLE IF NOT EXISTS subtitles (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        video_id INTEGER,
                        user_id INTEGER NOT NULL,
                        filename TEXT NOT NULL,
                        language TEXT,
                        upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        processed BOOLEAN DEFAULT 0,
                        job_id INTEGER,
                        FOREIGN KEY (video_id) REFERENCES videos (id),
                        FOREIGN KEY (user_id) REFERENCES users (id),
                        FOREIGN KEY (job_id) REFERENCES jobs (id)
                    );
                    
                    CREATE TABLE IF NOT EXISTS jobs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        video_id INTEGER,
                        subtitle_id INTEGER,
                        job_type TEXT NOT NULL,
                        status TEXT DEFAULT 'pending',
                        result_url TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        completed_at TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users (id),
                        FOREIGN KEY (video_id) REFERENCES videos (id),
                        FOREIGN KEY (subtitle_id) REFERENCES subtitles (id)
                    );
                """)
                logger.info("Basic database schema created successfully")
            
            conn.commit()
            conn.close()
            logger.info("Database initialization completed")
            
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        # Don't raise the exception - let the app continue with existing database
        logger.warning("Continuing with existing database state...")

# Authentication helpers
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Get current authenticated user from JWT token
    Returns mock user if no credentials provided (for development)
    """
    if credentials:
        try:
            # Import auth utilities
            from auth import UserAuth
            
            # Verify JWT token
            token_data = UserAuth.verify_token(credentials.credentials)
            
            # Get user from database
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, username, email, role
                FROM users
                WHERE id = ?
            """, (token_data.user_id,))
            
            user = cursor.fetchone()
            conn.close()
            
            if not user:
                logger.warning(f"Token valid but user not found: {token_data.user_id}")
                raise HTTPException(status_code=401, detail="User not found")
            
            logger.debug(f"Authenticated user: {user['username']} (ID: {user['id']})")
            
            return {
                "id": user['id'],
                "username": user['username'],
                "email": user['email'],
                "role": user['role']
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            raise HTTPException(status_code=401, detail="Invalid authentication")
    
    # Return mock user for development when no credentials provided
    logger.debug("No credentials provided, using anonymous user")
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
    logger.info(f"Starting subtitle sync processing - Video: {os.path.basename(video_path)}, "
                f"Subtitle: {os.path.basename(subtitle_path)}")
    
    try:
        # Validate input files exist
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")
        if not os.path.exists(subtitle_path):
            raise FileNotFoundError(f"Subtitle file not found: {subtitle_path}")
        
        logger.info(f"Input files validated - Video size: {os.path.getsize(video_path)} bytes, "
                    f"Subtitle size: {os.path.getsize(subtitle_path)} bytes")
        
        # Use the subtitle processor for correction
        logger.info("Attempting advanced subtitle sync processing...")
        corrected_path = await subtitle_processor.correct_subtitle_sync(
            video_path, subtitle_path, offset_ms=0
        )
        
        # Move corrected file to processed directory
        if os.path.exists(corrected_path):
            final_path = os.path.join(PROCESSED_DIR, os.path.basename(corrected_path))
            shutil.move(corrected_path, final_path)
            logger.info(f"Subtitle sync processing completed successfully: {final_path}")
            return final_path
        else:
            raise Exception("Correction processing failed - no output file generated")
            
    except Exception as e:
        logger.warning(f"Advanced subtitle sync processing failed: {e}")
        logger.info("Falling back to basic correction processing...")
        
        try:
            # Fallback to simple processing
            await asyncio.sleep(1)
            
            # Read subtitle content
            logger.info(f"Reading subtitle content from: {subtitle_path}")
            with open(subtitle_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            logger.info(f"Subtitle content loaded - {len(content)} characters, {content.count(chr(10))} lines")
            
            # Basic correction - ensure proper format
            corrected_content = content.strip()
            if not corrected_content.endswith('\n'):
                corrected_content += '\n'
            
            # Save corrected version
            base_name = os.path.splitext(os.path.basename(subtitle_path))[0]
            corrected_path = os.path.join(PROCESSED_DIR, f"{base_name}_corrected.srt")
            
            logger.info(f"Writing corrected subtitle to: {corrected_path}")
            with open(corrected_path, 'w', encoding='utf-8') as f:
                f.write(corrected_content)
            
            logger.info(f"Basic subtitle correction completed: {corrected_path}")
            return corrected_path
            
        except Exception as fallback_error:
            logger.error(f"Fallback processing also failed: {fallback_error}")
            raise Exception(f"All subtitle processing methods failed: {str(e)} | Fallback: {str(fallback_error)}")

async def generate_subtitles_from_video(video_path: str, target_language: str = "en") -> str:
    """
    Generate subtitles from video using the subtitle processor
    """
    logger.info(f"Starting subtitle generation - Video: {os.path.basename(video_path)}, "
                f"Target Language: {target_language}")
    
    try:
        # Validate input file exists
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")
        
        video_size = os.path.getsize(video_path)
        logger.info(f"Video file validated - Size: {video_size} bytes ({video_size / (1024*1024):.2f} MB)")
        
        # Use the subtitle processor for generation
        logger.info("Attempting advanced subtitle generation using AI/ML...")
        generated_path = await subtitle_processor.generate_subtitles_from_audio(
            video_path, target_language
        )
        
        # Move generated file to processed directory
        if os.path.exists(generated_path):
            final_path = os.path.join(PROCESSED_DIR, os.path.basename(generated_path))
            shutil.move(generated_path, final_path)
            logger.info(f"Subtitle generation completed successfully: {final_path}")
            return final_path
        else:
            raise Exception("Subtitle generation failed - no output file generated")
            
    except Exception as e:
        logger.warning(f"Advanced subtitle generation failed: {e}")
        logger.info("Falling back to mock subtitle generation...")
        
        try:
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

4
00:00:16,000 --> 00:00:20,000
Mock content created for development and testing purposes.
"""
            
            # Save generated subtitles
            base_name = os.path.splitext(os.path.basename(video_path))[0]
            generated_path = os.path.join(PROCESSED_DIR, f"{base_name}_generated_{target_language}.srt")
            
            logger.info(f"Writing mock subtitles to: {generated_path}")
            with open(generated_path, 'w', encoding='utf-8') as f:
                f.write(mock_subtitles)
            
            logger.info(f"Mock subtitle generation completed: {generated_path}")
            return generated_path
            
        except Exception as fallback_error:
            logger.error(f"Mock subtitle generation also failed: {fallback_error}")
            raise Exception(f"All subtitle generation methods failed: {str(e)} | Fallback: {str(fallback_error)}")

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
@app.get("/", summary="Health Check", description="Comprehensive health check endpoint")
async def root():
    """Health check endpoint with system status"""
    try:
        # Check database connectivity
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        conn.close()
        
        # Check directory permissions
        upload_writable = os.access(UPLOAD_DIR, os.W_OK)
        processed_writable = os.access(PROCESSED_DIR, os.W_OK)
        
        # System status
        status_info = {
            "message": "Subtitle Sync Backend API is running",
            "status": "healthy",
            "version": "1.0.0",
            "timestamp": datetime.now().isoformat(),
            "database": {
                "connected": True,
                "user_count": user_count
            },
            "storage": {
                "upload_dir": UPLOAD_DIR,
                "upload_writable": upload_writable,
                "processed_dir": PROCESSED_DIR,
                "processed_writable": processed_writable
            },
            "features": {
                "file_processing": True,
                "user_authentication": True,
                "job_tracking": True,
                "file_downloads": True,
                "translations": True
            }
        }
        
        logger.info("Health check requested - System healthy")
        return status_info
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "message": "Subtitle Sync Backend API - Health check failed",
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

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
@app.post("/auth/register", response_model=Dict[str, Any], tags=["auth"],
          summary="Register User", description="Register a new user account")
async def register_user(
    username: str = Form(..., description="Username"),
    password: str = Form(..., description="Password"),
    email: Optional[str] = Form(None, description="Email address"),
    role: str = Form("user", description="User role")
):
    """Register a new user account"""
    try:
        # Import auth utilities
        from auth import UserAuth, session_manager
        
        # Validate password strength
        password_validation = UserAuth.validate_password_strength(password)
        if not password_validation["is_valid"]:
            raise HTTPException(
                status_code=400, 
                detail=f"Password validation failed: {', '.join(password_validation['issues'])}"
            )
        
        # Hash password
        hashed_password = UserAuth.hash_password(password)
        
        # Store user in database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO users (username, email, password_hash, role, created_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (username, email, hashed_password, role))
            
            user_id = cursor.lastrowid
            conn.commit()
            
            logger.info(f"User registered successfully: {username} (ID: {user_id})")
            
            # Create session
            session_data = session_manager.create_session(user_id, username, role)
            
            return {
                "message": "User registered successfully",
                "user_id": user_id,
                "username": username,
                "access_token": session_data["access_token"],
                "token_type": "bearer"
            }
            
        except sqlite3.IntegrityError as e:
            if "username" in str(e):
                raise HTTPException(status_code=400, detail="Username already exists")
            elif "email" in str(e):
                raise HTTPException(status_code=400, detail="Email already registered")
            else:
                raise HTTPException(status_code=400, detail="Registration failed")
        finally:
            conn.close()
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(status_code=500, detail="Registration failed")

# PUBLIC_INTERFACE  
@app.post("/auth/login", response_model=Dict[str, Any], tags=["auth"],
          summary="Login User", description="Authenticate user and get access token")
async def login_user(
    email: str = Form(..., description="Email or username"),
    password: str = Form(..., description="Password")
):
    """Authenticate user and return access token"""
    try:
        # Import auth utilities
        from auth import UserAuth, session_manager
        
        # Get user from database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Try to find user by email or username
        cursor.execute("""
            SELECT id, username, email, password_hash, role
            FROM users
            WHERE email = ? OR username = ?
        """, (email, email))
        
        user = cursor.fetchone()
        conn.close()
        
        if not user:
            logger.warning(f"Login attempt with invalid credentials: {email}")
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        # Verify password
        if not UserAuth.verify_password(password, user['password_hash']):
            logger.warning(f"Login attempt with wrong password: {email}")
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        # Create session
        session_data = session_manager.create_session(
            user['id'], user['username'], user['role']
        )
        
        logger.info(f"User logged in successfully: {user['username']} (ID: {user['id']})")
        
        return {
            "message": "Login successful",
            "user_id": user['id'],
            "username": user['username'],
            "role": user['role'],
            "access_token": session_data["access_token"],
            "refresh_token": session_data["refresh_token"],
            "token_type": "bearer"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(status_code=500, detail="Login failed")

# PUBLIC_INTERFACE
@app.get("/jobs/{job_id}/status", response_model=JobResponse, tags=["jobs"],
         summary="Get Job Status", description="Get status and progress of a processing job")
async def get_job_status(
    job_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Get job status and progress"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT j.*, v.filename as video_filename, s.filename as subtitle_filename
            FROM jobs j
            LEFT JOIN videos v ON j.video_id = v.id
            LEFT JOIN subtitles s ON j.subtitle_id = s.id
            WHERE j.id = ? AND j.user_id = ?
        """, (job_id, current_user['id']))
        
        job = cursor.fetchone()
        conn.close()
        
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Calculate progress based on status
        progress_map = {
            "pending": 0,
            "running": 50,
            "complete": 100,
            "failed": 0
        }
        
        progress = progress_map.get(job['status'], 0)
        
        logger.info(f"Job status requested: {job_id} - Status: {job['status']}")
        
        return JobResponse(
            id=job['id'],
            job_type=job['job_type'],
            status=job['status'],
            progress=progress,
            result_url=job['result_url'],
            created_at=job['created_at'],
            completed_at=job['completed_at']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get job status")

# PUBLIC_INTERFACE
@app.get("/subtitles/{subtitle_id}/download", tags=["subtitles"],
         summary="Download Subtitle File", description="Download a processed subtitle file")
async def download_subtitle_file(
    subtitle_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Download subtitle file"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT filename FROM subtitles
            WHERE id = ? AND user_id = ?
        """, (subtitle_id, current_user['id']))
        
        result = cursor.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="Subtitle file not found")
        
        # Check both upload and processed directories
        filename = result['filename']
        upload_path = os.path.join(UPLOAD_DIR, filename)
        processed_path = os.path.join(PROCESSED_DIR, filename)
        
        file_path = None
        if os.path.exists(processed_path):
            file_path = processed_path
        elif os.path.exists(upload_path):
            file_path = upload_path
        
        if not file_path:
            raise HTTPException(status_code=404, detail="Subtitle file not found on disk")
        
        logger.info(f"Subtitle file download requested: {subtitle_id} - {filename}")
        
        return FileResponse(
            file_path,
            media_type='application/octet-stream',
            filename=filename
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading subtitle file: {e}")
        raise HTTPException(status_code=500, detail="Failed to download file")
    finally:
        conn.close()

# PUBLIC_INTERFACE
@app.post("/subtitles/{subtitle_id}/translate", response_model=JobResponse, tags=["translation"],
          summary="Request Translation", description="Request translation of subtitle file to target language")
async def request_subtitle_translation(
    subtitle_id: int,
    target_language: str = Form(..., description="Target language code (e.g., 'es', 'fr', 'de')"),
    current_user: dict = Depends(get_current_user),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """Request translation of subtitle file"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verify subtitle exists and belongs to user
        cursor.execute("""
            SELECT id, filename FROM subtitles
            WHERE id = ? AND user_id = ?
        """, (subtitle_id, current_user['id']))
        
        subtitle = cursor.fetchone()
        if not subtitle:
            raise HTTPException(status_code=404, detail="Subtitle file not found")
        
        # Create translation job
        cursor.execute("""
            INSERT INTO jobs (user_id, subtitle_id, job_type, status, created_at)
            VALUES (?, ?, 'translation', 'pending', CURRENT_TIMESTAMP)
        """, (current_user['id'], subtitle_id))
        
        job_id = cursor.lastrowid
        conn.commit()
        
        # Start background translation task
        background_tasks.add_task(process_translation_job, job_id, target_language)
        
        logger.info(f"Translation job created: {job_id} for subtitle {subtitle_id} to {target_language}")
        
        return JobResponse(
            id=job_id,
            job_type="translation",
            status="pending",
            progress=0,
            result_url=None,
            created_at=datetime.now().isoformat(),
            completed_at=None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error requesting translation: {e}")
        raise HTTPException(status_code=500, detail="Failed to request translation")
    finally:
        conn.close()

async def process_translation_job(job_id: int, target_language: str):
    """Background task to process translation job"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Update job status to running
        cursor.execute("UPDATE jobs SET status = 'running' WHERE id = ?", (job_id,))
        conn.commit()
        
        # Get job and subtitle details
        cursor.execute("""
            SELECT j.*, s.filename
            FROM jobs j
            JOIN subtitles s ON j.subtitle_id = s.id
            WHERE j.id = ?
        """, (job_id,))
        
        job = cursor.fetchone()
        if not job:
            raise Exception("Job not found")
        
        # Find subtitle file
        filename = job['filename']
        upload_path = os.path.join(UPLOAD_DIR, filename)
        processed_path = os.path.join(PROCESSED_DIR, filename)
        
        source_path = processed_path if os.path.exists(processed_path) else upload_path
        if not os.path.exists(source_path):
            raise Exception("Source subtitle file not found")
        
        # Perform translation
        translated_path = await translate_subtitles(source_path, target_language)
        
        # Update job with results
        if translated_path and os.path.exists(translated_path):
            result_filename = os.path.basename(translated_path)
            cursor.execute("""
                UPDATE jobs SET status = 'complete', result_url = ?, completed_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (f"/download/{result_filename}", job_id))
            
            logger.info(f"Translation job completed: {job_id}")
        else:
            cursor.execute("UPDATE jobs SET status = 'failed' WHERE id = ?", (job_id,))
            logger.error(f"Translation job failed: {job_id}")
        
        conn.commit()
        
    except Exception as e:
        logger.error(f"Translation job {job_id} failed: {e}")
        cursor.execute("UPDATE jobs SET status = 'failed' WHERE id = ?", (job_id,))
        conn.commit()
    finally:
        conn.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
