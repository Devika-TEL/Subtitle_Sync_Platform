import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "changeme-please")
    ALGORITHM: str = os.environ.get("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
    DB_URL: str = os.environ.get("DB_URL", "sqlite:///./test.db")
    LLM_API_KEY: str = os.environ.get("LLM_API_KEY", "")
    LLM_PROVIDER: str = os.environ.get("LLM_PROVIDER", "openai")
    ALLOW_ORIGINS: list = os.environ.get("ALLOW_ORIGINS", "").split(",") if os.environ.get("ALLOW_ORIGINS") else []
    FILE_STORAGE_PATH: str = os.environ.get("FILE_STORAGE_PATH", "processed")
    JOB_QUEUE_SYSTEM: str = os.environ.get("JOB_QUEUE_SYSTEM", "background")
    # Add more config/options as needed

settings = Settings()
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES

