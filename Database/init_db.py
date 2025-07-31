"""
Initializer/CLI for SQLite database using the models defined for Subtitle Sync Platform.
Run this script to create (or upgrade) the database schema in the SQLite file.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base

DB_FILE = os.getenv("DB_FILE", "subtitle_sync_platform.db")
DATABASE_URL = f"sqlite:///{DB_FILE}"

# PUBLIC_INTERFACE
def get_engine():
    """Return SQLAlchemy Engine instance."""
    return create_engine(DATABASE_URL, echo=True, future=True)

# PUBLIC_INTERFACE
def create_db():
    """Create all tables per models.py if not present."""
    engine = get_engine()
    Base.metadata.create_all(engine)
    print("Database schema created or verified.")

# PUBLIC_INTERFACE
def drop_db():
    """Drop all tables (DANGER: destructive)."""
    engine = get_engine()
    Base.metadata.drop_all(engine)
    print("Database schema dropped.")

if __name__ == "__main__":
    print("[DB INIT] Creating database/tables...")
    create_db()
