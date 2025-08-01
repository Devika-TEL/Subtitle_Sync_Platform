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
from auth import router as auth_router
from subtitle_processor import router as subtitle_processor_router
from job_processor import get_status  # if needed for router composition

app = FastAPI(
    title="Subtitle Sync Platform",
    description="A backend for subtitle-audio sync and management.",
    version="1.0"
)

app.include_router(auth_router)
app.include_router(subtitle_processor_router)
# For job_processor, if it implements a router, uncomment below:
# app.include_router(job_processor_router)
