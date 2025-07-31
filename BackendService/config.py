"""
Configuration management for the Subtitle Sync Platform backend
"""

import os
from typing import Optional, Dict, Any
from pydantic_settings import BaseSettings
from pydantic import validator
import logging

logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    """Application settings with environment variable support"""
    
    # Application settings
    app_name: str = "Subtitle Sync Backend API"
    app_version: str = "1.0.0"
    debug: bool = False
    
    # Server settings
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = False
    
    @validator('port', pre=True)
    def parse_port(cls, v):
        """Parse port from environment variable"""
        if isinstance(v, str):
            return int(v)
        return int(os.getenv("PORT", v))
    
    @validator('host', pre=True)
    def parse_host(cls, v):
        """Parse host from environment variable"""
        return os.getenv("HOST", v)
    
    # Database settings
    database_path: str = "../Database/subtitle_sync_platform.db"
    database_url: Optional[str] = None
    
    # Security settings
    secret_key: str = "change-this-in-production-please"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    
    # File storage settings
    upload_dir: str = "uploads"
    processed_dir: str = "processed"
    max_file_size_mb: int = 2048  # Increased to 2GB for large video files
    allowed_video_extensions: list = [".mp4", ".avi", ".mov", ".mkv", ".webm", ".m4v"]
    allowed_subtitle_extensions: list = [".srt", ".vtt", ".ass", ".ssa", ".scc", ".sub", ".smi", ".sami"]
    
    # Processing settings
    max_concurrent_jobs: int = 4
    job_timeout_minutes: int = 60
    cleanup_completed_jobs_hours: int = 24
    
    # AI/ML API settings (for future integration)
    openai_api_key: Optional[str] = None
    azure_speech_key: Optional[str] = None
    azure_speech_region: Optional[str] = None
    google_translate_api_key: Optional[str] = None
    
    # CORS settings
    cors_origins: list = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3002",
        # Current frontend URL
        "https://vscode-internal-29567-beta.beta01.cloud.kavia.ai:3001",
        "https://vscode-internal-29567-beta.beta01.cloud.kavia.ai:3000",
        "https://vscode-internal-29567-beta.beta01.cloud.kavia.ai",
        # Legacy URLs for backward compatibility
        "https://vscode-internal-29910-beta.beta01.cloud.kavia.ai:3000",
        "https://vscode-internal-29910-beta.beta01.cloud.kavia.ai:3001",
        "https://vscode-internal-29910-beta.beta01.cloud.kavia.ai:3002",
        "https://vscode-internal-29910-beta.beta01.cloud.kavia.ai",
        "https://vscode-internal-29822-beta.beta01.cloud.kavia.ai:3000",
        "https://vscode-internal-32497-beta.beta01.cloud.kavia.ai:3000",
        "https://vscode-internal-32497-beta.beta01.cloud.kavia.ai:3002",
        "https://*.beta01.cloud.kavia.ai:3002"
    ]
    
    # Logging settings
    log_level: str = "INFO"
    log_file: Optional[str] = None
    
    # Rate limiting
    rate_limit_per_minute: int = 60
    rate_limit_burst: int = 10
    
    @validator('debug')
    def set_debug_mode(cls, v, values):
        """Set debug mode based on environment"""
        if os.getenv('ENVIRONMENT') == 'development':
            return True
        return v
    
    @validator('cors_origins', pre=True)
    def parse_cors_origins(cls, v):
        """Parse CORS origins from environment variable"""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(',')]
        return v
    
    @validator('allowed_video_extensions', pre=True)
    def parse_video_extensions(cls, v):
        """Parse video extensions from environment variable"""
        if isinstance(v, str):
            return [ext.strip() for ext in v.split(',')]
        return v
    
    @validator('allowed_subtitle_extensions', pre=True)
    def parse_subtitle_extensions(cls, v):
        """Parse subtitle extensions from environment variable"""
        if isinstance(v, str):
            return [ext.strip() for ext in v.split(',')]
        return v
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        
        # Environment variable prefixes
        env_prefix = ""
        
        # Field aliases for environment variables
        fields = {
            "database_path": {"env": "DATABASE_PATH"},
            "secret_key": {"env": "SECRET_KEY"},
            "openai_api_key": {"env": "OPENAI_API_KEY"},
            "azure_speech_key": {"env": "AZURE_SPEECH_KEY"},
            "azure_speech_region": {"env": "AZURE_SPEECH_REGION"},
            "google_translate_api_key": {"env": "GOOGLE_TRANSLATE_API_KEY"},
            "cors_origins": {"env": "CORS_ORIGINS"},
            "max_file_size_mb": {"env": "MAX_FILE_SIZE_MB"},
        }

