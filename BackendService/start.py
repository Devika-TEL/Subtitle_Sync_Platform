"""
Uvicorn entrypoint for running the FastAPI app.
"""

import uvicorn
from config import get_settings


def main():
    settings = get_settings()
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )


if __name__ == "__main__":
    main()
