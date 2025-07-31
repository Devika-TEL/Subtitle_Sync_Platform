"""
Application startup script for the Subtitle Sync Platform Backend

This script ensures the FastAPI backend runs on port 3001 by default,
to match the React frontend API expectations for /process and /ws endpoints.
"""

import uvicorn
import asyncio
import logging
import signal
import sys
import os
from pathlib import Path

# Add the current directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import get_config
from database import init_database
from job_processor import job_processor
from file_utils import file_manager

logger = logging.getLogger(__name__)


class BackendApplication:
    """Backend application manager"""
    
    def __init__(self):
        self.config = get_config()
        self.server = None
        self.shutdown_event = asyncio.Event()
        
    async def startup(self):
        """Initialize application components"""
        logger.info("Starting Subtitle Sync Backend...")
        
        try:
            # Initialize database
            logger.info("Initializing database...")
            init_database()
            
            # Setup directories
            logger.info("Setting up directories...")
            self._setup_directories()
            
            # Clean up old temporary files
            logger.info("Cleaning up temporary files...")
            file_manager.cleanup_temp_files()
            
            # Initialize job processor
            logger.info("Initializing job processor...")
            # Job processor is already initialized as a global instance
            
            logger.info("Backend startup completed successfully")
            
        except Exception as e:
            logger.error(f"Failed to start backend: {e}")
            raise
    
    async def shutdown(self):
        """Graceful shutdown"""
        logger.info("Shutting down Subtitle Sync Backend...")
        
        try:
            # Shutdown job processor
            logger.info("Shutting down job processor...")
            await job_processor.shutdown()
            
            # Final cleanup
            logger.info("Performing final cleanup...")
            file_manager.cleanup_temp_files()
            
            logger.info("Backend shutdown completed")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
    
    def _setup_directories(self):
        """Ensure all required directories exist"""
        directories = [
            self.config.settings.upload_dir,
            self.config.settings.processed_dir,
            os.path.dirname(self.config.get_database_path())
        ]
        
        for directory in directories:
            if directory:
                Path(directory).mkdir(parents=True, exist_ok=True)
                logger.info(f"Directory ready: {directory}")
    
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating shutdown...")
            self.shutdown_event.set()
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    async def run(self):
        """Run the application"""
        try:
            # Setup signal handlers
            self._setup_signal_handlers()
            
            # Startup
            await self.startup()
            
            # Start uvicorn server with increased limits for large file uploads
            config = uvicorn.Config(
                "main:app",
                host=self.config.settings.host,
                port=self.config.settings.port,
                reload=self.config.settings.reload,
                log_level=self.config.settings.log_level.lower(),
                access_log=True,
                limit_max_requests=1000,
                limit_concurrency=1000,
                timeout_keep_alive=120,  # Increased for large uploads
                timeout_graceful_shutdown=60,
                # Critical settings for large file uploads (2GB+)
                http="h11",  # Use h11 for better large file handling
                ws_max_size=2 * 1024 * 1024 * 1024,  # 2GB WebSocket limit
                h11_max_incomplete_event_size=2 * 1024 * 1024 * 1024,  # 2GB HTTP limit
                # Add additional timeout and size limits
                server_header=False,
                date_header=True,
                # Request body size limit (2GB)
                loop="asyncio",
                # Increase timeout for slow clients uploading large files
                client_timeout=300,  # 5 minutes for large uploads
            )
            
            server = uvicorn.Server(config)
            
            # Run server until shutdown signal
            await server.serve()
            
        except Exception as e:
            logger.error(f"Application error: {e}")
            raise
        finally:
            await self.shutdown()

# PUBLIC_INTERFACE
def run_development_server():
    """
    Run development server with hot reload and large file upload support.
    The server will default to port 3001 for compatibility with the React frontend.
    """
    config = get_config()
    # Always use port 3001 unless explicitly overridden by environment/CLI
    port = int(os.getenv("PORT", 3001))
    uvicorn.run(
        "main:app",
        host=config.settings.host,
        port=port,
        reload=True,
        log_level="debug",
        access_log=True,
        limit_max_requests=1000,
        limit_concurrency=1000,
        timeout_keep_alive=120,  # Increased for large uploads
        timeout_graceful_shutdown=60,
        # Critical settings for large file uploads during development
        http="h11",  # Use h11 for better stability with large files
        ws_max_size=2 * 1024 * 1024 * 1024,  # 2GB WebSocket limit
        h11_max_incomplete_event_size=2 * 1024 * 1024 * 1024,  # 2GB HTTP limit
        # Add client timeout for large uploads
        server_header=False,
        date_header=True,
        loop="asyncio",
    )

# PUBLIC_INTERFACE
def run_production_server():
    """
    Run production server
    """
    app = BackendApplication()
    asyncio.run(app.run())

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Subtitle Sync Backend Server")
    parser.add_argument(
        "--mode", 
        choices=["development", "production"], 
        default="development",
        help="Server mode"
    )
    parser.add_argument(
        "--host", 
        default="0.0.0.0",
        help="Host to bind to"
    )
    parser.add_argument(
        "--port", 
        type=int, 
        # Default to port 3001 for compatibility
        default=int(os.getenv("PORT", 3001)),
        help="Port to bind to"
    )
    
    args = parser.parse_args()
    
    # Update config with command line arguments
    config = get_config()
    config.update_setting("host", args.host)
    config.update_setting("port", args.port)
    
    if args.mode == "development":
        logger.info("Starting in development mode...")
        run_development_server()
    else:
        logger.info("Starting in production mode...")
        run_production_server()
