import os
import tempfile
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from pathlib import Path

# Placeholder imports for actual processing logic
# from subtitle_processing_module import perform_correction, generate_subtitle

app = FastAPI(
    title="Subtitle Sync Platform Backend API",
    description="""API for subtitle-audio synchronization, correction, and subtitle generation using large language models.
Receives video and subtitle file uploads, returns corrected or generated subtitle files directly as downloadable responses.
""",
    version="1.0.0",
    openapi_tags=[
        {"name": "Subtitle Correction", "description": "Endpoints for subtitle-audio synchronization and correction."},
        {"name": "Subtitle Generation", "description": "Endpoints for generating subtitles and translations."}
    ],
)

origins = [
    "*",  # Adjust for environment
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _move_upload_to_temp(uploaded_file: UploadFile, suffix: str = "") -> str:
    """Save an uploaded file to a temp directory and return the path."""
    suffix = suffix or Path(uploaded_file.filename).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as out_file:
        out_file.write(uploaded_file.file.read())
        tmp_path = out_file.name
    uploaded_file.file.close()
    return tmp_path

def _cleanup_file(filepath: str):
    """Remove a temporary file if it exists."""
    try:
        os.remove(filepath)
    except Exception:
        pass

# PUBLIC_INTERFACE
@app.post("/api/correction", tags=["Subtitle Correction"],
          summary="Synchronize and correct subtitle file",
          description="""
Upload a video file and a subtitle file.
Performs subtitle-audio synchronization and applies corrections.
Returns the corrected subtitle file directly as a downloadable response in the same format as the input.

**Input files:**
- video_file: Video file (any supported format)
- subtitle_file: Subtitle file (e.g., .srt, .vtt, etc.)

**Response:**
- Returns: FileResponse, corrected subtitle file in same format as uploaded.

**Usage:** POST as multipart/form-data.
""")
async def correct_subtitle(
    video_file: UploadFile = File(..., description="Video file"),
    subtitle_file: UploadFile = File(..., description="Subtitle file (e.g., .srt, .vtt)")
):
    # Save uploads to temp files
    video_temp_path = _move_upload_to_temp(video_file)
    subtitle_temp_path = _move_upload_to_temp(subtitle_file)
    # Determine the output subtitle path
    output_suffix = Path(subtitle_file.filename).suffix
    output_temp = tempfile.NamedTemporaryFile(delete=False, suffix=output_suffix)
    output_temp_path = output_temp.name
    output_temp.close()

    try:
        # --- PLACEHOLDER: Your correction logic should process files here ---
        # For demonstration, just copy input subtitle as output
        with open(subtitle_temp_path, "rb") as fin, open(output_temp_path, "wb") as fout:
            fout.write(fin.read())
        # In real case, call correction function (uncomment and adapt):
        # perform_correction(video_temp_path, subtitle_temp_path, output_temp_path)
        # ---------------------------------------------------------------
        filename_out = f"corrected_{subtitle_file.filename}"
        headers = {'Content-Disposition': f'attachment; filename="{filename_out}"'}
        return FileResponse(
            output_temp_path,
            media_type="application/octet-stream",
            filename=filename_out,
            headers=headers,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Correction failed: {e}")
    finally:
        _cleanup_file(video_temp_path)
        _cleanup_file(subtitle_temp_path)
        # The output file will be automatically deleted by FileResponse once sent

# PUBLIC_INTERFACE
@app.post("/api/generation", tags=["Subtitle Generation"],
          summary="Generate subtitles for a video",
          description="""
Upload a video file to generate subtitles in the video's native language (and optionally translations).
Returns a generated subtitle file directly as a downloadable response.

**Input files:**
- video_file: Video file (any supported format)

**Optional parameters:**
- language (str, query or form): target language for subtitle (leave blank for native)

**Response:**
- Returns: FileResponse, generated subtitle file.

**Usage:** POST as multipart/form-data.
""")
async def generate_subtitle(
    video_file: UploadFile = File(..., description="Video file"),
    language: Optional[str] = None
):
    # Save uploads to temp files
    video_temp_path = _move_upload_to_temp(video_file)
    # Determine output subtitle path (.srt by default)
    output_temp = tempfile.NamedTemporaryFile(delete=False, suffix=".srt")
    output_temp_path = output_temp.name
    output_temp.close()

    try:
        # --- PLACEHOLDER: Your generation logic should process files here ---
        # For demonstration, create a dummy SRT file
        dummy_content = "1\n00:00:00,000 --> 00:00:02,000\n[Generated subtitle]\n"
        with open(output_temp_path, "w", encoding="utf-8") as fout:
            fout.write(dummy_content)
        # In real case, call generation function (uncomment and adapt):
        # generate_subtitle_file(video_temp_path, output_temp_path, language)
        # ---------------------------------------------------------------
        filename_out = f"generated_{video_file.filename.rsplit('.', 1)[0]}.srt"
        headers = {'Content-Disposition': f'attachment; filename="{filename_out}"'}
        return FileResponse(
            output_temp_path,
            media_type="application/x-subrip",
            filename=filename_out,
            headers=headers,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Subtitle generation failed: {e}")
    finally:
        _cleanup_file(video_temp_path)

# PUBLIC_INTERFACE
@app.get("/docs/websocket-info", tags=["Subtitle Correction", "Subtitle Generation"])
async def get_websocket_usage():
    """
    Returns information about WebSocket (if supported in the future).
    """
    return JSONResponse({"message": "WebSocket interfaces are not currently supported. All processing is synchronous."})

# Remove all job/status related routes and state. All endpoints now return results directly.

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
