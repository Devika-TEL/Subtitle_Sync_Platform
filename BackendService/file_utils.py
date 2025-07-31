"""
File handling utilities for the Subtitle Sync Platform
"""

import os
import shutil
import tempfile
import hashlib
import mimetypes
from typing import Optional, Dict, List, Tuple, BinaryIO
from pathlib import Path
import magic
import logging
from datetime import datetime

from config import get_config

logger = logging.getLogger(__name__)
config = get_config()

class FileValidator:
    """File validation utilities"""
    
    @staticmethod
    # PUBLIC_INTERFACE
    def validate_file_size(file_size: int) -> bool:
        """
        Validate file size against configured limits
        
        Args:
            file_size: Size of the file in bytes
            
        Returns:
            True if file size is acceptable, False otherwise
        """
        max_size = config.get_max_file_size_bytes()
        return file_size <= max_size
    
    @staticmethod
    # PUBLIC_INTERFACE
    def validate_file_extension(filename: str, file_type: str) -> bool:
        """
        Validate file extension against allowed types
        
        Args:
            filename: Name of the file
            file_type: Type of file ('video' or 'subtitle')
            
        Returns:
            True if extension is allowed, False otherwise
        """
        if file_type == 'video':
            return config.is_allowed_video_file(filename)
        elif file_type == 'subtitle':
            return config.is_allowed_subtitle_file(filename)
        else:
            return False
    
    @staticmethod
    # PUBLIC_INTERFACE
    def validate_file_content(file_path: str, expected_type: str) -> Dict[str, any]:
        """
        Validate file content using magic numbers and content analysis
        
        Args:
            file_path: Path to the file to validate
            expected_type: Expected file type ('video' or 'subtitle')
            
        Returns:
            Dictionary with validation results
        """
        result = {
            "is_valid": False,
            "detected_type": None,
            "mime_type": None,
            "issues": []
        }
        
        try:
            # Get MIME type
            mime_type = magic.from_file(file_path, mime=True)
            result["mime_type"] = mime_type
            
            if expected_type == 'video':
                if mime_type.startswith('video/'):
                    result["is_valid"] = True
                    result["detected_type"] = "video"
                else:
                    result["issues"].append(f"Expected video file, got {mime_type}")
            
            elif expected_type == 'subtitle':
                # For subtitle files, be more flexible with MIME types since browsers vary
                # Many subtitle files (especially .srt) are detected as text/plain or application/octet-stream
                accepted_mime_patterns = [
                    'text/',
                    'application/x-subrip',
                    'application/x-sub',
                    'application/x-sami',
                    'application/octet-stream',  # Some browsers report .srt as this
                ]
                
                mime_type_acceptable = any(pattern in mime_type.lower() for pattern in accepted_mime_patterns)
                
                if mime_type_acceptable or mime_type == 'text/plain':
                    # Additional content validation for subtitles
                    content_valid = FileValidator._validate_subtitle_content(file_path)
                    if content_valid:
                        result["is_valid"] = True
                        result["detected_type"] = "subtitle"
                    else:
                        result["issues"].append("File content doesn't appear to be a valid subtitle format")
                else:
                    # Still validate content even if MIME type is unexpected - file extension might be correct
                    content_valid = FileValidator._validate_subtitle_content(file_path)
                    if content_valid:
                        result["is_valid"] = True
                        result["detected_type"] = "subtitle"
                        result["issues"].append(f"Unusual MIME type for subtitle file: {mime_type}, but content appears valid")
                    else:
                        result["issues"].append(f"Expected text-based file for subtitles, got {mime_type}")
        
        except Exception as e:
            logger.error(f"File validation error: {e}")
            result["issues"].append(f"Validation error: {str(e)}")
        
        return result
    
    @staticmethod
    def _validate_subtitle_content(file_path: str) -> bool:
        """Validate subtitle file content"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read(2000)  # Read first 2000 characters
            
            # Check for common subtitle patterns
            subtitle_patterns = [
                r'\d+\s*\n\d{2}:\d{2}:\d{2},\d{3}',  # SRT pattern
                r'\d+\s*\r?\n\d{2}:\d{2}:\d{2},\d{3}',  # SRT pattern with carriage return
                r'WEBVTT',  # WebVTT pattern
                r'\d{2}:\d{2}:\d{2}\.\d{3}',  # WebVTT time pattern
                r'\[Script Info\]',  # ASS/SSA pattern
                r'\d{2}:\d{2}:\d{2}:\d{2}',  # SCC pattern
                r'\{\d+\}\{\d+\}',  # SUB pattern (MicroDVD)
                r'<SAMI>',  # SAMI pattern
                r'<SYNC Start=\d+>',  # SAMI sync pattern
            ]
            
            import re
            for pattern in subtitle_patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    return True
            
            # If no patterns match but file extension suggests subtitle format, allow it
            file_extension = file_path.lower()
            if any(file_extension.endswith(ext) for ext in ['.srt', '.vtt', '.ass', '.ssa', '.scc', '.sub', '.smi', '.sami']):
                # Additional basic checks for subtitle-like content
                if '-->' in content or any(char.isdigit() for char in content[:100]):
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Subtitle content validation error: {e}")
            return False

class FileManager:
    """File management operations"""
    
    def __init__(self):
        self.upload_dir = config.settings.upload_dir
        self.processed_dir = config.settings.processed_dir
        
        # Ensure directories exist
        os.makedirs(self.upload_dir, exist_ok=True)
        os.makedirs(self.processed_dir, exist_ok=True)
    
    # PUBLIC_INTERFACE
    def save_uploaded_file(self, file_obj: BinaryIO, filename: str, 
                          file_type: str) -> Dict[str, any]:
        """
        Save uploaded file with validation
        
        Args:
            file_obj: File object to save
            filename: Original filename
            file_type: Type of file ('video' or 'subtitle')
            
        Returns:
            Dictionary with save results
        """
        result = {
            "success": False,
            "file_path": None,
            "file_size": 0,
            "checksum": None,
            "issues": []
        }
        
        try:
            # Generate safe filename
            safe_filename = self._generate_safe_filename(filename)
            file_path = os.path.join(self.upload_dir, safe_filename)
            
            # Save file and calculate checksum
            checksum = hashlib.md5()
            file_size = 0
            
            with open(file_path, 'wb') as f:
                while chunk := file_obj.read(8192):
                    f.write(chunk)
                    checksum.update(chunk)
                    file_size += len(chunk)
            
            result["file_path"] = file_path
            result["file_size"] = file_size
            result["checksum"] = checksum.hexdigest()
            
            # Validate file size
            if not FileValidator.validate_file_size(file_size):
                result["issues"].append(f"File size ({file_size} bytes) exceeds limit")
                os.remove(file_path)
                return result
            
            # Validate file extension
            if not FileValidator.validate_file_extension(safe_filename, file_type):
                result["issues"].append(f"File extension not allowed for {file_type} files")
                os.remove(file_path)
                return result
            
            # Validate file content
            validation_result = FileValidator.validate_file_content(file_path, file_type)
            if not validation_result["is_valid"]:
                result["issues"].extend(validation_result["issues"])
                os.remove(file_path)
                return result
            
            result["success"] = True
            logger.info(f"Successfully saved file: {safe_filename} ({file_size} bytes)")
            
        except Exception as e:
            logger.error(f"Error saving file {filename}: {e}")
            result["issues"].append(f"Save error: {str(e)}")
            
            # Clean up on error
            if result["file_path"] and os.path.exists(result["file_path"]):
                try:
                    os.remove(result["file_path"])
                except Exception:
                    pass
        
        return result
    
    # PUBLIC_INTERFACE
    def move_to_processed(self, source_path: str, new_filename: Optional[str] = None) -> str:
        """
        Move file from upload directory to processed directory
        
        Args:
            source_path: Path to source file
            new_filename: Optional new filename
            
        Returns:
            Path to moved file
        """
        if not os.path.exists(source_path):
            raise FileNotFoundError(f"Source file not found: {source_path}")
        
        if new_filename:
            filename = self._generate_safe_filename(new_filename)
        else:
            filename = os.path.basename(source_path)
        
        dest_path = os.path.join(self.processed_dir, filename)
        
        # Handle filename conflicts
        counter = 1
        base_name, ext = os.path.splitext(filename)
        while os.path.exists(dest_path):
            filename = f"{base_name}_{counter}{ext}"
            dest_path = os.path.join(self.processed_dir, filename)
            counter += 1
        
        shutil.move(source_path, dest_path)
        logger.info(f"Moved file to processed: {dest_path}")
        
        return dest_path
    
    # PUBLIC_INTERFACE
    def create_temp_copy(self, source_path: str) -> str:
        """
        Create temporary copy of file for processing
        
        Args:
            source_path: Path to source file
            
        Returns:
            Path to temporary copy
        """
        if not os.path.exists(source_path):
            raise FileNotFoundError(f"Source file not found: {source_path}")
        
        # Create temporary file with same extension
        _, ext = os.path.splitext(source_path)
        temp_fd, temp_path = tempfile.mkstemp(suffix=ext)
        
        try:
            with os.fdopen(temp_fd, 'wb') as temp_file:
                with open(source_path, 'rb') as source_file:
                    shutil.copyfileobj(source_file, temp_file)
        except Exception:
            # Clean up on error
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise
        
        return temp_path
    
    # PUBLIC_INTERFACE
    def cleanup_temp_files(self, max_age_hours: int = 24):
        """
        Clean up temporary files older than specified age
        
        Args:
            max_age_hours: Maximum age of temp files in hours
        """
        temp_dir = tempfile.gettempdir()
        current_time = datetime.now().timestamp()
        max_age_seconds = max_age_hours * 3600
        
        cleaned_count = 0
        
        try:
            for filename in os.listdir(temp_dir):
                if filename.startswith('tmp') and any(
                    filename.endswith(ext) 
                    for ext in config.settings.allowed_video_extensions + config.settings.allowed_subtitle_extensions
                ):
                    file_path = os.path.join(temp_dir, filename)
                    try:
                        file_age = current_time - os.path.getmtime(file_path)
                        if file_age > max_age_seconds:
                            os.remove(file_path)
                            cleaned_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to clean temp file {file_path}: {e}")
        
        except Exception as e:
            logger.error(f"Error during temp file cleanup: {e}")
        
        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} temporary files")
    
    # PUBLIC_INTERFACE
    def get_file_info(self, file_path: str) -> Dict[str, any]:
        """
        Get comprehensive file information
        
        Args:
            file_path: Path to file
            
        Returns:
            Dictionary with file information
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        stat = os.stat(file_path)
        
        info = {
            "filename": os.path.basename(file_path),
            "size_bytes": stat.st_size,
            "size_mb": round(stat.st_size / (1024 * 1024), 2),
            "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "extension": os.path.splitext(file_path)[1].lower(),
        }
        
        # Add MIME type if available
        try:
            info["mime_type"] = magic.from_file(file_path, mime=True)
        except Exception:
            info["mime_type"] = mimetypes.guess_type(file_path)[0]
        
        # Add checksum for integrity verification
        try:
            info["md5_checksum"] = self._calculate_file_checksum(file_path)
        except Exception as e:
            logger.warning(f"Failed to calculate checksum for {file_path}: {e}")
            info["md5_checksum"] = None
        
        return info
    
    # PUBLIC_INTERFACE
    def list_files(self, directory: str, pattern: Optional[str] = None) -> List[Dict[str, any]]:
        """
        List files in directory with optional pattern matching
        
        Args:
            directory: Directory to list
            pattern: Optional glob pattern for filtering
            
        Returns:
            List of file information dictionaries
        """
        if not os.path.exists(directory):
            return []
        
        files = []
        
        try:
            if pattern:
                from glob import glob
                file_paths = glob(os.path.join(directory, pattern))
            else:
                file_paths = [
                    os.path.join(directory, f) 
                    for f in os.listdir(directory) 
                    if os.path.isfile(os.path.join(directory, f))
                ]
            
            for file_path in file_paths:
                try:
                    info = self.get_file_info(file_path)
                    info["full_path"] = file_path
                    files.append(info)
                except Exception as e:
                    logger.warning(f"Failed to get info for {file_path}: {e}")
        
        except Exception as e:
            logger.error(f"Error listing files in {directory}: {e}")
        
        return sorted(files, key=lambda x: x["modified"], reverse=True)
    
    def _generate_safe_filename(self, filename: str) -> str:
        """Generate safe filename by removing/replacing problematic characters"""
        # Remove or replace problematic characters
        safe_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-_"
        safe_filename = "".join(c if c in safe_chars else "_" for c in filename)
        
        # Ensure filename is not empty and doesn't start with dot
        if not safe_filename or safe_filename.startswith('.'):
            safe_filename = f"file_{datetime.now().strftime('%Y%m%d_%H%M%S')}" + safe_filename
        
        # Add timestamp to avoid conflicts
        name, ext = os.path.splitext(safe_filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        return f"{name}_{timestamp}{ext}"
    
    def _calculate_file_checksum(self, file_path: str) -> str:
        """Calculate MD5 checksum of file"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

# Global file manager instance
file_manager = FileManager()
