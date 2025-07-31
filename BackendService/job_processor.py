"""
Job processing and management utilities for background tasks
"""

import asyncio
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from enum import Enum
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor
import uuid
import os

from database import get_db_connection
from subtitle_processor import subtitle_processor

logger = logging.getLogger(__name__)

class JobStatus(Enum):
    """Job status enumeration"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class JobType(Enum):
    """Job type enumeration"""
    CORRECTION = "correction"
    GENERATION = "generation"
    TRANSLATION = "translation"
    VALIDATION = "validation"

@dataclass
class JobProgress:
    """Job progress information"""
    job_id: int
    progress_percent: int
    current_step: str
    total_steps: int
    current_step_number: int
    estimated_completion: Optional[datetime] = None
    message: Optional[str] = None

@dataclass
class JobResult:
    """Job execution result"""
    success: bool
    result_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    output_files: Optional[List[str]] = None

class JobProcessor:
    """Main job processing engine"""
    
    def __init__(self):
        self.active_jobs: Dict[int, asyncio.Task] = {}
        self.job_progress: Dict[int, JobProgress] = {}
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.progress_callbacks: Dict[int, List[Callable]] = {}
        
        # Job processing functions
        self.job_handlers = {
            JobType.CORRECTION: self._process_correction_job,
            JobType.GENERATION: self._process_generation_job,
            JobType.TRANSLATION: self._process_translation_job,
            JobType.VALIDATION: self._process_validation_job
        }
    
    # PUBLIC_INTERFACE
    async def start_job(self, job_id: int, job_type: JobType, job_data: Dict[str, Any]) -> bool:
        """
        Start processing a job in the background
        
        Args:
            job_id: Unique job identifier
            job_type: Type of job to process
            job_data: Job-specific data and parameters
            
        Returns:
            True if job started successfully, False otherwise
        """
        if job_id in self.active_jobs:
            logger.warning(f"Job {job_id} is already running")
            return False
        
        # Update job status to running
        self._update_job_status(job_id, JobStatus.RUNNING)
        
        # Initialize progress tracking
        self.job_progress[job_id] = JobProgress(
            job_id=job_id,
            progress_percent=0,
            current_step="Initializing",
            total_steps=self._get_total_steps(job_type),
            current_step_number=1
        )
        
        # Start job processing
        handler = self.job_handlers.get(job_type)
        if not handler:
            logger.error(f"No handler found for job type: {job_type}")
            self._update_job_status(job_id, JobStatus.FAILED)
            return False
        
        # Create and start async task
        task = asyncio.create_task(self._execute_job(job_id, handler, job_data))
        self.active_jobs[job_id] = task
        
        logger.info(f"Started job {job_id} of type {job_type}")
        return True
    
    async def _execute_job(self, job_id: int, handler: Callable, job_data: Dict[str, Any]):
        """Execute a job with error handling and progress tracking"""
        try:
            result = await handler(job_id, job_data)
            
            if result.success:
                self._update_job_status(job_id, JobStatus.COMPLETED, result.result_data)
                self._update_progress(job_id, 100, "Completed", "Job finished successfully")
                
                # Store result files in database
                if result.output_files:
                    self._store_job_results(job_id, result.output_files)
                    
            else:
                self._update_job_status(job_id, JobStatus.FAILED, {"error": result.error_message})
                self._update_progress(job_id, 0, "Failed", result.error_message or "Job failed")
                
        except Exception as e:
            logger.error(f"Job {job_id} failed with exception: {e}")
            self._update_job_status(job_id, JobStatus.FAILED, {"error": str(e)})
            self._update_progress(job_id, 0, "Failed", f"Job failed with error: {str(e)}")
            
        finally:
            # Clean up
            if job_id in self.active_jobs:
                del self.active_jobs[job_id]
            
            # Keep progress for a while for client retrieval
            asyncio.create_task(self._cleanup_job_progress(job_id))
    
    async def _cleanup_job_progress(self, job_id: int):
        """Clean up job progress after completion"""
        await asyncio.sleep(3600)  # Keep for 1 hour
        if job_id in self.job_progress:
            del self.job_progress[job_id]
    
    def _get_total_steps(self, job_type: JobType) -> int:
        """Get total steps for a job type"""
        step_counts = {
            JobType.CORRECTION: 5,  # validate, analyze, correct, verify, save
            JobType.GENERATION: 4,  # extract audio, transcribe, format, save
            JobType.TRANSLATION: 3, # analyze, translate, save
            JobType.VALIDATION: 2   # analyze, report
        }
        return step_counts.get(job_type, 3)
    
    def _update_progress(self, job_id: int, progress: int, step: str, message: str = ""):
        """Update job progress"""
        if job_id in self.job_progress:
            progress_info = self.job_progress[job_id]
            progress_info.progress_percent = progress
            progress_info.current_step = step
            progress_info.message = message
            
            # Notify callbacks
            if job_id in self.progress_callbacks:
                for callback in self.progress_callbacks[job_id]:
                    try:
                        callback(progress_info)
                    except Exception as e:
                        logger.error(f"Progress callback failed: {e}")
    
    def _update_job_status(self, job_id: int, status: JobStatus, result_data: Optional[Dict] = None):
        """Update job status in database"""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            if status == JobStatus.COMPLETED:
                result_url = result_data.get('result_url') if result_data else None
                cursor.execute("""
                    UPDATE jobs SET status = ?, result_url = ?, completed_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (status.value, result_url, job_id))
            else:
                cursor.execute("UPDATE jobs SET status = ? WHERE id = ?", (status.value, job_id))
            
            conn.commit()
            
        except Exception as e:
            logger.error(f"Failed to update job status: {e}")
        finally:
            conn.close()
    
    def _store_job_results(self, job_id: int, output_files: List[str]):
        """Store job result files"""
        # In a production system, this would:
        # 1. Move files to permanent storage
        # 2. Update database with file locations
        # 3. Generate download URLs
        
        if output_files:
            primary_result = output_files[0]
            filename = os.path.basename(primary_result)
            result_url = f"/download/{filename}"
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            try:
                cursor.execute("""
                    UPDATE jobs SET result_url = ? WHERE id = ?
                """, (result_url, job_id))
                conn.commit()
            finally:
                conn.close()
    
    async def _process_correction_job(self, job_id: int, job_data: Dict[str, Any]) -> JobResult:
        """Process subtitle correction job"""
        try:
            video_path = job_data.get('video_path')
            subtitle_path = job_data.get('subtitle_path')
            offset_ms = job_data.get('offset_ms', 0)
            
            if not video_path or not subtitle_path:
                return JobResult(False, error_message="Missing video or subtitle path")
            
            # Step 1: Validate input files
            self._update_progress(job_id, 20, "Validating input files")
            await asyncio.sleep(0.5)  # Simulate processing
            
            if not os.path.exists(video_path) or not os.path.exists(subtitle_path):
                return JobResult(False, error_message="Input files not found")
            
            # Step 2: Analyze subtitle content
            self._update_progress(job_id, 40, "Analyzing subtitle content")
            
            with open(subtitle_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            validation_result = subtitle_processor.validate_subtitles(content)
            if not validation_result.is_valid:
                error_issues = [issue.message for issue in validation_result.issues if issue.severity == "error"]
                if error_issues:
                    return JobResult(False, error_message=f"Subtitle validation failed: {', '.join(error_issues)}")
            
            # Step 3: Perform correction
            self._update_progress(job_id, 60, "Processing subtitle synchronization")
            
            corrected_path = await subtitle_processor.correct_subtitle_sync(
                video_path, subtitle_path, offset_ms
            )
            
            # Step 4: Verify results
            self._update_progress(job_id, 80, "Verifying corrected subtitles")
            await asyncio.sleep(0.5)
            
            if not os.path.exists(corrected_path):
                return JobResult(False, error_message="Correction failed to produce output")
            
            # Step 5: Finalize
            self._update_progress(job_id, 95, "Finalizing results")
            
            return JobResult(
                True,
                result_data={
                    "corrected_file": corrected_path,
                    "original_issues": len(validation_result.issues),
                    "result_url": f"/download/{os.path.basename(corrected_path)}"
                },
                output_files=[corrected_path]
            )
            
        except Exception as e:
            logger.error(f"Correction job {job_id} failed: {e}")
            return JobResult(False, error_message=str(e))
    
    async def _process_generation_job(self, job_id: int, job_data: Dict[str, Any]) -> JobResult:
        """Process subtitle generation job"""
        try:
            video_path = job_data.get('video_path')
            target_language = job_data.get('target_language', 'en')
            
            if not video_path:
                return JobResult(False, error_message="Missing video path")
            
            # Step 1: Validate video file
            self._update_progress(job_id, 25, "Validating video file")
            await asyncio.sleep(0.5)
            
            if not os.path.exists(video_path):
                return JobResult(False, error_message="Video file not found")
            
            # Step 2: Extract and analyze audio
            self._update_progress(job_id, 50, "Extracting and analyzing audio")
            await asyncio.sleep(1)  # Simulate audio processing
            
            # Step 3: Generate subtitles
            self._update_progress(job_id, 75, "Generating subtitles using AI")
            
            generated_path = await subtitle_processor.generate_subtitles_from_audio(
                video_path, target_language
            )
            
            # Step 4: Finalize
            self._update_progress(job_id, 95, "Finalizing generated subtitles")
            
            if not os.path.exists(generated_path):
                return JobResult(False, error_message="Generation failed to produce output")
            
            return JobResult(
                True,
                result_data={
                    "generated_file": generated_path,
                    "language": target_language,
                    "result_url": f"/download/{os.path.basename(generated_path)}"
                },
                output_files=[generated_path]
            )
            
        except Exception as e:
            logger.error(f"Generation job {job_id} failed: {e}")
            return JobResult(False, error_message=str(e))
    
    async def _process_translation_job(self, job_id: int, job_data: Dict[str, Any]) -> JobResult:
        """Process subtitle translation job"""
        try:
            subtitle_path = job_data.get('subtitle_path')
            target_language = job_data.get('target_language')
            
            if not subtitle_path or not target_language:
                return JobResult(False, error_message="Missing subtitle path or target language")
            
            # Step 1: Validate subtitle file
            self._update_progress(job_id, 33, "Validating subtitle file")
            await asyncio.sleep(0.5)
            
            if not os.path.exists(subtitle_path):
                return JobResult(False, error_message="Subtitle file not found")
            
            # Step 2: Translate subtitles
            self._update_progress(job_id, 66, f"Translating to {target_language}")
            
            translated_path = await subtitle_processor.translate_subtitles(
                subtitle_path, target_language
            )
            
            # Step 3: Finalize
            self._update_progress(job_id, 95, "Finalizing translation")
            
            if not os.path.exists(translated_path):
                return JobResult(False, error_message="Translation failed to produce output")
            
            return JobResult(
                True,
                result_data={
                    "translated_file": translated_path,
                    "target_language": target_language,
                    "result_url": f"/download/{os.path.basename(translated_path)}"
                },
                output_files=[translated_path]
            )
            
        except Exception as e:
            logger.error(f"Translation job {job_id} failed: {e}")
            return JobResult(False, error_message=str(e))
    
    async def _process_validation_job(self, job_id: int, job_data: Dict[str, Any]) -> JobResult:
        """Process subtitle validation job"""
        try:
            subtitle_path = job_data.get('subtitle_path')
            
            if not subtitle_path:
                return JobResult(False, error_message="Missing subtitle path")
            
            # Step 1: Load and analyze
            self._update_progress(job_id, 50, "Analyzing subtitle content")
            
            if not os.path.exists(subtitle_path):
                return JobResult(False, error_message="Subtitle file not found")
            
            with open(subtitle_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            validation_result = subtitle_processor.validate_subtitles(content)
            
            # Step 2: Generate report
            self._update_progress(job_id, 95, "Generating validation report")
            await asyncio.sleep(0.5)
            
            return JobResult(
                True,
                result_data={
                    "validation_result": {
                        "is_valid": validation_result.is_valid,
                        "format": validation_result.format_type.value,
                        "total_issues": len(validation_result.issues),
                        "errors": len([i for i in validation_result.issues if i.severity == "error"]),
                        "warnings": len([i for i in validation_result.issues if i.severity == "warning"]),
                        "statistics": validation_result.statistics
                    }
                }
            )
            
        except Exception as e:
            logger.error(f"Validation job {job_id} failed: {e}")
            return JobResult(False, error_message=str(e))
    
    # PUBLIC_INTERFACE
    def get_job_progress(self, job_id: int) -> Optional[JobProgress]:
        """
        Get current progress for a job
        
        Args:
            job_id: Job identifier
            
        Returns:
            JobProgress object or None if not found
        """
        return self.job_progress.get(job_id)
    
    # PUBLIC_INTERFACE
    def cancel_job(self, job_id: int) -> bool:
        """
        Cancel a running job
        
        Args:
            job_id: Job identifier
            
        Returns:
            True if job was cancelled, False if not found or already completed
        """
        if job_id in self.active_jobs:
            task = self.active_jobs[job_id]
            task.cancel()
            
            self._update_job_status(job_id, JobStatus.CANCELLED)
            self._update_progress(job_id, 0, "Cancelled", "Job was cancelled by user")
            
            del self.active_jobs[job_id]
            return True
        
        return False
    
    # PUBLIC_INTERFACE
    def register_progress_callback(self, job_id: int, callback: Callable[[JobProgress], None]):
        """
        Register a callback for job progress updates
        
        Args:
            job_id: Job identifier
            callback: Function to call with progress updates
        """
        if job_id not in self.progress_callbacks:
            self.progress_callbacks[job_id] = []
        
        self.progress_callbacks[job_id].append(callback)
    
    # PUBLIC_INTERFACE
    def get_active_jobs(self) -> List[int]:
        """
        Get list of currently active job IDs
        
        Returns:
            List of active job IDs
        """
        return list(self.active_jobs.keys())
    
    # PUBLIC_INTERFACE
    async def shutdown(self):
        """Gracefully shutdown job processor"""
        logger.info("Shutting down job processor...")
        
        # Cancel all active jobs
        for job_id, task in self.active_jobs.items():
            task.cancel()
            self._update_job_status(job_id, JobStatus.CANCELLED)
        
        # Wait for tasks to complete
        if self.active_jobs:
            await asyncio.gather(*self.active_jobs.values(), return_exceptions=True)
        
        # Shutdown thread pool
        self.executor.shutdown(wait=True)
        
        logger.info("Job processor shutdown complete")

# Global job processor instance
job_processor = JobProcessor()
