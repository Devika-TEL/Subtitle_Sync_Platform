"""
Authentication and authorization utilities for the Subtitle Sync Platform
"""

import hashlib
import secrets
import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import HTTPException, status
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

# Configuration - in production these would come from environment variables
SECRET_KEY = "your-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

class TokenData(BaseModel):
    """Token data model"""
    username: Optional[str] = None
    user_id: Optional[int] = None
    role: Optional[str] = None

class UserAuth:
    """User authentication and authorization utilities"""
    
    @staticmethod
    # PUBLIC_INTERFACE
    def hash_password(password: str) -> str:
        """
        Hash a password using SHA-256 with salt
        
        Args:
            password: Plain text password
            
        Returns:
            Hashed password string
        """
        # Generate a random salt
        salt = secrets.token_hex(16)
        
        # Hash password with salt
        password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
        
        # Return salt + hash for storage
        return f"{salt}:{password_hash}"
    
    @staticmethod
    # PUBLIC_INTERFACE
    def verify_password(password: str, hashed_password: str) -> bool:
        """
        Verify a password against its hash
        
        Args:
            password: Plain text password to verify
            hashed_password: Stored hash (salt:hash format)
            
        Returns:
            True if password matches, False otherwise
        """
        try:
            salt, stored_hash = hashed_password.split(':', 1)
            password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
            return password_hash == stored_hash
        except ValueError:
            # Handle legacy or malformed hashes
            logger.warning("Invalid hash format encountered")
            return False
    
    @staticmethod
    # PUBLIC_INTERFACE
    def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """
        Create a JWT access token
        
        Args:
            data: Data to encode in token
            expires_delta: Token expiration time
            
        Returns:
            JWT token string
        """
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire})
        
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    
    @staticmethod
    # PUBLIC_INTERFACE  
    def verify_token(token: str) -> TokenData:
        """
        Verify and decode a JWT token
        
        Args:
            token: JWT token string
            
        Returns:
            TokenData object with user information
            
        Raises:
            HTTPException: If token is invalid or expired
        """
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username: str = payload.get("sub")
            user_id: int = payload.get("user_id")
            role: str = payload.get("role", "user")
            
            if username is None or user_id is None:
                raise credentials_exception
                
            token_data = TokenData(username=username, user_id=user_id, role=role)
            return token_data
            
        except jwt.PyJWTError:
            raise credentials_exception
    
    @staticmethod
    # PUBLIC_INTERFACE
    def check_permission(user_role: str, required_role: str) -> bool:
        """
        Check if user has required permission level
        
        Args:
            user_role: User's current role
            required_role: Required role for action
            
        Returns:
            True if user has permission, False otherwise
        """
        role_hierarchy = {
            "user": 1,
            "admin": 2,
            "superuser": 3
        }
        
        user_level = role_hierarchy.get(user_role, 0)
        required_level = role_hierarchy.get(required_role, 999)
        
        return user_level >= required_level
    
    @staticmethod
    # PUBLIC_INTERFACE
    def generate_api_key() -> str:
        """
        Generate a secure API key for programmatic access
        
        Returns:
            Secure API key string
        """
        return secrets.token_urlsafe(32)
    
    @staticmethod
    # PUBLIC_INTERFACE
    def validate_password_strength(password: str) -> Dict[str, Any]:
        """
        Validate password strength and return feedback
        
        Args:
            password: Password to validate
            
        Returns:
            Dictionary with validation results and suggestions
        """
        issues = []
        score = 0
        
        # Length check
        if len(password) < 8:
            issues.append("Password must be at least 8 characters long")
        else:
            score += 1
        
        # Character variety checks
        if not any(c.islower() for c in password):
            issues.append("Password should contain lowercase letters")
        else:
            score += 1
            
        if not any(c.isupper() for c in password):
            issues.append("Password should contain uppercase letters")
        else:
            score += 1
            
        if not any(c.isdigit() for c in password):
            issues.append("Password should contain numbers")
        else:
            score += 1
            
        if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
            issues.append("Password should contain special characters")
        else:
            score += 1
        
        # Common password check (simplified)
        common_passwords = [
            "password", "123456", "password123", "admin", "letmein",
            "welcome", "monkey", "dragon", "qwerty", "abc123"
        ]
        
        if password.lower() in common_passwords:
            issues.append("Password is too common")
            score = max(0, score - 2)
        
        # Determine strength
        if score <= 2:
            strength = "weak"
        elif score <= 3:
            strength = "medium"
        else:
            strength = "strong"
        
        return {
            "is_valid": len(issues) == 0 and score >= 3,
            "strength": strength,
            "score": score,
            "issues": issues
        }