class ConfigManager:
    """Configuration manager with validation and defaults"""
    
    def __init__(self):
        self.settings = Settings()
        self._validate_configuration()
        self._setup_directories()
        self._setup_logging()
    
    def _validate_configuration(self):
        """Validate configuration settings"""
        # Check required directories
        required_dirs = [
            self.settings.upload_dir,
            self.settings.processed_dir
        ]
        
        for directory in required_dirs:
            if not os.path.exists(directory):
                try:
                    os.makedirs(directory, exist_ok=True)
                    logger.info(f"Created directory: {directory}")
                except Exception as e:
                    logger.error(f"Failed to create directory {directory}: {e}")
        
        # Validate file size limits
        if self.settings.max_file_size_mb <= 0:
            logger.warning("Invalid max file size, using default 500MB")
            self.settings.max_file_size_mb = 500
        
        # Validate token expiry times
        if self.settings.access_token_expire_minutes <= 0:
            logger.warning("Invalid access token expiry, using default 30 minutes")
            self.settings.access_token_expire_minutes = 30
    
    def _setup_directories(self):
        """Setup required directories"""
        directories = [
            self.settings.upload_dir,
            self.settings.processed_dir,
            os.path.dirname(self.get_database_path())
        ]
        
        for directory in directories:
            if directory and not os.path.exists(directory):
                try:
                    os.makedirs(directory, exist_ok=True)
                except Exception as e:
                    logger.error(f"Failed to create directory {directory}: {e}")
    
    def _setup_logging(self):
        """Setup logging configuration"""
        log_level = getattr(logging, self.settings.log_level.upper(), logging.INFO)
        
        # Configure root logger
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
            ]
        )
        
        # Add file handler if specified
        if self.settings.log_file:
            try:
                file_handler = logging.FileHandler(self.settings.log_file)
                file_handler.setFormatter(
                    logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
                )
                logging.getLogger().addHandler(file_handler)
            except Exception as e:
                logger.error(f"Failed to setup file logging: {e}")
    
    # PUBLIC_INTERFACE
    def get_database_path(self) -> str:
        """
        Get the full database path
        
        Returns:
            Absolute path to the database file
        """
        if self.settings.database_url:
            return self.settings.database_url
        
        if os.path.isabs(self.settings.database_path):
            return self.settings.database_path
        
        # Relative path - make it relative to the backend service directory
        return os.path.join(
            os.path.dirname(__file__),
            self.settings.database_path
        )
    
    # PUBLIC_INTERFACE
    def get_upload_path(self, filename: str) -> str:
        """
        Get full path for uploaded file
        
        Args:
            filename: Name of the uploaded file
            
        Returns:
            Full path to the upload location
        """
        return os.path.join(self.settings.upload_dir, filename)
    
    # PUBLIC_INTERFACE
    def get_processed_path(self, filename: str) -> str:
        """
        Get full path for processed file
        
        Args:
            filename: Name of the processed file
            
        Returns:
            Full path to the processed file location
        """
        return os.path.join(self.settings.processed_dir, filename)
    
    # PUBLIC_INTERFACE
    def is_allowed_video_file(self, filename: str) -> bool:
        """
        Check if video file extension is allowed
        
        Args:
            filename: Name of the video file
            
        Returns:
            True if extension is allowed, False otherwise
        """
        _, ext = os.path.splitext(filename.lower())
        return ext in self.settings.allowed_video_extensions
    
    # PUBLIC_INTERFACE
    def is_allowed_subtitle_file(self, filename: str) -> bool:
        """
        Check if subtitle file extension is allowed
        
        Args:
            filename: Name of the subtitle file
            
        Returns:
            True if extension is allowed, False otherwise
        """
        _, ext = os.path.splitext(filename.lower())
        return ext in self.settings.allowed_subtitle_extensions
    
    # PUBLIC_INTERFACE
    def get_max_file_size_bytes(self) -> int:
        """
        Get maximum file size in bytes
        
        Returns:
            Maximum file size in bytes
        """
        return self.settings.max_file_size_mb * 1024 * 1024
    
    # PUBLIC_INTERFACE
    def get_cors_settings(self) -> Dict[str, Any]:
        """
        Get CORS configuration
        
        Returns:
            Dictionary with CORS settings
        """
        return {
            "allow_origins": self.settings.cors_origins,
            "allow_credentials": True,
            "allow_methods": ["*"],
            "allow_headers": ["*"],
        }
    
    # PUBLIC_INTERFACE
    def get_security_settings(self) -> Dict[str, Any]:
        """
        Get security configuration
        
        Returns:
            Dictionary with security settings
        """
        return {
            "secret_key": self.settings.secret_key,
            "algorithm": self.settings.algorithm,
            "access_token_expire_minutes": self.settings.access_token_expire_minutes,
            "refresh_token_expire_days": self.settings.refresh_token_expire_days,
        }
    
    # PUBLIC_INTERFACE
    def has_ai_integration(self) -> Dict[str, bool]:
        """
        Check which AI services are configured
        
        Returns:
            Dictionary indicating which AI services are available
        """
        return {
            "openai": bool(self.settings.openai_api_key),
            "azure_speech": bool(self.settings.azure_speech_key and self.settings.azure_speech_region),
            "google_translate": bool(self.settings.google_translate_api_key),
        }
    
    # PUBLIC_INTERFACE
    def update_setting(self, key: str, value: Any) -> bool:
        """
        Update a configuration setting at runtime
        
        Args:
            key: Setting key to update
            value: New value for the setting
            
        Returns:
            True if update was successful, False otherwise
        """
        try:
            if hasattr(self.settings, key):
                setattr(self.settings, key, value)
                logger.info(f"Updated setting {key} = {value}")
                return True
            else:
                logger.warning(f"Unknown setting key: {key}")
                return False
        except Exception as e:
            logger.error(f"Failed to update setting {key}: {e}")
            return False
    
    # PUBLIC_INTERFACE
    def get_all_settings(self) -> Dict[str, Any]:
        """
        Get all configuration settings (excluding sensitive data)
        
        Returns:
            Dictionary with all settings
        """
        settings_dict = self.settings.dict()
        
        # Remove sensitive information
        sensitive_keys = [
            "secret_key", "openai_api_key", "azure_speech_key", 
            "google_translate_api_key"
        ]
        
        for key in sensitive_keys:
            if key in settings_dict and settings_dict[key]:
                settings_dict[key] = "***configured***"
        
        return settings_dict

# Global configuration manager
config = ConfigManager()

# PUBLIC_INTERFACE
def get_settings() -> Settings:
    """
    Get application settings
    
    Returns:
        Settings object with all configuration
    """
    return config.settings

# PUBLIC_INTERFACE
def get_config() -> ConfigManager:
    """
    Get configuration manager instance
    
    Returns:
        ConfigManager instance
    """
    return config
