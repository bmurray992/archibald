"""
Job Registry - Register all default jobs and handlers
"""
import logging
from datetime import datetime, timedelta
from .scheduler import get_scheduler, JobResult, register_job_handler, schedule_job
from .snapshot_job import snapshot_handler
from .indexer_job import indexer_handler
from .dedupe_job import dedupe_handler
from .health_staleness_job import health_staleness_handler

logger = logging.getLogger(__name__)


def register_all_jobs():
    """Register all default jobs with the scheduler"""
    scheduler = get_scheduler()
    
    # Register job handlers
    register_job_handler("snapshot", snapshot_handler)
    register_job_handler("indexer", indexer_handler) 
    register_job_handler("dedupe", dedupe_handler)
    register_job_handler("health_staleness", health_staleness_handler)
    
    # Schedule default recurring jobs
    _schedule_default_jobs(scheduler)
    
    logger.info("✅ All default jobs registered")


def _schedule_default_jobs(scheduler):
    """Schedule the default recurring jobs"""
    
    # Nightly snapshot at 3 AM
    snapshot_job_id = scheduler.schedule_job(
        name="snapshot",
        rrule_string="FREQ=DAILY;BYHOUR=3;BYMINUTE=0;BYSECOND=0",
        payload={
            "backup_type": "incremental",
            "retention_days": 14
        },
        max_retries=2,
        timeout_seconds=1800  # 30 minutes
    )
    
    # Incremental indexer every hour
    indexer_job_id = scheduler.schedule_job(
        name="indexer", 
        rrule_string="FREQ=HOURLY;BYMINUTE=0",
        payload={
            "mode": "incremental"
        },
        max_retries=3,
        timeout_seconds=300  # 5 minutes
    )
    
    # Dedupe job every 6 hours
    dedupe_job_id = scheduler.schedule_job(
        name="dedupe",
        rrule_string="FREQ=HOURLY;INTERVAL=6;BYMINUTE=30",
        payload={
            "min_file_size": 1024,  # Only dedupe files > 1KB
            "dry_run": False
        },
        max_retries=2,
        timeout_seconds=600  # 10 minutes  
    )
    
    # Health staleness check every 4 hours
    health_staleness_job_id = scheduler.schedule_job(
        name="health_staleness",
        rrule_string="FREQ=HOURLY;INTERVAL=4;BYMINUTE=15",
        payload={
            "max_staleness_hours": 24,
            "alert_threshold_hours": 48
        },
        max_retries=1,
        timeout_seconds=60  # 1 minute
    )
    
    logger.info("📅 Default jobs scheduled:")
    logger.info(f"  - Snapshot: {snapshot_job_id}")
    logger.info(f"  - Indexer: {indexer_job_id}")
    logger.info(f"  - Dedupe: {dedupe_job_id}")  
    logger.info(f"  - Health staleness: {health_staleness_job_id}")


def schedule_maintenance_jobs():
    """Schedule additional maintenance jobs"""
    scheduler = get_scheduler()
    
    # Weekly full snapshot on Sundays at 2 AM
    full_snapshot_job_id = scheduler.schedule_job(
        name="snapshot",
        rrule_string="FREQ=WEEKLY;BYDAY=SU;BYHOUR=2;BYMINUTE=0",
        payload={
            "backup_type": "full",
            "retention_days": 90
        },
        max_retries=1,
        timeout_seconds=3600  # 1 hour
    )
    
    # Full reindex weekly on Sundays at 4 AM  
    full_index_job_id = scheduler.schedule_job(
        name="indexer",
        rrule_string="FREQ=WEEKLY;BYDAY=SU;BYHOUR=4;BYMINUTE=0", 
        payload={
            "mode": "full_rebuild"
        },
        max_retries=1,
        timeout_seconds=1800  # 30 minutes
    )
    
    # Cleanup old jobs monthly
    cleanup_job_id = scheduler.schedule_job(
        name="cleanup_jobs",
        rrule_string="FREQ=MONTHLY;BYMONTHDAY=1;BYHOUR=1;BYMINUTE=0",
        payload={
            "older_than_days": 30
        },
        max_retries=1,
        timeout_seconds=300
    )
    
    logger.info("🔧 Maintenance jobs scheduled:")
    logger.info(f"  - Full snapshot: {full_snapshot_job_id}")
    logger.info(f"  - Full reindex: {full_index_job_id}")
    logger.info(f"  - Job cleanup: {cleanup_job_id}")


# Register cleanup job handler
async def cleanup_jobs_handler(payload):
    """Handler for cleaning up old completed jobs"""
    try:
        scheduler = get_scheduler()
        older_than_days = payload.get("older_than_days", 30)
        
        deleted_count = scheduler.cleanup_completed_jobs(older_than_days)
        
        return JobResult(
            success=True,
            message=f"Cleaned up {deleted_count} old jobs",
            data={"deleted_count": deleted_count}
        )
        
    except Exception as e:
        return JobResult(
            success=False,
            message=f"Job cleanup failed: {str(e)}"
        )

# Register the cleanup handler
register_job_handler("cleanup_jobs", cleanup_jobs_handler)