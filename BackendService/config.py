import os

# Other config values...

DB_URI = os.getenv("DATABASE_URL", "sqlite:///./test.db")

# PUBLIC_INTERFACE
def get_gemini_api_key():
    """
    Fetch Gemini API key from environment variable.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set in environment variables.")
    return api_key
