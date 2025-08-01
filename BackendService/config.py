from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache

# PUBLIC_INTERFACE
class Settings(BaseSettings):
    """Application configuration managed via environment variables or .env file."""
    GEMINI_API_KEY: str = Field(..., description="API Key for Gemini LLM Integration")
    DATABASE_URL: str = Field(..., description="Database connection string/URL")

    class Config:
        env_file = ".env"
        case_sensitive = True

# Use lru_cache to ensure that settings are only loaded and instantiated once
@lru_cache()
def get_settings():
    """Returns a cached Settings instance."""
    return Settings()

# Exported singleton for use throughout the backend
settings: Settings = get_settings()
