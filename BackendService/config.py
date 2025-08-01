import os

class Settings:
    """Application settings (no database support)."""
    SECRET_KEY = os.environ.get("SECRET_KEY", "secret-key")
