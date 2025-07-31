"""
Database schema definitions for the Subtitle Sync Platform.

Tables:
- User: Registered users, roles, and authentication info
- Video: Metadata for video uploads
- Subtitle: Subtitle records (multi-language, multi-version per video)
- Job: Processing jobs for correction/generation, status, progress
- Session: User session tracking (IP, login times, etc)
- AuditLog: Audit/action log entries (for admin/monitoring)
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, DateTime, Boolean, ForeignKey, Enum, Text, UniqueConstraint
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

# PUBLIC_INTERFACE
class User(Base):
    """
    Application users. Supports user roles (end user/admin).
    """
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    email = Column(String(255), nullable=False, unique=True, index=True)
    name = Column(String(128))
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login_at = Column(DateTime)

    # User may have many videos/jobs/sessions
    videos = relationship("Video", back_populates="uploader", cascade="all, delete-orphan")
    jobs = relationship("Job", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user", cascade="all, delete-orphan")


# PUBLIC_INTERFACE
class Video(Base):
    """
    Uploaded videos and their metadata.
    """
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True)
    uploader_id = Column(Integer, ForeignKey("users.id"))
    filename = Column(String(255), nullable=False)
    original_path = Column(String(512))  # Filesystem or storage path
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    duration = Column(Integer)  # Duration in seconds
    file_size = Column(Integer) # Size (bytes)
    title = Column(String(255))
    description = Column(Text)
    language = Column(String(12)) # ISO lang code (if known)
    # Subtitle and Job relationships
    subtitles = relationship("Subtitle", back_populates="video", cascade="all, delete-orphan")
    jobs = relationship("Job", back_populates="video", cascade="all, delete-orphan")
    uploader = relationship("User", back_populates="videos")

    # Add further fields (e.g., video resolution, frame rate) as needed.

# PUBLIC_INTERFACE
class Subtitle(Base):
    """
    Subtitle records - supports multiple versions and languages per video.
    """
    __tablename__ = "subtitles"

    id = Column(Integer, primary_key=True)
    video_id = Column(Integer, ForeignKey("videos.id"), nullable=False)
    language = Column(String(12), nullable=False)  # ISO code: 'en', 'es', etc.
    version = Column(Integer, default=1)  # For versioning per video/language
    filename = Column(String(255), nullable=False)
    format = Column(String(32), nullable=False) # 'srt', 'vtt', etc.
    file_path = Column(String(512), nullable=False)
    is_original = Column(Boolean, default=False) # True = as uploaded, False = generated/corrected
    created_at = Column(DateTime, default=datetime.utcnow)
    creator_job_id = Column(Integer, ForeignKey("jobs.id")) # Job that produced this (if generated)
    user_id = Column(Integer, ForeignKey("users.id")) # Who uploaded or triggered
    notes = Column(Text)  # E.g., "Compliant", "Translated", "Corrected by LLM"

    video = relationship("Video", back_populates="subtitles")
    creator_job = relationship("Job")
    user = relationship("User")

    __table_args__ = (
        # Prevent duplicate version for same video/lang
        UniqueConstraint('video_id', 'language', 'version', name='_video_lang_version_uc'),
    )

# PUBLIC_INTERFACE
class Job(Base):
    """
    Jobs for processing video/subtitles: stores operation type, status, timestamps, etc.
    """
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    video_id = Column(Integer, ForeignKey("videos.id"))
    type = Column(Enum("correction", "generation", name="job_type_enum"), nullable=False)
    status = Column(Enum("pending", "in_progress", "success", "error", "cancelled", name="job_status_enum"), default="pending")
    requested_language = Column(String(12))  # If generation/translation
    input_subtitle_id = Column(Integer, ForeignKey("subtitles.id")) # For correction jobs
    output_subtitle_id = Column(Integer, ForeignKey("subtitles.id")) # For output/corrected/generated
    progress = Column(Integer, default=0)  # % progress, for async status UI
    message = Column(Text) # Last status message or error
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime)
    finished_at = Column(DateTime)
    # Relations
    user = relationship("User", back_populates="jobs")
    video = relationship("Video", back_populates="jobs")
    input_subtitle = relationship("Subtitle", foreign_keys=[input_subtitle_id])
    output_subtitle = relationship("Subtitle", foreign_keys=[output_subtitle_id])

# PUBLIC_INTERFACE
class Session(Base):
    """
    Tracks user login sessions (with audit/monitoring fields).
    """
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    session_token = Column(String(255), unique=True, nullable=False)
    login_ip = Column(String(64))
    user_agent = Column(String(256))
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)

    user = relationship("User", back_populates="sessions")

# PUBLIC_INTERFACE
class AuditLog(Base):
    """
    Audit/action log (admin/monitoring).
    """
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    event_type = Column(String(64))  # e.g., 'login', 'job_start', 'subtitle_uploaded'
    event_details = Column(Text)
    event_time = Column(DateTime, default=datetime.utcnow)
    ip = Column(String(64))
    # Custom fields as needed per event type

    user = relationship("User", back_populates="audit_logs")
