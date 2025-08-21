"""
Configuration management for the Backend Service.

Environment variables (set in .env at deployment runtime):
- BACKEND_HOST: Host to bind the FastAPI app (default: 0.0.0.0)
- BACKEND_PORT: Port to listen on (default: 8000)
- DEBUG: Enable debug/reload (default: false)
- CORS_ALLOW_ORIGINS: Comma-separated list of origins allowed by CORS (default: *)
- UPLOAD_DIR: Directory to store uploaded files (default: ./uploads)
- PROCESSED_DIR: Directory to store processed output files (default: ./processed)
- WORK_DIR: Working directory for temp files (default: ./work)
- LLM_PROVIDER: LLM provider identifier (optional)
- LLM_API_KEY: API key for LLM provider (optional)
- STT_PROVIDER: Speech-to-text provider identifier (optional)
- STT_API_KEY: API key for STT provider (optional)

Note: Do not hardcode secrets. The orchestrator/CI will inject environment values.
"""

from functools import lru_cache
from dataclasses import dataclass
import os
from pathlib import Path
from typing import List

# Load environment variables from a .env file if present.
# This enables local development without exporting vars manually.
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    # dotenv is optional; if not available, the environment must provide vars.
    pass


@dataclass
class Settings:
    HOST: str
    PORT: int
    DEBUG: bool
    CORS_ALLOW_ORIGINS: List[str]
    UPLOAD_DIR: Path
    PROCESSED_DIR: Path
    WORK_DIR: Path
    LLM_PROVIDER: str
    LLM_API_KEY: str
    STT_PROVIDER: str
    STT_API_KEY: str


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load settings from environment with sensible defaults."""
    host = os.getenv("BACKEND_HOST", "0.0.0.0")
    port = int(os.getenv("BACKEND_PORT", "8000"))
    debug_env = os.getenv("DEBUG", "false").lower()
    debug = debug_env in ("1", "true", "yes", "on")

    cors_raw = os.getenv("CORS_ALLOW_ORIGINS", "*")
    cors_list = [o.strip() for o in cors_raw.split(",")] if cors_raw else ["*"]

    upload_dir = Path(os.getenv("UPLOAD_DIR", "./uploads")).resolve()
    processed_dir = Path(os.getenv("PROCESSED_DIR", "./processed")).resolve()
    work_dir = Path(os.getenv("WORK_DIR", "./work")).resolve()

    return Settings(
        HOST=host,
        PORT=port,
        DEBUG=debug,
        CORS_ALLOW_ORIGINS=cors_list,
        UPLOAD_DIR=upload_dir,
        PROCESSED_DIR=processed_dir,
        WORK_DIR=work_dir,
        LLM_PROVIDER=os.getenv("LLM_PROVIDER", ""),
        LLM_API_KEY=os.getenv("LLM_API_KEY", ""),
        STT_PROVIDER=os.getenv("STT_PROVIDER", ""),
        STT_API_KEY=os.getenv("STT_API_KEY", ""),
    )
