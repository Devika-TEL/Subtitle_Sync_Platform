import os

class Settings:
    """Application settings (no database support)."""
    SECRET_KEY = os.environ.get("SECRET_KEY", "secret-key")
    # Add any other non-database settings here

# PUBLIC_INTERFACE
def get_gemini_api_key():
    """
    Return the Gemini API key from the environment or config.

    Returns:
        str: Gemini API key

    Raises:
        RuntimeError: If the GEMINI_API_KEY environment variable is missing
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY environment variable is not set. "
            "Please set it in your environment or .env file."
        )
    return api_key
