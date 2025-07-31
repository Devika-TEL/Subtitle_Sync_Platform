"""
Background job processor for handling subtitle processing tasks
"""

import asyncio
import logging
from typing import Dict, Optional, Any
from datetime import datetime
import threading
import queue
import time

logger = logging.getLogger(__name__)

class JobProcessor:
    """Background job processor for managing subtitle processing tasks"""
    
    def __init__(self):
        self.jobs: Dict[str, Dict[str, Any]] = {}
        self.job_queue = queue.Queue()
        self.worker_thread = None
        self.running = False
        self._lock = threading.Lock()
    
    def start(self):
        """Start the job processor"""
        if not self.running:
            self.running = True
            self.worker_thread = threading.Thread(target=self._worker, daemon=True)
            self.worker_thread.start()
            logger.info("Job processor started")
    
    def stop(self):
        """Stop the job processor"""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
        logger.info("Job processor stopped")
    
    async def shutdown(self):
        """Async shutdown method"""
        self.stop()
    
    def _worker(self):
        """Worker thread for processing jobs"""
        while self.running:
            try:
                time.sleep(0.1)  # Small delay to prevent busy waiting
                # Process any queued jobs (placeholder for future implementation)
            except Exception as e:
                logger.error(f"Job processor worker error: {e}")
    
    def update_job_status(self, job_id: str, status: str, progress: int = 0, message: str = ""):
        """Update job status and progress"""
        with self._lock:
            if job_id not in self.jobs:
                self.jobs[job_id] = {
                    "id": job_id,
                    "created_at": datetime.now()
                }
            
            self.jobs[job_id].update({
                "status": status,
                "progress": progress,
                "message": message,
                "updated_at": datetime.now()
            })
            
            if status in ["completed", "failed"]:
                self.jobs[job_id]["completed_at"] = datetime.now()
        
        logger.info(f"Job {job_id} status updated: {status} ({progress}%) - {message}")
    
    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get current job status"""
        with self._lock:
            return self.jobs.get(job_id)
    
    def remove_job(self, job_id: str):
        """Remove completed job from memory"""
        with self._lock:
            if job_id in self.jobs:
                del self.jobs[job_id]
                logger.info(f"Job {job_id} removed from processor")
    
    def get_all_jobs(self) -> Dict[str, Dict[str, Any]]:
        """Get all jobs (for debugging/monitoring)"""
        with self._lock:
            return self.jobs.copy()

# Global job processor instance
job_processor = JobProcessor()

# Start the processor when module is imported
job_processor.start()
