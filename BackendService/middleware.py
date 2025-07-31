"""
Custom middleware for handling large file uploads and request size limits
"""

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import logging

logger = logging.getLogger(__name__)

class FileSizeMiddleware(BaseHTTPMiddleware):
    """Middleware to handle large file uploads and set appropriate limits"""
    
    def __init__(self, app, max_upload_size: int = 2 * 1024 * 1024 * 1024):  # 2GB default
        super().__init__(app)
        self.max_upload_size = max_upload_size
    
    async def dispatch(self, request: Request, call_next):
        """Process request and handle file size validation"""
        
        # Check if this is a file upload endpoint
        if request.url.path in ["/process", "/videos/upload", "/subtitles/upload"]:
            # Get content length from headers
            content_length = request.headers.get("content-length")
            
            if content_length:
                content_length = int(content_length)
                
                # Check if content length exceeds limit
                if content_length > self.max_upload_size:
                    logger.warning(f"File upload rejected: size {content_length} exceeds limit {self.max_upload_size}")
                    raise HTTPException(
                        status_code=413,
                        detail=f"File too large. Maximum size allowed: {self.max_upload_size // (1024*1024)}MB"
                    )
        
        # Continue with request processing
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            logger.error(f"Request processing error: {e}")
            # Don't re-raise HTTPExceptions as they're handled by FastAPI
            if isinstance(e, HTTPException):
                raise
            # For other exceptions, return a generic error
            raise HTTPException(status_code=500, detail="Internal server error")

class CORSHeadersMiddleware(BaseHTTPMiddleware):
    """Additional CORS middleware to ensure proper headers are set"""
    
    def __init__(self, app):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next):
        """Add additional CORS headers if needed"""
        
        response = await call_next(request)
        
        # Ensure CORS headers are present for all responses
        if not response.headers.get("access-control-allow-origin"):
            origin = request.headers.get("origin")
            if origin:
                # Check if origin is allowed (basic check)
                allowed_origins = [
                    "http://localhost:3000",
                    "http://localhost:3001", 
                    "http://localhost:3002",
                    "https://vscode-internal-32497-beta.beta01.cloud.kavia.ai:3002"
                ]
                
                # Check for cloud kavia.ai domains
                if origin in allowed_origins or "beta01.cloud.kavia.ai" in origin:
                    response.headers["access-control-allow-origin"] = origin
                    response.headers["access-control-allow-credentials"] = "true"
                    response.headers["access-control-allow-methods"] = "*"
                    response.headers["access-control-allow-headers"] = "*"
        
        return response
