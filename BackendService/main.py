import os
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, status, Depends, Request, Path as FPath
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Any
from uuid import uuid4
from pathlib import Path
from datetime import datetime

# --- ORM & Database Imports ---
import sys
sys.path.append(
    str(Path(__file__).resolve().parent.parent / "Database")
)
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError

import Database.models as models
import Database.init_db as db_init

# Initialize SQLAlchemy engine and session
engine = db_init.get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """Yield a database session for dependency injection (one per request)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app = FastAPI(
    title="Subtitle Sync Platform Backend",
    description="APIs for subtitle correction and generation workflows, powered by LLM",
    version="0.2.0",
    openapi_tags=[
        {"name": "Correction", "description": "Subtitle correction and compliance check endpoints"},
        {"name": "Generation", "description": "Subtitle and subtitle translation generation endpoints"},
        {"name": "Videos", "description": "Video metadata and file registry CRUD"},
        {"name": "Subtitles", "description": "Subtitle files metadata and CRUD"},
        {"name": "Jobs", "description": "Job processing status and control CRUD"}
    ],
)

# Automatically initialize DB on startup if needed
@app.on_event("startup")
def startup_event():
    db_init.create_db()

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

# ----------------- Pydantic Schemas --------------------

class VideoBase(BaseModel):
    filename: str
    original_path: Optional[str] = None
    duration: Optional[int] = None
    file_size: Optional[int] = None
    title: Optional[str] = None
    description: Optional[str] = None
    language: Optional[str] = None

class VideoCreate(VideoBase):
    pass

class VideoRead(VideoBase):
    id: int
    uploader_id: Optional[int]
    uploaded_at: datetime

    class Config:
        orm_mode = True

class SubtitleBase(BaseModel):
    video_id: int
    language: str
    version: Optional[int] = 1
    filename: str
    format: str
    file_path: str
    is_original: Optional[bool] = False
    notes: Optional[str] = None

class SubtitleCreate(SubtitleBase):
    pass

class SubtitleRead(SubtitleBase):
    id: int
    created_at: datetime
    creator_job_id: Optional[int]
    user_id: Optional[int]

    class Config:
        orm_mode = True

class JobBase(BaseModel):
    user_id: Optional[int] = None
    video_id: Optional[int]
    type: str = Field(..., description="Job type: 'correction' or 'generation'")
    status: Optional[str] = "pending"
    requested_language: Optional[str] = None
    input_subtitle_id: Optional[int] = None
    output_subtitle_id: Optional[int] = None
    progress: Optional[int] = 0
    message: Optional[str] = None

class JobCreate(JobBase):
    pass

class JobRead(JobBase):
    id: int
    created_at: datetime
    started_at: Optional[datetime]
    finished_at: Optional[datetime]

    class Config:
        orm_mode = True

# ---------------- Videos CRUD --------------------------

# PUBLIC_INTERFACE
@app.post("/api/videos/", tags=["Videos"], response_model=VideoRead)
def create_video(video_in: VideoCreate, db: Session = Depends(get_db)):
    """
    Create a new video record.
    """
    video = models.Video(**video_in.dict())
    db.add(video)
    db.commit()
    db.refresh(video)
    return video

# PUBLIC_INTERFACE
@app.get("/api/videos/", tags=["Videos"], response_model=List[VideoRead])
def get_videos(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    """
    List videos.
    """
    return db.query(models.Video).offset(skip).limit(limit).all()

# PUBLIC_INTERFACE
@app.get("/api/videos/{video_id}", tags=["Videos"], response_model=VideoRead)
def get_video(video_id: int, db: Session = Depends(get_db)):
    """
    Retrieve a single video record by id.
    """
    video = db.query(models.Video).filter(models.Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return video

# PUBLIC_INTERFACE
@app.put("/api/videos/{video_id}", tags=["Videos"], response_model=VideoRead)
def update_video(video_id: int, video_in: VideoCreate, db: Session = Depends(get_db)):
    """
    Update video record.
    """
    video = db.query(models.Video).filter(models.Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    for key, value in video_in.dict().items():
        setattr(video, key, value)
    db.commit()
    db.refresh(video)
    return video

# PUBLIC_INTERFACE
@app.delete("/api/videos/{video_id}", tags=["Videos"], response_model=dict)
def delete_video(video_id: int, db: Session = Depends(get_db)):
    """
    Delete a video record.
    """
    video = db.query(models.Video).filter(models.Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    db.delete(video)
    db.commit()
    return {"ok": True}

# ---------------- Subtitles CRUD --------------------------

# PUBLIC_INTERFACE
@app.post("/api/subtitles/", tags=["Subtitles"], response_model=SubtitleRead)
def create_subtitle(subtitle_in: SubtitleCreate, db: Session = Depends(get_db)):
    """
    Create a new subtitle record.
    """
    subtitle = models.Subtitle(**subtitle_in.dict())
    db.add(subtitle)
    db.commit()
    db.refresh(subtitle)
    return subtitle

# PUBLIC_INTERFACE
@app.get("/api/subtitles/", tags=["Subtitles"], response_model=List[SubtitleRead])
def get_subtitles(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    List subtitle records.
    """
    return db.query(models.Subtitle).offset(skip).limit(limit).all()

