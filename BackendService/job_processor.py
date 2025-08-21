"""
Simple in-memory job queue to simulate asynchronous processing.

For production, replace with a persistent queue and worker system (e.g., Celery, RQ/Redis).
"""

from dataclasses import dataclass, field
from enum import Enum
from threading import Thread, Lock
from typing import Callable, Optional, List, Dict
import uuid
import traceback


class JobStatus(Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"


@dataclass
class JobRecord:
    job_id: str
    description: str
    meta: Dict
    status: JobStatus = JobStatus.QUEUED
    message: Optional[str] = None
    result_files: Optional[List[str]] = None


class JobQueue:
    def __init__(self, process_dir: str):
        self._jobs: Dict[str, JobRecord] = {}
        self._lock = Lock()
        self._process_dir = process_dir

    # PUBLIC_INTERFACE
    def enqueue(self, fn: Callable[[], List[str]], description: str = "", meta: Optional[Dict] = None) -> str:
        """Enqueue a function to be executed on a background thread. Returns a job id."""
        job_id = uuid.uuid4().hex
        rec = JobRecord(job_id=job_id, description=description, meta=meta or {})
        with self._lock:
            self._jobs[job_id] = rec

        def runner():
            with self._lock:
                self._jobs[job_id].status = JobStatus.RUNNING
            try:
                result_files = fn()
                with self._lock:
                    self._jobs[job_id].status = JobStatus.COMPLETED
                    self._jobs[job_id].result_files = result_files
                    self._jobs[job_id].message = "Done"
            except Exception as e:
                with self._lock:
                    self._jobs[job_id].status = JobStatus.FAILED
                    self._jobs[job_id].message = f"{e}\n{traceback.format_exc()}"

        Thread(target=runner, daemon=True).start()
        return job_id

    # PUBLIC_INTERFACE
    def get_status(self, job_id: str) -> Optional[JobRecord]:
        """Retrieve the status of a submitted job."""
        with self._lock:
            return self._jobs.get(job_id)
