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
# Add additional routers as needed, e.g.:
# app.include_router(subtitle_processor_router)
# For job_processor, if it implements a router, uncomment below:
# app.include_router(job_processor_router)
