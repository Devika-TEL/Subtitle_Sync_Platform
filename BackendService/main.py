from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from typing import Optional
import os
import shutil

# PUBLIC_INTERFACE
def get_app():
    """
    Create and configure the FastAPI application for the Subtitle Sync Platform.

    Returns:
        FastAPI: Configured FastAPI app instance.
    """
    app = FastAPI(
        title="Subtitle Sync Platform Backend",
        description="Backend API for subtitle-audio synchronization and subtitle generation/correction.",
        version="1.0.0"
    )

    # Allow CORS from frontend
    origins = [
        "http://localhost:3000",
        "http://localhost:3001",
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Serve processed files and uploads as static files
    if not os.path.exists("uploads"):
        os.makedirs("uploads")
    app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

    # Sample health check endpoint
    @app.get("/api/health", tags=["Health"])
    # PUBLIC_INTERFACE
    def health_check():
        """Simple API health check endpoint."""
        return {"status": "ok"}

    # Endpoint: Upload video and subtitle file for processing
    @app.post("/api/process", summary="Upload video and subtitle for processing", tags=["Processing"])
    # PUBLIC_INTERFACE
    async def process_files(
        video: UploadFile = File(..., description="Video file"),
        subtitle: UploadFile = File(..., description="Subtitle file"),
    ):
        """
        Handle upload of video and subtitle file, simulate processing, and stage a processed file for download.

        Args:
            video (UploadFile): The uploaded video file.
            subtitle (UploadFile): The uploaded subtitle file.

        Returns:
            JSON with download URL or status.
        """
        # Save files (simulate)
        video_save = f"uploads/{video.filename}"
        subtitle_save = f"uploads/{subtitle.filename}"
        with open(video_save, "wb") as f:
            shutil.copyfileobj(video.file, f)
        with open(subtitle_save, "wb") as f:
            shutil.copyfileobj(subtitle.file, f)

        # Simulate processing, copy subtitle file to processed file for this demo
        processed_filename = "sample_processed_subtitle.srt"
        processed_path = os.path.join("uploads", processed_filename)
        shutil.copy(subtitle_save, processed_path)

        # Return download link relative to frontend
        download_url = f"/uploads/{processed_filename}"
        return {"download_url": download_url, "status": "complete"}

    # Endpoint: Download processed subtitle file
    @app.get("/uploads/{filename}", response_class=FileResponse, summary="Download processed subtitle", tags=["Download"])
    # PUBLIC_INTERFACE
    async def download_file(filename: str):
        """
        Download processed subtitle file by filename.

        Args:
            filename (str): Name of the file in the uploads folder.

        Returns:
            FileResponse: The file to download.
        """
        file_path = os.path.join("uploads", filename)
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")
        return FileResponse(file_path, media_type="application/octet-stream", filename=filename)

    return app

app = get_app()

