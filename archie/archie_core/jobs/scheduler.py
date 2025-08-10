"""
RRULE-based Job Scheduler for ArchieOS
Supports recurrence rules, backoff, retry logic, and persistence
"""
import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable, Awaitable
from dateutil import rrule
from dateutil.parser import parse as parse_date
import traceback
from concurrent.futures import ThreadPoolExecutor
from tenacity import retry, stop_after_attempt, wait_exponential

from ..db import Database
from ..models import Job

logger = logging.getLogger(__name__)


class JobResult:
    """Job execution result"""
    def __init__(self, success: bool, message: str = "", data: Any = None):
        self.success = success
        self.message = message
        self.data = data


class JobScheduler:
    """RRULE-based job scheduler with persistence and retry logic"""
    
    def __init__(self):
        self.db = Database()
        self.db.initialize()
        
        # Job registry (name -> handler function)
        self.job_handlers: Dict[str, Callable[..., Awaitable[JobResult]]] = {}
        
        # Runtime state
        self.running = False
        self.executor = ThreadPoolExecutor(max_workers=4)
        self._scheduler_task = None
        
        # Configuration
        self.check_interval = 30  # seconds
        self.max_concurrent_jobs = 4
        
        logger.info("🕐 Job scheduler initialized")
    
    def register_job_handler(self, job_name: str, handler: Callable[..., Awaitable[JobResult]]):
        """Register a job handler function"""
        self.job_handlers[job_name] = handler
        logger.info(f"📝 Registered job handler: {job_name}")
    
    def schedule_job(self, 
                    name: str,
                    rrule_string: str,
                    payload: Optional[Dict[str, Any]] = None,
                    max_retries: int = 3,
                    timeout_seconds: int = 300) -> str:
        """Schedule a new recurring job"""
        
        job_id = str(uuid.uuid4())
        next_run = self._calculate_next_run(rrule_string)
        
        job_data = {
            'id': job_id,
            'name': name,
            'status': 'pending',
            'next_run': int(next_run.timestamp()) if next_run else None,
            'payload': payload or {},
            'retries': 0,
            'rrule': rrule_string,
            'max_retries': max_retries,
            'timeout_seconds': timeout_seconds
        }
        
        self.db.create_job(job_data)
        logger.info(f"📅 Scheduled job '{name}' (ID: {job_id}) next run: {next_run}")
        return job_id
    
    def schedule_one_time_job(self,
                             name: str,
                             run_at: datetime,
                             payload: Optional[Dict[str, Any]] = None,
                             max_retries: int = 3,
                             timeout_seconds: int = 300) -> str:
        """Schedule a one-time job"""
        
        job_id = str(uuid.uuid4())
        
        job_data = {
            'id': job_id,
            'name': name,
            'status': 'pending',
            'next_run': int(run_at.timestamp()),
            'payload': payload or {},
            'retries': 0,
            'max_retries': max_retries,
            'timeout_seconds': timeout_seconds
        }
        
        self.db.create_job(job_data)
        logger.info(f"⏰ Scheduled one-time job '{name}' (ID: {job_id}) at: {run_at}")
        return job_id
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a pending or failed job"""
        try:
            self.db.update_job(job_id, {
                'status': 'cancelled'
            })
            logger.info(f"❌ Cancelled job {job_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to cancel job {job_id}: {e}")
            return False
    
    async def start(self):
        """Start the job scheduler"""
        if self.running:
            logger.warning("Scheduler already running")
            return
        
        self.running = True
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        logger.info("🚀 Job scheduler started")
    
    async def stop(self):
        """Stop the job scheduler"""
        if not self.running:
            return
        
        self.running = False
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
        
        self.executor.shutdown(wait=True)
        logger.info("⏹️ Job scheduler stopped")
    
    async def _scheduler_loop(self):
        """Main scheduler loop"""
        while self.running:
            try:
                # Get pending jobs
                pending_jobs = self.db.get_pending_jobs()
                
                # Execute ready jobs
                for job in pending_jobs:
                    if not self.running:
                        break
                    
                    # Check if it's time to run
                    current_time = int(time.time())
                    if job['next_run'] and job['next_run'] <= current_time:
                        # Create task for job execution
                        asyncio.create_task(self._execute_job(job))
                
                # Wait before next check
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                await asyncio.sleep(5)
    
    async def _execute_job(self, job: Dict[str, Any]):
        """Execute a job with timeout and error handling"""
        job_id = job['id']
        job_name = job['name']
        
        logger.info(f"🔄 Executing job '{job_name}' (ID: {job_id})")
        
        # Update status to running
        self.db.update_job(job_id, {
            'status': 'running',
            'last_run': int(time.time())
        })
        
        try:
            # Get handler
            handler = self.job_handlers.get(job_name)
            if not handler:
                raise Exception(f"No handler registered for job '{job_name}'")
            
            # Execute with timeout
            result = await asyncio.wait_for(
                handler(job['payload']),
                timeout=job['timeout_seconds']
            )
            
            if result.success:
                # Job succeeded
                await self._handle_job_success(job, result)
            else:
                # Job failed
                await self._handle_job_failure(job, result.message)
                
        except asyncio.TimeoutError:
            await self._handle_job_failure(job, "Job timed out")
        except Exception as e:
            error_msg = f"Job execution failed: {str(e)}\n{traceback.format_exc()}"
            await self._handle_job_failure(job, error_msg)
    
    async def _handle_job_success(self, job: Dict[str, Any], result: JobResult):
        """Handle successful job execution"""
        job_id = job['id']
        
        # Calculate next run if recurring
        next_run = None
        if job.get('rrule'):
            next_run = self._calculate_next_run(job['rrule'])
        
        # Update job
        updates = {
            'status': 'pending' if next_run else 'completed',
            'retries': 0,  # Reset retries on success
            'error_message': None,
            'result': {
                'success': True,
                'message': result.message,
                'data': result.data,
                'completed_at': datetime.now().isoformat()
            }
        }
        
        if next_run:
            updates['next_run'] = int(next_run.timestamp())
        
        self.db.update_job(job_id, updates)
        
        logger.info(f"✅ Job '{job['name']}' completed successfully")
        if next_run:
            logger.info(f"⏭️ Next run scheduled for: {next_run}")
    
    async def _handle_job_failure(self, job: Dict[str, Any], error_message: str):
        """Handle failed job execution with retry logic"""
        job_id = job['id']
        retries = job['retries'] + 1
        max_retries = job['max_retries']
        
        if retries >= max_retries:
            # Max retries reached, mark as failed
            self.db.update_job(job_id, {
                'status': 'failed',
                'retries': retries,
                'error_message': error_message,
                'result': {
                    'success': False,
                    'message': error_message,
                    'failed_at': datetime.now().isoformat()
                }
            })
            logger.error(f"❌ Job '{job['name']}' failed permanently after {max_retries} retries")
        else:
            # Schedule retry with exponential backoff
            retry_delay = min(300, 30 * (2 ** (retries - 1)))  # Cap at 5 minutes
            next_retry = datetime.now() + timedelta(seconds=retry_delay)
            
            self.db.update_job(job_id, {
                'status': 'pending',
                'retries': retries,
                'next_run': int(next_retry.timestamp()),
                'error_message': error_message
            })
            
            logger.warning(f"⚠️ Job '{job['name']}' failed (attempt {retries}/{max_retries}), "
                          f"retrying in {retry_delay}s: {error_message}")
    
    def _calculate_next_run(self, rrule_string: str) -> Optional[datetime]:
        """Calculate the next run time from an RRULE string"""
        try:
            # Parse RRULE
            if rrule_string.startswith('RRULE:'):
                rrule_string = rrule_string[6:]
            
            # Create rule from string
            rule = rrule.rrulestr(rrule_string, dtstart=datetime.now())
            
            # Get next occurrence
            next_run = rule.after(datetime.now())
            return next_run
            
        except Exception as e:
            logger.error(f"Failed to parse RRULE '{rrule_string}': {e}")
            return None
    
    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific job"""
        cur = self.db.connection.execute(
            "SELECT * FROM jobs WHERE id = ?",
            (job_id,)
        )
        row = cur.fetchone()
        
        if row:
            return {
                'id': row['id'],
                'name': row['name'],
                'status': row['status'],
                'last_run': row['last_run'],
                'next_run': row['next_run'],
                'retries': row['retries'],
                'max_retries': row['max_retries'],
                'rrule': row['rrule'],
                'error_message': row['error_message'],
                'result': json.loads(row['result']) if row['result'] else None
            }
        
        return None
    
    def list_jobs(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List jobs, optionally filtered by status"""
        query = "SELECT * FROM jobs"
        params = []
        
        if status:
            query += " WHERE status = ?"
            params.append(status)
        
        query += " ORDER BY next_run ASC"
        
        cur = self.db.connection.execute(query, params)
        
        jobs = []
        for row in cur:
            jobs.append({
                'id': row['id'],
                'name': row['name'],
                'status': row['status'],
                'last_run': row['last_run'],
                'next_run': row['next_run'],
                'retries': row['retries'],
                'max_retries': row['max_retries'],
                'rrule': row['rrule'],
                'error_message': row['error_message']
            })
        
        return jobs
    
    def get_scheduler_stats(self) -> Dict[str, Any]:
        """Get scheduler statistics"""
        # Job counts by status
        cur = self.db.connection.execute(
            "SELECT status, COUNT(*) as count FROM jobs GROUP BY status"
        )
        status_counts = {row['status']: row['count'] for row in cur}
        
        # Upcoming jobs
        cur = self.db.connection.execute("""
            SELECT * FROM jobs 
            WHERE status = 'pending' AND next_run > ? 
            ORDER BY next_run LIMIT 5
        """, (int(time.time()),))
        
        upcoming_jobs = []
        for row in cur:
            next_run = datetime.fromtimestamp(row['next_run']) if row['next_run'] else None
            upcoming_jobs.append({
                'id': row['id'],
                'name': row['name'],
                'next_run': next_run.isoformat() if next_run else None
            })
        
        # Recent failures
        cur = self.db.connection.execute("""
            SELECT name, error_message, last_run FROM jobs 
            WHERE status = 'failed' 
            ORDER BY last_run DESC LIMIT 5
        """)
        
        recent_failures = []
        for row in cur:
            last_run = datetime.fromtimestamp(row['last_run']) if row['last_run'] else None
            recent_failures.append({
                'name': row['name'],
                'error': row['error_message'],
                'failed_at': last_run.isoformat() if last_run else None
            })
        
        return {
            'running': self.running,
            'registered_handlers': list(self.job_handlers.keys()),
            'status_counts': status_counts,
            'upcoming_jobs': upcoming_jobs,
            'recent_failures': recent_failures,
            'check_interval_seconds': self.check_interval
        }
    
    def cleanup_completed_jobs(self, older_than_days: int = 30):
        """Clean up old completed jobs"""
        cutoff = int((datetime.now() - timedelta(days=older_than_days)).timestamp())
        
        cur = self.db.connection.execute("""
            DELETE FROM jobs 
            WHERE status = 'completed' AND last_run < ?
        """, (cutoff,))
        
        deleted_count = cur.rowcount
        logger.info(f"🧹 Cleaned up {deleted_count} completed jobs older than {older_than_days} days")
        return deleted_count


# Global scheduler instance
_scheduler = None


def get_scheduler() -> JobScheduler:
    """Get global scheduler instance"""
    global _scheduler
    if _scheduler is None:
        _scheduler = JobScheduler()
    return _scheduler


async def start_scheduler():
    """Start the global scheduler"""
    scheduler = get_scheduler()
    await scheduler.start()


async def stop_scheduler():
    """Stop the global scheduler"""
    scheduler = get_scheduler()
    await scheduler.stop()


def schedule_job(name: str, 
                rrule_string: str,
                payload: Optional[Dict[str, Any]] = None,
                max_retries: int = 3,
                timeout_seconds: int = 300) -> str:
    """Convenience function to schedule a job"""
    scheduler = get_scheduler()
    return scheduler.schedule_job(name, rrule_string, payload, max_retries, timeout_seconds)


def register_job_handler(name: str, handler: Callable[..., Awaitable[JobResult]]):
    """Convenience function to register a job handler"""
    scheduler = get_scheduler()
    scheduler.register_job_handler(name, handler)