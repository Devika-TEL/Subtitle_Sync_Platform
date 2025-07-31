import os
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any
import uuid
from pydantic import BaseModel, Field

# PUBLIC_INTERFACE
def create_app():
    """Create and configure FastAPI app for subtitle sync platform backend."""
    app = FastAPI(
        title="Subtitle Sync Platform API",
        description="Backend service for subtitle-audio synchronization, subtitle correction, and generation.",
        version="1.0.0",
        openapi_tags=[
            {"name": "Jobs", "description": "Job submission, status, and management"},
            {"name": "Files", "description": "Subtitle and video file upload/download endpoints"}
        ]
    )

    # Allow CORS for dev: adjust origins as needed
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Restrict to the frontend or deployment domain in production!
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    return app

app = create_app()

# --- "Database" substitute for demo --- #
JOBS: Dict[str, Dict[str, Any]] = {}
JOB_FILES_DIR = "job_outputs"
os.makedirs(JOB_FILES_DIR, exist_ok=True)

class JobSubmissionResponse(BaseModel):
    job_id: str = Field(..., description="Unique job identifier")
    status: str = Field(..., description="Current status of the job (queued, processing, complete, failed)")
    result_url: str = Field(None, description="URL for downloading result file, populated upon completion")

class JobStatusResponse(BaseModel):
    job_id: str = Field(..., description="Unique job identifier")
    status: str = Field(..., description="Job status")
    download_url: str = Field(None, description="Direct download URL (populated when ready)")
    detail: str = Field(None, description="Job detail or error (optional)")

ALLOWED_EXTENSIONS = {'.srt', '.vtt', '.ass', '.sub', '.txt'}  # Expand as needed

def get_result_file_path(job_id: str) -> str:
    """Get absolute path to job output file by job id."""
    for ext in ALLOWED_EXTENSIONS:
        candidate = os.path.join(JOB_FILES_DIR, f"{job_id}_result{ext}")
        if os.path.exists(candidate):
            return candidate
    # Not found
    return None

def do_correction(sub_path: str, job_id: str) -> str:
    """
    Dummy subtitle correction job for demonstration - replace with real logic.
    For demo, just copy the input file as output with new name.
    """
    # Detect extension
    _, ext = os.path.splitext(sub_path)
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError("Unsupported subtitle file extension")
    out_path = os.path.join(JOB_FILES_DIR, f"{job_id}_result{ext}")
    # Simulate correction (copy file for demo)
    with open(sub_path, "rb") as fin, open(out_path, "wb") as fout:
        fout.write(fin.read())
    return out_path

# PUBLIC_INTERFACE
@app.post("/jobs/submit", response_model=JobSubmissionResponse, tags=["Jobs"])
async def submit_job(background_tasks: BackgroundTasks, subtitle_file: UploadFile = File(...)):
    """
    Submit a subtitle correction job. Accepts a subtitle file, starts background processing, returns job ID.
    """
    # Ensure subtitle format
    _, ext = os.path.splitext(subtitle_file.filename)
    if ext.lower() not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported subtitle format.")
    job_id = str(uuid.uuid4())
    # Save uploaded file temporarily
    in_path = os.path.join(JOB_FILES_DIR, f"{job_id}_input{ext}")
    with open(in_path, "wb") as out_f:
        data = await subtitle_file.read()
        out_f.write(data)
    # Register job in "DB"
    JOBS[job_id] = {
        "status": "queued",
        "input": in_path,
        "output": None,
        "detail": ""
    }
    # Launch background correction
    background_tasks.add_task(run_job, job_id)
    return JobSubmissionResponse(
        job_id=job_id,
        status="queued",
        result_url=None
    )

def run_job(job_id: str):
    """
    Actual execution for the job.
    """
    try:
        JOBS[job_id]["status"] = "processing"
        res_path = do_correction(JOBS[job_id]["input"], job_id)
        JOBS[job_id]["output"] = res_path
        JOBS[job_id]["status"] = "complete"
        # Compose result download URL
        JOBS[job_id]["download_url"] = f"/jobs/{job_id}/result"
    except Exception as e:
        JOBS[job_id]["status"] = "failed"
        JOBS[job_id]["detail"] = str(e)
        JOBS[job_id]["output"] = None
        JOBS[job_id]["download_url"] = None

# PUBLIC_INTERFACE
@app.get("/jobs/{job_id}/status", response_model=JobStatusResponse, tags=["Jobs"])
async def get_job_status(job_id: str):
    """
    Query the current status of a subtitle correction/generation job.
    Will return a download URL when processing is complete.
    """
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    # Compose download URL if ready for download
    download_url = None
    if job.get("status") == "complete" and job.get("output"):
        download_url = f"/jobs/{job_id}/result"
    return JobStatusResponse(
        job_id=job_id,
        status=job["status"],
        download_url=download_url,
        detail=job.get("detail", "")
    )

# PUBLIC_INTERFACE
@app.get("/jobs/{job_id}/result", tags=["Files"])
async def download_job_result(job_id: str):
    """
    Download the resulting corrected/generated subtitle file for a given job.
    Returns a file download if the job is complete.
    Uses FastAPI's FileResponse for safe, robust serving.
    """
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] != "complete" or not job.get("output"):
        raise HTTPException(status_code=400, detail="Job not finished or error occurred")
    file_path = job["output"]
    if not (file_path and os.path.exists(file_path)):
        raise HTTPException(status_code=404, detail="Output file missing")
    # Serve with correct content type and robust handling
    filename = os.path.basename(file_path)
    return FileResponse(
        file_path,
        media_type="application/octet-stream",
        filename=filename
    )

# PUBLIC_INTERFACE
@app.get("/", tags=["Misc"])
async def root():
    """Health check and welcome endpoint."""
    return {"status": "ok", "message": "Subtitle Sync Platform Backend API"}

# PUBLIC_INTERFACE
@app.get("/api-docs", tags=["Misc"])
async def docs_link():
    """Returns direct OpenAPI JSON and Swagger UI docs URLs."""
    return {
        "openapi_json_url": "/openapi.json",
        "swagger_ui_url": "/docs"
    }

# If run as module/script
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
