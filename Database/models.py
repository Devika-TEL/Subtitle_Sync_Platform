import sqlite3
import os

# PUBLIC_INTERFACE
def create_tables():
    """
    Create database tables for videos, subtitles, jobs, and users.

    Tables:
        users - Registered users and roles
        videos - Video files and metadata
        subtitles - Subtitle files, linked to videos
        jobs - Processing jobs and statuses
    """
    # Get the database path relative to this file's location
    db_path = os.path.join(os.path.dirname(__file__), 'subtitle_sync_platform.db')
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Users table: authentication and role management
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        email TEXT,
        role TEXT NOT NULL DEFAULT 'user'
    )
    """)

    # Videos table: stores uploaded video metadata
    c.execute("""
    CREATE TABLE IF NOT EXISTS videos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
        filename TEXT NOT NULL,
        upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        language TEXT,
        original BOOLEAN DEFAULT 1
    )
    """)

    # Subtitles table: stores uploaded/processed subtitles
    c.execute("""
    CREATE TABLE IF NOT EXISTS subtitles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        video_id INTEGER REFERENCES videos(id) ON DELETE CASCADE,
        user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
        filename TEXT NOT NULL,
        language TEXT,
        upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        processed BOOLEAN DEFAULT 0,
        job_id INTEGER REFERENCES jobs(id)
    )
    """)

    # Jobs table: tracks processing (correction, generation, translation)
    c.execute("""
    CREATE TABLE IF NOT EXISTS jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
        video_id INTEGER REFERENCES videos(id) ON DELETE CASCADE,
        subtitle_id INTEGER REFERENCES subtitles(id) ON DELETE CASCADE,
        job_type TEXT NOT NULL, -- correction, generation, translation
        status TEXT NOT NULL, -- pending, running, complete, failed
        result_url TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        completed_at TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()

if __name__ == "__main__":
    create_tables()
