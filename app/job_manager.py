"""
Job Manager Module
Handles background task execution with limited concurrency and state tracking.
"""
import uuid
import logging
import asyncio
from enum import Enum
from typing import Dict, Any, Optional, Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

logger = logging.getLogger("app.job_manager")

class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class Job:
    """Represents a background job."""
    def __init__(self, func: Callable, user_id: int, job_type: str, args: tuple, kwargs: dict, metadata: Optional[Dict[str, Any]] = None):
        self.id = str(uuid.uuid4())
        self.user_id = user_id
        self.job_type = job_type
        self.status = JobStatus.PENDING
        self.submitted_at = datetime.now()
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.result: Any = None
        self.error: Optional[str] = None
        self.metadata: Dict[str, Any] = metadata or {}
        self._func = func
        self._args = args
        self._kwargs = kwargs

class JobManager:
    """
    Manages background jobs with a fixed-size thread pool.
    Stores job state in memory.
    """
    def __init__(self, max_workers: int = 2):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        # self.jobs replaced by Redis
        self.max_workers = max_workers
        # Import here to avoid circular dependencies if any
        from app.redis_client import redis_client
        self.redis = redis_client
        self.logger = logger
        self.logger.info(f"JobManager initialized with max_workers={max_workers}")
        
        # Recover pending jobs from Redis on startup
        self._recover_jobs()

    def submit_job(self, func: Callable, user_id: int, job_type: str, *args, metadata: Optional[Dict[str, Any]] = None, **kwargs) -> str:
        """
        Submit a function to be run in the background.
        Returns the job ID.
        
        Args:
            metadata: Optional dict with context info (file_name, table_id, etc.)
        """
        job = Job(func, user_id, job_type, args, kwargs, metadata=metadata)
        
        # 1. Save to Redis
        self._save_job(job)
        
        # 2. Add to Pending Sorted Set (for queue order/recovery)
        # Score = timestamp
        if self.redis.is_connected:
            self.redis.client.zadd("jobs:pending", {job.id: job.submitted_at.timestamp()})
        
        # 3. Submit to executor
        self.executor.submit(self._run_job, job.id, func, *args, **kwargs)
        
        self.logger.info(f"Job submitted: {job.id} [User: {user_id}, Type: {job_type}]")
        return job.id

    def _recover_jobs(self):
        """Recover jobs that were pending when the server restarted."""
        if not self.redis.is_connected:
            return

        # Get all pending job IDs from the sorted set
        # Using zrange to get all
        pending_ids = self.redis.client.zrange("jobs:pending", 0, -1)
        
        count = 0
        for job_id in pending_ids:
            job_data = self._get_job_data(job_id)
            if job_data and job_data.get('status') == JobStatus.PENDING:
                # We can't actually re-run the EXACT function because arguments might be complex objects
                # or the function reference is lost.
                # LIMITATION: For now, we only recover 'tracked' state correctness.
                # If we really want to recover execution, we need to pickle args or use a predefined registry of functions.
                # For this implementation, we will mark them as FAILED if they are not in the current memory executor
                # BUT since this runs on init, we assume we missed them.
                
                # Ideally: We need a registry of functions to re-submit.
                # Simpler approach for now: Mark them as failed with "Server Restarted" message
                # unless we implement a full task queue like Celery.
                
                # However, for 'Async Analysis', we want to try to support it.
                # Let's clean up stuck jobs for now to avoid indefinite pending.
                self.logger.warning(f"Marking stale pending job as failed: {job_id}")
                job_data['status'] = JobStatus.FAILED
                job_data['error'] = "Job interrupted by server restart"
                job_data['completed_at'] = datetime.now().isoformat()
                self._save_job_data(job_data)
                
                # Remove from pending set
                self.redis.client.zrem("jobs:pending", job_id)
                count += 1
                
        if count > 0:
            self.logger.info(f"Cleaned up {count} stale pending jobs from previous session")

    def _run_job(self, job_id: str, func: Callable, *args, **kwargs):
        """Internal worker method to run the job and update state."""
        # Update status to RUNNING
        self._update_status(job_id, JobStatus.RUNNING)
        
        # Remove from pending queue as it is now running
        if self.redis.is_connected:
            self.redis.client.zrem("jobs:pending", job_id)
            
        try:
            self.logger.info(f"Starting job execution: {job_id}")
            result = func(*args, **kwargs)
            
            # Update to COMPLETED
            self._update_status(job_id, JobStatus.COMPLETED, result=result)
            self.logger.info(f"Job completed successfully: {job_id}")
            
        except Exception as e:
            self.logger.error(f"Job failed: {job_id} - {e}")
            self._update_status(job_id, JobStatus.FAILED, error=str(e))

    def _save_job(self, job: Job):
        """Save job initial state to Redis."""
        data = self._job_to_dict(job)
        self._save_job_data(data)

    def _save_job_data(self, data: dict):
        if self.redis.is_connected:
            self.redis.set(f"job:{data['id']}", data, expire_seconds=604800)  # 7 days retention
        else:
            # Fallback to memory if redis fails (temporary)
            if not hasattr(self, '_memory_jobs'): self._memory_jobs = {}
            self._memory_jobs[data['id']] = data

    def _get_job_data(self, job_id: str) -> Optional[dict]:
        if self.redis.is_connected:
            return self.redis.get(f"job:{job_id}")
        else:
            return getattr(self, '_memory_jobs', {}).get(job_id)

    def _update_status(self, job_id: str, status: JobStatus, result: Any = None, error: Optional[str] = None):
        """Update job status in Redis."""
        data = self._get_job_data(job_id)
        if not data:
            return
            
        data['status'] = status.value
        if status == JobStatus.RUNNING:
            data['started_at'] = datetime.now().isoformat()
        elif status in [JobStatus.COMPLETED, JobStatus.FAILED]:
            data['completed_at'] = datetime.now().isoformat()
            
        if result is not None:
            data['result'] = result
        if error is not None:
            data['error'] = error
            
        self._save_job_data(data)

    def get_job(self, job_id: str) -> Optional[dict]:
        """Get job status and calculate queue position if pending."""
        job = self._get_job_data(job_id)
        if not job:
            return None
            
        # If pending, calculate queue position
        if job['status'] == JobStatus.PENDING.value and self.redis.is_connected:
            try:
                # Rank returns 0-based index
                rank = self.redis.client.zrank("jobs:pending", job_id)
                if rank is not None:
                    job['queue_position'] = rank + 1
                    job['queue_total'] = self.redis.client.zcard("jobs:pending")
            except Exception as e:
                self.logger.error(f"Failed to calc queue pos: {e}")
                
        return job

    def get_user_jobs(self, user_id: int, job_type: Optional[str] = None, limit: int = 10) -> list:
        """
        Get all jobs (not filtered by user) for transparency.
        All users can see all jobs, but only owners can edit/delete.
        
        Args:
            user_id: Still accepted for API compatibility but not used for filtering
            job_type: Optional filter by job type
            limit: Maximum number of jobs to return
        """
        # Fetch ALL jobs from Redis (not filtered by user)
        if not self.redis.is_connected:
            self.logger.warning(f"Fetching jobs from MEMORY")
            all_jobs = list(getattr(self, '_memory_jobs', {}).values())
        else:
            # Get all job keys
            keys = self.redis.client.keys("job:*")
            self.logger.info(f"Scanning Redis jobs. Found {len(keys)} total job keys.")
            all_jobs = []
            for k in keys:
                j = self.redis.get(k)
                if j:
                    all_jobs.append(j)
            self.logger.info(f"Returning {len(all_jobs)} total jobs (unfiltered by user).")
                    
        if job_type:
            all_jobs = [j for j in all_jobs if j.get('job_type') == job_type]
            
        # Sort by submitted_at
        all_jobs.sort(key=lambda x: x.get('submitted_at') or '', reverse=True)
        
        # Calculate queue stats for pending jobs in the result set
        if self.redis.is_connected:
            try:
                pending_total = self.redis.client.zcard("jobs:pending")
                for job in all_jobs:
                    if job.get('status') == JobStatus.PENDING.value:
                        rank = self.redis.client.zrank("jobs:pending", job['id'])
                        if rank is not None:
                            job['queue_position'] = rank + 1
                            job['queue_total'] = pending_total
            except Exception as e:
                self.logger.error(f"Failed to enrich jobs with queue stats: {e}")
                
        return all_jobs[:limit]

    def _job_to_dict(self, job: Job) -> dict:
        """Helper to serialize job."""
        return {
            "id": job.id,
            "user_id": job.user_id,
            "job_type": job.job_type,
            "status": job.status,
            "submitted_at": job.submitted_at.isoformat() if job.submitted_at else None,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "result": job.result,
            "error": job.error,
            "metadata": job.metadata
        }

    def delete_job(self, job_id: str, user_id: int):
        """Delete a specific job if it belongs to the user."""
        job = self.get_job(job_id)
        if not job:
            raise ValueError("Job not found")
        if job.get('user_id') != user_id:
            raise ValueError("Not authorized to delete this job")
        
        # Delete from Redis
        if self.redis.is_connected:
            self.redis.client.delete(f"job:{job_id}")
            # Remove from pending queue if present
            self.redis.client.zrem("jobs:pending", job_id)
        else:
            # Memory fallback
            if hasattr(self, '_memory_jobs') and job_id in self._memory_jobs:
                del self._memory_jobs[job_id]
        
        self.logger.info(f"Deleted job: {job_id}")

    def clear_user_jobs(self, user_id: int, cutoff: Optional[datetime] = None) -> int:
        """Clear jobs for a user, optionally filtered by date cutoff."""
        from datetime import datetime
        
        jobs = self.get_user_jobs(user_id, limit=1000)  # Get all jobs
        count = 0
        
        for job in jobs:
            # Skip if job is older than cutoff (we keep older jobs)
            if cutoff:
                submitted = datetime.fromisoformat(job['submitted_at']) if job.get('submitted_at') else None
                if submitted and submitted > cutoff:
                    continue  # Job is newer than cutoff, skip
            
            # Delete the job
            try:
                self.delete_job(job['id'], user_id)
                count += 1
            except:
                pass
        
        return count

    def cleanup_old_jobs(self, max_age_seconds: int = 604800):  # 7 days default
        """Clean up jobs older than max_age_seconds. Called periodically."""
        # Redis expires keys automatically via TTL set in _save_job_data
        # This is mainly for memory fallback
        if not self.redis.is_connected:
            from datetime import datetime, timedelta
            cutoff = datetime.now() - timedelta(seconds=max_age_seconds)
            if hasattr(self, '_memory_jobs'):
                to_delete = []
                for job_id, job in self._memory_jobs.items():
                    submitted = datetime.fromisoformat(job['submitted_at']) if job.get('submitted_at') else None
                    if submitted and submitted < cutoff:
                        to_delete.append(job_id)
                for job_id in to_delete:
                    del self._memory_jobs[job_id]
                if to_delete:
                    self.logger.info(f"Cleaned up {len(to_delete)} old jobs")

# Global instance with configurable workers
import os
_max_workers = int(os.getenv("JOB_MAX_WORKERS", 2))
job_manager = JobManager(max_workers=_max_workers)