# PUBLIC_INTERFACE
@app.get("/api/subtitles/{subtitle_id}", tags=["Subtitles"], response_model=SubtitleRead)
def get_subtitle(subtitle_id: int, db: Session = Depends(get_db)):
    """
    Retrieve a single subtitle record by id.
    """
    sub = db.query(models.Subtitle).filter(models.Subtitle.id == subtitle_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Subtitle not found")
    return sub

# PUBLIC_INTERFACE
@app.put("/api/subtitles/{subtitle_id}", tags=["Subtitles"], response_model=SubtitleRead)
def update_subtitle(subtitle_id: int, subtitle_in: SubtitleCreate, db: Session = Depends(get_db)):
    """
    Update a subtitle record.
    """
    sub = db.query(models.Subtitle).filter(models.Subtitle.id == subtitle_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Subtitle not found")
    for key, value in subtitle_in.dict().items():
        setattr(sub, key, value)
    db.commit()
    db.refresh(sub)
    return sub

# PUBLIC_INTERFACE
@app.delete("/api/subtitles/{subtitle_id}", tags=["Subtitles"], response_model=dict)
def delete_subtitle(subtitle_id: int, db: Session = Depends(get_db)):
    """
    Delete a subtitle record.
    """
    sub = db.query(models.Subtitle).filter(models.Subtitle.id == subtitle_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Subtitle not found")
    db.delete(sub)
    db.commit()
    return {"ok": True}

# ---------------- Jobs CRUD --------------------------

# PUBLIC_INTERFACE
@app.post("/api/jobs/", tags=["Jobs"], response_model=JobRead)
def create_job(job_in: JobCreate, db: Session = Depends(get_db)):
    """
    Create a new job.
    """
    job = models.Job(**job_in.dict())
    db.add(job)
    db.commit()
    db.refresh(job)
    return job

# PUBLIC_INTERFACE
@app.get("/api/jobs/", tags=["Jobs"], response_model=List[JobRead])
def get_jobs(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    List jobs.
    """
    return db.query(models.Job).offset(skip).limit(limit).all()

# PUBLIC_INTERFACE
@app.get("/api/jobs/{job_id}", tags=["Jobs"], response_model=JobRead)
def get_job(job_id: int, db: Session = Depends(get_db)):
    """
    Retrieve a job by id.
    """
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

# PUBLIC_INTERFACE
@app.put("/api/jobs/{job_id}", tags=["Jobs"], response_model=JobRead)
def update_job(job_id: int, job_in: JobCreate, db: Session = Depends(get_db)):
    """
    Update a job.
    """
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    for key, value in job_in.dict().items():
        setattr(job, key, value)
    db.commit()
    db.refresh(job)
    return job

# PUBLIC_INTERFACE
@app.delete("/api/jobs/{job_id}", tags=["Jobs"], response_model=dict)
def delete_job(job_id: int, db: Session = Depends(get_db)):
    """
    Delete job by id.
    """
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    db.delete(job)
    db.commit()
    return {"ok": True}

# -------- Update correction/generation endpoints to record jobs/files ----------

def detect_subtitle_format(filename: str) -> str:
    ext = Path(filename).suffix.lower().strip(".")
    known = ["srt", "vtt", "ass", "sub", "txt", "dfxp", "sbv"]
    return ext if ext in known else "txt"

# PUBLIC_INTERFACE
@app.post("/api/correction", tags=["Correction"], summary="Upload video & subtitle for correction", status_code=201)
async def correction_upload(
    video_file: UploadFile = File(..., description="Video file for subtitle correction."),
    subtitle_file: UploadFile = File(..., description="Subtitle file to be checked and corrected."),
    db: Session = Depends(get_db),
):
    """
    Accepts a video file and a subtitle file, saves files, records files and new Job in database,
    then performs AI-based correction (timing, burnt-in text, compliance), and stores the corrected subtitle file.
    Returns a job identifier and result metadata.

    Args:
        video_file: UploadFile (required) - Video file for correction
        subtitle_file: UploadFile (required) - Subtitle file to check

    Returns:
        JSON object containing job_id and message
    """
    job_uuid = uuid4().hex
    job_dir = UPLOAD_BASE / job_uuid
    job_dir.mkdir(parents=True, exist_ok=True)

    video_path = save_upload_file(video_file, job_dir, "video" + Path(video_file.filename).suffix)
    subtitle_path = save_upload_file(subtitle_file, job_dir, "subtitle" + Path(subtitle_file.filename).suffix)

    # Create video record
    video_rec = models.Video(
        filename=video_file.filename,
        original_path=str(video_path),
        uploaded_at=datetime.utcnow()
    )
    db.add(video_rec)
    db.commit()
    db.refresh(video_rec)

    # Create subtitle record (is_original=True)
    subtitle_rec = models.Subtitle(
        video_id=video_rec.id,
        language="und",
        version=1,
        filename=subtitle_file.filename,
        format=detect_subtitle_format(subtitle_file.filename),
        file_path=str(subtitle_path),
        is_original=True,
        created_at=datetime.utcnow(),
        user_id=None
    )
    db.add(subtitle_rec)
    db.commit()
    db.refresh(subtitle_rec)

    # Create job record (status: in_progress)
    job_rec = models.Job(
        user_id=None,
        video_id=video_rec.id,
        type="correction",
        status="in_progress",
        input_subtitle_id=subtitle_rec.id,
        progress=10,
        created_at=datetime.utcnow(),
        message="Files uploaded. Correction started."
    )
    db.add(job_rec)
    db.commit()
    db.refresh(job_rec)

    # ---- ACTUAL CORRECTION STEP ----
    # This block acts as the business logic layer.
    # For demonstration, we use a stub function; replace this with LLM/AI integration.
    # Key tasks:
    # - Validate subtitle (timing, compliance)
    # - Detect and correct latency, burnt-in overlaps, rate/length problems
    # - Write corrected subtitle to disk and update database

    def correct_subtitles(sub_path: Path, vid_path: Path) -> (Path, str):
        """
        Stub for actual subtitle correction using LLM or library.
        Returns: (output_path, compliance_note)
        """
        # Dummy: just copy input to output and append note;
        # Replace with your LLM/pipeline/AI processing.
        corrected_sub_path = sub_path.parent / f"corrected_{sub_path.name}"
        with open(sub_path, "r", encoding="utf-8", errors="replace") as fin, \
             open(corrected_sub_path, "w", encoding="utf-8") as fout:
            for line in fin:
                fout.write(line)
            fout.write("\nNOTE: This file would be corrected (timing/compliance) by AI/LLM.\n")
        compliance_note = "Corrected by AI: latency/resync applied; checked for burnt-in text/OTT compliance."
        return corrected_sub_path, compliance_note

    try:
        corrected_subtitle_path, correction_note = correct_subtitles(subtitle_path, video_path)
        # Store result file/record
        corrected_subtitle_rec = models.Subtitle(
            video_id=video_rec.id,
            language="und",
            version=2,
            filename=f"corrected_{subtitle_file.filename}",
            format=detect_subtitle_format(subtitle_file.filename),
            file_path=str(corrected_subtitle_path),
            is_original=False,
            created_at=datetime.utcnow(),
            user_id=None,
            notes=correction_note
        )
        db.add(corrected_subtitle_rec)
        db.commit()
        db.refresh(corrected_subtitle_rec)

        # Update job for success
        job_rec.status = "success"
        job_rec.progress = 100
        job_rec.message = "Subtitle correction complete."
        job_rec.output_subtitle_id = corrected_subtitle_rec.id
        job_rec.finished_at = datetime.utcnow()
        db.commit()
        db.refresh(job_rec)

        return JSONResponse({
            "job_id": job_rec.id,
            "status": job_rec.status,
            "message": job_rec.message,
            "output_subtitle_id": corrected_subtitle_rec.id,
            "output_file_path": str(corrected_subtitle_path)
        }, status_code=status.HTTP_201_CREATED)
    except Exception as ex:
        # Update job for error
        job_rec.status = "error"
        job_rec.progress = 100
        job_rec.message = f"Correction failed: {ex}"
        job_rec.finished_at = datetime.utcnow()
        db.commit()
        return JSONResponse({
            "job_id": job_rec.id,
            "status": job_rec.status,
            "message": job_rec.message,
        }, status_code=500)

# PUBLIC_INTERFACE
@app.post("/api/generation", tags=["Generation"], summary="Upload video for subtitle generation", status_code=201)
async def generation_upload(
    video_file: UploadFile = File(..., description="Video file for generating subtitles."),
    language: str = Form(..., description="Output subtitle language (ISO code, e.g., 'en', 'es')."),
    db: Session = Depends(get_db),
):
    """
    Accepts a video file and language code, stores them and records a generation job.
    Runs the subtitle generation pipeline (stubbed). Outputs subtitles in the requested language and stores them.
    Returns a job identifier and result metadata.

    Args:
        video_file: UploadFile (required) - Video file for subtitle generation
        language: str (required) - Target output language code

    Returns:
        JSON object containing job_id and message
    """
    job_uuid = uuid4().hex
    job_dir = UPLOAD_BASE / job_uuid
    job_dir.mkdir(parents=True, exist_ok=True)

    video_path = save_upload_file(video_file, job_dir, "video" + Path(video_file.filename).suffix)
    meta_path = job_dir / "job_meta.txt"
    meta_path.write_text(f"language={language}")

    # Create video record
    video_rec = models.Video(
        filename=video_file.filename,
        original_path=str(video_path),
        uploaded_at=datetime.utcnow()
    )
    db.add(video_rec)
    db.commit()
    db.refresh(video_rec)

    # Create job record (status: in_progress)
    job_rec = models.Job(
        user_id=None,
        video_id=video_rec.id,
        type="generation",
        status="in_progress",
        requested_language=language,
        progress=10,
        created_at=datetime.utcnow(),
        message="Generation started."
    )
    db.add(job_rec)
    db.commit()
    db.refresh(job_rec)

    # ---- SUBTITLE GENERATION LOGIC ----
    # Use an LLM or speech-to-text module here.
    # Here, we mock/placeholder the output for demonstration.

    def generate_subtitles_from_video(video_path: Path, lang: str) -> (Path, str):
        """
        Stub for AI/LLM-based subtitle generation from video.
        Returns: (output_path, compliance_note)
        """
        out_sub = video_path.parent / f"generated_{lang}.srt"
        # Dummy SRT content for demo (replace with actual pipeline)
        srt_template = (
            "1\n00:00:00,000 --> 00:00:02,000\n[AI generated subtitle line 1 in {lang}]\n\n"
            "2\n00:00:02,001 --> 00:00:04,000\n[AI generated subtitle line 2...]\n\n"
        )
        with open(out_sub, "w", encoding="utf-8") as fout:
            fout.write(srt_template.format(lang=lang))
            fout.write(f"\nNOTE: This SRT is a placeholder; LLM would return real lines in language '{lang}'.\n")
        return out_sub, "Subtitle generated by AI ({}).".format(lang)

    try:
        generated_sub_path, gen_note = generate_subtitles_from_video(video_path, language)
        # Store generated subtitle
        subtitle_rec = models.Subtitle(
            video_id=video_rec.id,
            language=language,
            version=1,
            filename=f"generated_{language}.srt",
            format="srt",
            file_path=str(generated_sub_path),
            is_original=False,
            created_at=datetime.utcnow(),
            user_id=None,
            notes=gen_note
        )
        db.add(subtitle_rec)
        db.commit()
        db.refresh(subtitle_rec)

        # Update job status
        job_rec.status = "success"
        job_rec.progress = 100
        job_rec.message = f"Subtitle generation complete."
        job_rec.output_subtitle_id = subtitle_rec.id
        job_rec.finished_at = datetime.utcnow()
        db.commit()
        db.refresh(job_rec)

        return JSONResponse({
            "job_id": job_rec.id,
            "status": job_rec.status,
            "message": job_rec.message,
            "output_subtitle_id": subtitle_rec.id,
            "output_file_path": str(generated_sub_path)
        }, status_code=status.HTTP_201_CREATED)
    except Exception as ex:
        job_rec.status = "error"
        job_rec.progress = 100
        job_rec.message = f"Generation failed: {ex}"
        job_rec.finished_at = datetime.utcnow()
        db.commit()
        return JSONResponse({
            "job_id": job_rec.id,
            "status": job_rec.status,
            "message": job_rec.message,
        }, status_code=500)

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
