from pydantic import BaseSettings, Field

# PUBLIC_INTERFACE
class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    Add more fields as necessary for config and secrets.
    """
    DB_URI: str = Field("sqlite:///./test.db", env="DATABASE_URL")
    GEMINI_API_KEY: str = Field(..., env="GEMINI_API_KEY")
    # Add additional config fields as needed

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

# Create and export the settings object
settings = Settings()

# Backward compatible access if code expects 'DB_URI' global
DB_URI = settings.DB_URI

# PUBLIC_INTERFACE
def get_gemini_api_key():
    """
    Fetch Gemini API key from the settings object.
    """
    api_key = settings.GEMINI_API_KEY
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set in environment variables.")
    return api_key
