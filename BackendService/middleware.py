"""
Custom middleware for the backend service.
"""

import time
from fastapi import Request, Response


# PUBLIC_INTERFACE
async def add_process_time_header(request: Request, call_next):
    """Middleware that adds X-Process-Time header to responses."""
    start = time.perf_counter()
    response: Response = await call_next(request)
    duration = (time.perf_counter() - start) * 1000.0
    response.headers["X-Process-Time-ms"] = f"{duration:.2f}"
    return response
