"""
Database utilities and connection management for the Subtitle Sync Platform
"""

import sqlite3
import os
import logging
from contextlib import contextmanager
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

# Database configuration
DATABASE_PATH = os.path.join(os.path.dirname(__file__), "..", "Database", "subtitle_sync_platform.db")

class DatabaseManager:
    """Database manager for handling connections and operations"""
    
    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path
        self.ensure_database_exists()
    
    def ensure_database_exists(self):
        """Ensure database file and directory exist"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        if not os.path.exists(self.db_path):
            self.initialize_database()
    
    def initialize_database(self):
        """Initialize database with schema"""
        try:
            # Try to import and use the models
            import sys
            parent_dir = os.path.join(os.path.dirname(__file__), "..")
            if parent_dir not in sys.path:
                sys.path.insert(0, parent_dir)
            
            from Database.models import create_tables
            create_tables()
            logger.info("Database initialized using models.py")
        except Exception as e:
            logger.warning(f"Could not initialize using models.py: {e}")
            # Fallback: create tables directly
            self._create_tables_directly()
    
    def _create_tables_directly(self):
        """Create tables directly using SQL"""
        schema_sql = """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            email TEXT,
            role TEXT NOT NULL DEFAULT 'user'
        );

        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            filename TEXT NOT NULL,
            upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            language TEXT,
            original BOOLEAN DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS subtitles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id INTEGER REFERENCES videos(id) ON DELETE CASCADE,
            user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            filename TEXT NOT NULL,
            language TEXT,
            upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            processed BOOLEAN DEFAULT 0,
            job_id INTEGER REFERENCES jobs(id)
        );

        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            video_id INTEGER REFERENCES videos(id) ON DELETE CASCADE,
            subtitle_id INTEGER REFERENCES subtitles(id) ON DELETE CASCADE,
            job_type TEXT NOT NULL,
            status TEXT NOT NULL,
            result_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP
        );
        """
        
        conn = self.get_connection()
        try:
            conn.executescript(schema_sql)
            conn.commit()
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Failed to create tables: {e}")
            raise
        finally:
            conn.close()
    
    @contextmanager
    def get_connection(self):
        """Get database connection with proper error handling"""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("PRAGMA foreign_keys = ON")
            conn.row_factory = sqlite3.Row
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            if conn:
                conn.close()
    
    # PUBLIC_INTERFACE
    def execute_query(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """
        Execute a SELECT query and return results as list of dictionaries
        
        Args:
            query: SQL query string
            params: Query parameters
            
        Returns:
            List of dictionaries representing rows
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    
    # PUBLIC_INTERFACE
    def execute_insert(self, query: str, params: tuple = ()) -> int:
        """
        Execute an INSERT query and return the last row ID
        
        Args:
            query: SQL INSERT query string
            params: Query parameters
            
        Returns:
            Last inserted row ID
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            row_id = cursor.lastrowid
            conn.commit()
            return row_id
    
    # PUBLIC_INTERFACE
    def execute_update(self, query: str, params: tuple = ()) -> int:
        """
        Execute an UPDATE or DELETE query and return number of affected rows
        
        Args:
            query: SQL UPDATE/DELETE query string
            params: Query parameters
            
        Returns:
            Number of affected rows
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            affected_rows = cursor.rowcount
            conn.commit()
            return affected_rows

# Global database manager instance
db_manager = DatabaseManager()

# PUBLIC_INTERFACE
def get_db_connection():
    """
    Get database connection for use in FastAPI dependencies
    
    Returns:
        SQLite connection with row factory set
    """
    conn = sqlite3.connect(DATABASE_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn

# PUBLIC_INTERFACE
def init_database():
    """
    Initialize database - creates tables if they don't exist
    """
    db_manager.initialize_database()
