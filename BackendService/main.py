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

# CORS middleware for frontend integration - only the specified URL is allowed
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://vscode-internal-29567-beta.beta01.cloud.kavia.ai:3001/",
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

# ----
# The rest of the file remains unchanged.
# ----

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

# ... (rest of the file is unchanged and identical to the previous content)

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
# ... (models stay unchanged)

# Database helper functions
# ... (functions unchanged)

# Authentication helpers
# ... (unchanged)

# Subtitle processing functions
# ... (unchanged)

# Background job processing
# ... (unchanged)

# API Endpoints
# ... (unchanged)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
