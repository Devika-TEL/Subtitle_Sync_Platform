"""
File management utilities for the Subtitle Sync Platform
"""

import os
import shutil
import logging
import tempfile
from pathlib import Path
from typing import List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class FileManager:
    """Handles file operations and cleanup"""
    
    def __init__(self):
        self.upload_dir = "uploads"
        self.processed_dir = "processed"
        self.temp_cleanup_age = timedelta(hours=24)  # Clean up temp files older than 24 hours
    
    def cleanup_temp_files(self):
        """Clean up old temporary files"""
        try:
            cutoff_time = datetime.now() - self.temp_cleanup_age
            
            for directory in [self.upload_dir, self.processed_dir]:
                if os.path.exists(directory):
                    for filename in os.listdir(directory):
                        if filename.startswith('temp_'):
                            file_path = os.path.join(directory, filename)
                            try:
                                file_time = datetime.fromtimestamp(os.path.getctime(file_path))
                                if file_time < cutoff_time:
                                    os.remove(file_path)
                                    logger.info(f"Cleaned up old temp file: {filename}")
                            except Exception as e:
                                logger.warning(f"Failed to clean up {filename}: {e}")
            
        except Exception as e:
            logger.error(f"Temp file cleanup failed: {e}")
    
    def get_file_info(self, file_path: str) -> Optional[dict]:
        """Get file information"""
        try:
            if os.path.exists(file_path):
                stat = os.stat(file_path)
                return {
                    "path": file_path,
                    "size": stat.st_size,
                    "created": datetime.fromtimestamp(stat.st_ctime),
                    "modified": datetime.fromtimestamp(stat.st_mtime)
                }
        except Exception as e:
            logger.error(f"Failed to get file info for {file_path}: {e}")
        
        return None
    
    def safe_delete(self, file_path: str) -> bool:
        """Safely delete a file"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Deleted file: {file_path}")
                return True
        except Exception as e:
            logger.error(f"Failed to delete {file_path}: {e}")
        
        return False
    
    def create_temp_copy(self, source_path: str) -> Optional[str]:
        """Create a temporary copy of a file"""
        try:
            temp_fd, temp_path = tempfile.mkstemp()
            os.close(temp_fd)
            
            shutil.copy2(source_path, temp_path)
            logger.info(f"Created temp copy: {source_path} -> {temp_path}")
            return temp_path
            
        except Exception as e:
            logger.error(f"Failed to create temp copy of {source_path}: {e}")
            return None
    
    def get_processed_files(self) -> List[dict]:
        """Get list of processed files with metadata"""
        files = []
        
        try:
            if os.path.exists(self.processed_dir):
                for filename in os.listdir(self.processed_dir):
                    file_path = os.path.join(self.processed_dir, filename)
                    if os.path.isfile(file_path):
                        info = self.get_file_info(file_path)
                        if info:
                            files.append({
                                "filename": filename,
                                "size": info["size"],
                                "created": info["created"],
                                "modified": info["modified"]
                            })
        
        except Exception as e:
            logger.error(f"Failed to get processed files: {e}")
        
        return files

# Global file manager instance
file_manager = FileManager()
