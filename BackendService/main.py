"""
IMPORTANT FOR LOCAL DEVELOPMENT:
This backend service loads environment variables from a .env file using python-dotenv.
This guarantees environment variables (such as GEMINI_API_KEY) are always available, regardless of whether you
run the app via 'uvicorn', an IDE, or any other means. Do not rely solely on uvicorn's built-in .env loading.
This maximizes reliability and prevents environment-related bugs.

Best practice: Always use python-dotenv's load_dotenv() at the TOP of your FastAPI entrypoint.
"""

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI

# Import all main routers here, and assign tags/prefixes for organization in docs
from auth import router as auth_router
from subtitle_processor import router as subtitle_processor_router
# from job_processor import router as job_processor_router  # Uncomment if applicable

app = FastAPI(
    title="Subtitle Sync Platform Backend Service",
    description="API for audio-subtitle sync, subtitle generation, correction, validation, and translation.",
    version="1.0.0",
    docs_url="/docs",                     # Swagger UI endpoint
    openapi_url="/openapi.json",          # OpenAPI schema endpoint
    redoc_url="/redoc",                   # ReDoc docs endpoint
)

# PUBLIC_INTERFACE
# Add main routers - tag/prefix values improve docs clarity and grouping
app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
app.include_router(subtitle_processor_router, prefix="/subtitles", tags=["Subtitles"])
# app.include_router(job_processor_router, prefix="/jobs", tags=["Job Processing"])  # Enable if router is available

# Additional routers can be included above as needed.
