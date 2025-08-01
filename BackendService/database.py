import uuid
import sqlalchemy as sa
from sqlalchemy import create_engine, Column, String, Boolean, Integer, DateTime, Text, ForeignKey
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from datetime import datetime
from pydantic import BaseModel

from config import settings

Base = declarative_base()

# --- SQLAlchemy Schema Models ---
class UserModel(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    role = Column(String, default="user")  # can be "user" or "admin"
    disabled = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class FileModel(Base):
    __tablename__ = "files"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    path = Column(String, unique=True, index=True)
    user_id = Column(String, ForeignKey("users.id"))
    type = Column(String) # video, subtitle, etc.
    created_at = Column(DateTime, default=datetime.utcnow)
    user = relationship('UserModel')

class JobModel(Base):
    __tablename__ = "jobs"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"))
    file_id = Column(String, ForeignKey("files.id"))
    type = Column(String) # upload, sync, generate_subtitle, compliance, etc.
    status = Column(String, default="pending")
    result = Column(Text)
    logs = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    user = relationship('UserModel')
    file = relationship('FileModel')

# --- Pydantic Models for API/Logic Layers ---
class JobCreate(BaseModel):
    user_id: str
    file_id: str
    type: str

# --- Database Session ---
engine = create_engine(settings.DB_URL, echo=False, connect_args={"check_same_thread": False} if 'sqlite' in settings.DB_URL else {})
SessionLocal = sessionmaker(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Data Access Functions ---
def create_user(db, username, hashed_password):
    user = UserModel(username=username, hashed_password=hashed_password, role="user")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def get_user_by_username(db, username):
    return db.query(UserModel).filter(UserModel.username == username).first()

def create_file_entry(db, path, user_id, type):
    file = FileModel(path=path, user_id=user_id, type=type)
    db.add(file)
    db.commit()
    db.refresh(file)
    return file

def get_file_by_id(db, file_id):
    return db.query(FileModel).filter(FileModel.id == file_id).first()

def create_job(db, job: JobCreate):
    db_job = JobModel(user_id=job.user_id, file_id=job.file_id, type=job.type)
    db.add(db_job)
    db.commit()
    db.refresh(db_job)
    return db_job

def get_job(db, job_id):
    return db.query(JobModel).filter(JobModel.id == job_id).first()

def update_job_status(db, job_id, status, result=None, logs=None):
    job = get_job(db, job_id)
    if job:
        job.status = status
        job.updated_at = datetime.utcnow()
        if result is not None:
            job.result = result
        if logs:
            job.logs = (job.logs or "") + f"\n{datetime.utcnow()}: {logs}"
        db.commit()
        db.refresh(job)
    return job

def list_jobs(db):
    return db.query(JobModel).order_by(JobModel.created_at.desc()).all()

def list_users(db):
    return db.query(UserModel).order_by(UserModel.created_at.desc()).all()

def list_files(db):
    return db.query(FileModel).order_by(FileModel.created_at.desc()).all()
