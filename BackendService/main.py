import os
import secrets
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Request
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

DOWNLOAD_BASE_URL = "/jobs"  # For building result URLs. In a real deployment use request.url_for or an absolute path.

def get_download_url(job_id: str, download_token: str = None) -> str:
    """Determine download URL for a given job; includes download_token if present for basic access control."""
    url = f"{DOWNLOAD_BASE_URL}/{job_id}/result"
    if download_token:
        url = f"{url}?token={download_token}"
    return url

class JobSubmissionResponse(BaseModel):
    job_id: str = Field(..., description="Unique job identifier")
    status: str = Field(..., description="Current status of the job (queued, processing, complete, failed)")
    result_url: str = Field(None, description="URL for downloading result file, populated upon completion")

class JobStatusResponse(BaseModel):
    job_id: str = Field(..., description="Unique job identifier")
    status: str = Field(..., description="Job status")
    download_url: str = Field(None, description="Publicly accessible URL for download if job is complete")
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
    Simulated subtitle correction. For production, insert real logic here.
    Detects file extension, checks support, and outputs result into job_outputs/.
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
    PUBLIC_INTERFACE
    Subtitle Correction Job Submission.
    - Accepts a subtitle file (multiple formats).
    - Starts job processing deferred.
    - Returns a unique job ID and initial status.
    """
    # Ensure subtitle format
    _, ext = os.path.splitext(subtitle_file.filename)
    if ext.lower() not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported subtitle format.")
    job_id = str(uuid.uuid4())

    # Save uploaded file temporarily (to job_outputs)
    in_path = os.path.join(JOB_FILES_DIR, f"{job_id}_input{ext}")
    with open(in_path, "wb") as out_f:
        data = await subtitle_file.read()
        out_f.write(data)
    # Generate secure random download token for job result (optional, for demo use)
    download_token = secrets.token_urlsafe(16)
    # Register job in "DB"
    JOBS[job_id] = {
        "status": "queued",
        "input": in_path,
        "output": None,
        "detail": "",
        "download_token": download_token,
        "download_url": None, # will be filled when ready
    }
    # Run job processing in background
    background_tasks.add_task(run_job, job_id)
    return JobSubmissionResponse(
        job_id=job_id,
        status="queued",
        result_url=None
    )

def run_job(job_id: str):
    """
    Perform subtitle correction/generation for job (invoked in background).
    Generates output, updates job state, and constructs download URL.
    """
    try:
        JOBS[job_id]["status"] = "processing"
        res_path = do_correction(JOBS[job_id]["input"], job_id)
        JOBS[job_id]["output"] = res_path
        JOBS[job_id]["status"] = "complete"
        # Compose result download URL, include token for basic security (optional)
        token = JOBS[job_id].get("download_token")
        JOBS[job_id]["download_url"] = get_download_url(job_id, token)
    except Exception as e:
        JOBS[job_id]["status"] = "failed"
        JOBS[job_id]["detail"] = str(e)
        JOBS[job_id]["output"] = None
        JOBS[job_id]["download_url"] = None

# PUBLIC_INTERFACE
@app.get("/jobs/{job_id}/status", response_model=JobStatusResponse, tags=["Jobs"])
async def get_job_status(job_id: str, request: Request = None):
    """
    PUBLIC_INTERFACE
    Query/monitor job status.
    Returns fields:
      - job_id
      - status (queued, processing, complete, failed)
      - detail (error message or processing notes)
      - download_url (direct access link for download, populated on complete)
    """
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    # Compose download URL if ready for download
    download_url = None
    if job.get("status") == "complete" and job.get("output"):
        token = job.get("download_token")
        download_url = get_download_url(job_id, token)

        # If request is supplied, can prepend base URL for absolute URLs (for production!)
        if request:
            base = str(request.base_url).rstrip("/")
            rel = download_url if download_url.startswith("/") else "/" + download_url
            download_url = base + rel  # Absolute URL for frontend use

    return JobStatusResponse(
        job_id=job_id,
        status=job["status"],
        download_url=download_url,
        detail=job.get("detail", "")
    )

# PUBLIC_INTERFACE
@app.get("/jobs/{job_id}/result", tags=["Files"])
async def download_job_result(job_id: str, token: str = None):
    """
    PUBLIC_INTERFACE
    Download the resulting/corrected/generated subtitle file for a job.
    - Requires job to be in 'complete' state
    - Checks result file existence/robust error handling
    - Optionally checks a secure download token (for demo; in real app, use user-level auth!)
    - Uses FileResponse for robust downloading
    """
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    # Access control: require token match if download_token is set
    expected_token = job.get("download_token")
    if expected_token and token != expected_token:
        raise HTTPException(status_code=403, detail="Download token invalid or missing")
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
    """
    Health check and welcome endpoint.
    """
    return {"status": "ok", "message": "Subtitle Sync Platform Backend API"}

# PUBLIC_INTERFACE
@app.get("/api-docs", tags=["Misc"])
async def docs_link():
    """
    Returns API documentation and OpenAPI discovery links.
    """
    return {
        "openapi_json_url": "/openapi.json",
        "swagger_ui_url": "/docs"
    }

# --- End of main.py --- #
# If run as module/script
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
