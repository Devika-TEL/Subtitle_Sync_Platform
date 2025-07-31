import os
import sys
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, status, Depends, Request, Path as FPath
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Any
from uuid import uuid4
from pathlib import Path
from datetime import datetime

# --- ORM & Database Imports ---
# Dynamically find the Database directory (for local/dev or prod reliably)
DATABASE_PATH = str((Path(__file__).resolve().parent.parent / "Database"))
if DATABASE_PATH not in sys.path:
    sys.path.insert(0, DATABASE_PATH)

try:
    import models as models
    import init_db as db_init
except ModuleNotFoundError:
    try:
        from Database import models as models
        from Database import init_db as db_init
    except ModuleNotFoundError:
        raise ImportError(
            "Unable to import 'models' and 'init_db' from 'Database'. "
            "Check that Subtitle_Sync_Platform/Database/ is present and Python path is correctly set. "
            "This is needed so FastAPI backend can use database models."
        )

from sqlalchemy.orm import sessionmaker, Session

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

# ------------------------------------------------------------------------------
app = FastAPI(
    title="Subtitle Sync Platform Backend API",
    description="APIs for subtitle-audio sync, subtitle generation, and management.",
    version="1.0.0"
)

# Enable CORS for development (allow frontend on port 3000/3001)
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
    "*"
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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

# --------------- (Truncated CRUD routes and class definitions for brevity - keep as in previous version!) -----------------
# Copy all your existing Video, Subtitle, Job CRUD, correction/generation endpoints, and diagnostics routes here as-is from before

# PUBLIC_INTERFACE
@app.get("/api/health", tags=["Diagnostics"], summary="Health Check", description="Backend health and database connectivity diagnostics", response_description="Health status object")
async def health_check():
    """
    Health check endpoint for backend diagnostics and connectivity.
    Returns a JSON object with status and message. Useful for deployment checks or frontend connectivity testing.
    """
    try:
        db_status = False
        db_msg = ""
        try:
            with engine.connect() as conn:
                conn.execute("SELECT 1")
            db_status = True
            db_msg = "OK"
        except Exception as db_ex:
            db_msg = str(db_ex)
        return JSONResponse(
            status_code=200,
            content={
                "status": "ok",
                "backend": "ok",
                "database": "ok" if db_status else "error",
                "database_msg": db_msg
            }
        )
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "backend": "error",
                "details": str(exc)
            }
        )

if __name__ == "__main__":
    # Port 3001 as standard backend port for dev, aligned with frontend docs
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=3001, reload=True)
    # Tip: If port 3001 is already in use, ensure no other process is blocking it or adjust both frontend & backend configs to match the selected port.
