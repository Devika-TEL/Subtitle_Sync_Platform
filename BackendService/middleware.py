from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
import logging

class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        logger = logging.getLogger("uvicorn")
        logger.info(f"{request.method} {request.url}")
        response = await call_next(request)
        return response
