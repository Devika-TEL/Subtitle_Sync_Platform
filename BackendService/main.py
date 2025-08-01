from fastapi import FastAPI
import auth
import subtitle_processor
import job_processor

app = FastAPI(
    title="Subtitle Sync Platform",
    description="A backend for subtitle-audio sync and management.",
    version="1.0"
)

app.include_router(auth.router)
# Add additional routers as needed, e.g.:
# app.include_router(subtitle_processor.router)
# app.include_router(job_processor.router)