class SessionManager:
    """Manage user sessions and tokens"""
    
    def __init__(self):
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
    
    # PUBLIC_INTERFACE
    def create_session(self, user_id: int, username: str, role: str) -> Dict[str, str]:
        """
        Create a new user session
        
        Args:
            user_id: User ID
            username: Username
            role: User role
            
        Returns:
            Dictionary with access and refresh tokens
        """
        # Create access token
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = UserAuth.create_access_token(
            data={"sub": username, "user_id": user_id, "role": role},
            expires_delta=access_token_expires
        )
        
        # Create refresh token (longer expiry)
        refresh_token_expires = timedelta(days=7)
        refresh_token = UserAuth.create_access_token(
            data={"sub": username, "user_id": user_id, "role": role, "type": "refresh"},
            expires_delta=refresh_token_expires
        )
        
        # Store session
        session_id = secrets.token_urlsafe(32)
        self.active_sessions[session_id] = {
            "user_id": user_id,
            "username": username,
            "role": role,
            "created_at": datetime.utcnow(),
            "last_activity": datetime.utcnow(),
            "access_token": access_token,
            "refresh_token": refresh_token
        }
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "session_id": session_id
        }
    
    # PUBLIC_INTERFACE
    def refresh_token(self, refresh_token: str) -> Optional[Dict[str, str]]:
        """
        Refresh an access token using refresh token
        
        Args:
            refresh_token: Valid refresh token
            
        Returns:
            New token dictionary or None if invalid
        """
        try:
            # Verify refresh token
            token_data = UserAuth.verify_token(refresh_token)
            
            # Find session
            session = None
            session_id = None
            for sid, sess in self.active_sessions.items():
                if sess["refresh_token"] == refresh_token:
                    session = sess
                    session_id = sid
                    break
            
            if not session:
                return None
            
            # Create new access token
            access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
            new_access_token = UserAuth.create_access_token(
                data={
                    "sub": token_data.username,
                    "user_id": token_data.user_id,
                    "role": token_data.role
                },
                expires_delta=access_token_expires
            )
            
            # Update session
            session["access_token"] = new_access_token
            session["last_activity"] = datetime.utcnow()
            
            return {
                "access_token": new_access_token,
                "token_type": "bearer"
            }
            
        except Exception as e:
            logger.error(f"Token refresh failed: {e}")
            return None
    
    # PUBLIC_INTERFACE
    def revoke_session(self, session_id: str) -> bool:
        """
        Revoke a user session
        
        Args:
            session_id: Session ID to revoke
            
        Returns:
            True if session was revoked, False if not found
        """
        if session_id in self.active_sessions:
            del self.active_sessions[session_id]
            return True
        return False
    
    # PUBLIC_INTERFACE
    def cleanup_expired_sessions(self):
        """Remove expired sessions"""
        current_time = datetime.utcnow()
        expired_sessions = []
        
        for session_id, session in self.active_sessions.items():
            # Check if session is older than 7 days (refresh token expiry)
            if current_time - session["created_at"] > timedelta(days=7):
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            del self.active_sessions[session_id]
        
        logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")

# Global instances
user_auth = UserAuth()
session_manager = SessionManager()
