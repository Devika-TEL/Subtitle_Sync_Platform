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
        logger.info(f"FileSizeMiddleware initialized with max upload size: {max_upload_size // (1024*1024)}MB")
    
    async def dispatch(self, request: Request, call_next):
        """Process request and handle file size validation"""
        
        # Check if this is a file upload endpoint
        if request.url.path in ["/process", "/videos/upload", "/subtitles/upload"]:
            # Get content length from headers
            content_length = request.headers.get("content-length")
            
            if content_length:
                try:
                    content_length = int(content_length)
                    logger.info(f"Upload request to {request.url.path} with content length: {content_length // (1024*1024)}MB")
                    
                    # Check if content length exceeds limit
                    if content_length > self.max_upload_size:
                        logger.warning(f"File upload rejected: size {content_length} exceeds limit {self.max_upload_size}")
                        # Let the error bubble up so CORSHeadersMiddleware can handle it
                        raise HTTPException(
                            status_code=413,
                            detail=f"File too large. Maximum size allowed: {self.max_upload_size // (1024*1024)}MB"
                        )
                except ValueError:
                    logger.warning(f"Invalid content-length header: {content_length}")
            else:
                # For multipart uploads without content-length, we'll check during processing
                logger.info(f"Upload request to {request.url.path} without content-length header (likely multipart)")
        
        try:
            # Continue with request processing
            response = await call_next(request)
            return response
        except Exception as e:
            # Handle any processing errors with proper CORS headers
            logger.error(f"Request processing error: {str(e)}")
            # This will be caught by CORSHeadersMiddleware for proper error response
            raise

class CORSHeadersMiddleware(BaseHTTPMiddleware):
    """Additional CORS middleware to ensure proper headers are set on all responses including errors"""
    
    def __init__(self, app):
        super().__init__(app)
        self.allowed_origins = [
            "http://localhost:3000",
            "http://localhost:3001", 
            "http://localhost:3002",
            "https://vscode-internal-32497-beta.beta01.cloud.kavia.ai:3000",
            "https://vscode-internal-32497-beta.beta01.cloud.kavia.ai:3002"
        ]
    
    def _add_cors_headers(self, response: Response, origin: str = None):
        """Add CORS headers to response"""
        if origin and (origin in self.allowed_origins or "beta01.cloud.kavia.ai" in origin):
            response.headers["access-control-allow-origin"] = origin
            response.headers["access-control-allow-credentials"] = "true"
            response.headers["access-control-allow-methods"] = "GET, POST, PUT, DELETE, OPTIONS"
            response.headers["access-control-allow-headers"] = "*"
            response.headers["access-control-expose-headers"] = "*"
    
    async def dispatch(self, request: Request, call_next):
        """Add CORS headers to all responses including error responses"""
        origin = request.headers.get("origin")
        
        # Handle preflight requests
        if request.method == "OPTIONS":
            from starlette.responses import Response
            response = Response()
            self._add_cors_headers(response, origin)
            return response
        
        try:
            response = await call_next(request)
        except HTTPException as e:
            # Create error response with CORS headers
            from fastapi.responses import JSONResponse
            response = JSONResponse(
                status_code=e.status_code,
                content={"detail": e.detail}
            )
            self._add_cors_headers(response, origin)
            return response
        except Exception as e:
            # Handle unexpected errors with CORS headers
            from fastapi.responses import JSONResponse
            logger.error(f"Unexpected error in CORS middleware: {e}")
            response = JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"}
            )
            self._add_cors_headers(response, origin)
            return response
        
        # Add CORS headers to successful responses
        self._add_cors_headers(response, origin)
        return response
