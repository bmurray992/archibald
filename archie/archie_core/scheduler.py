"""
ArchieOS Scheduler - Automated task scheduling for maintenance and backups
"""
import asyncio
import schedule
import time
from datetime import datetime, timedelta
from typing import Dict, Callable, Any, List
from pathlib import Path
import logging
import threading
import json

from .backup_manager import BackupManager
from .prune_manager import PruneManager
from .memory_manager import MemoryManager

logger = logging.getLogger(__name__)


class ArchieScheduler:
    """
    Manages scheduled tasks for ArchieOS maintenance, backups, and automation
    """
    
    def __init__(self):
        self.backup_manager = BackupManager()
        self.prune_manager = PruneManager()
        self.memory_manager = MemoryManager()
        
        self.running = False
        self.scheduler_thread = None
        self.task_history = []
        
        # Initialize default schedule
        self._setup_default_schedule()
        
        logger.info("⏰ Archie: Scheduler initialized - Ready to keep things running smoothly!")
    
    def _setup_default_schedule(self):
        """Set up default scheduled tasks"""
        
        # Daily tasks at 2 AM
        schedule.every().day.at("02:00").do(self._daily_memory_backup)
        schedule.every().day.at("02:15").do(self._daily_plugin_backup)
        schedule.every().day.at("02:30").do(self._daily_temp_cleanup)
        
        # Weekly tasks on Sunday at 3 AM
        schedule.every().sunday.at("03:00").do(self._weekly_full_backup)
        schedule.every().sunday.at("03:30").do(self._weekly_pruning_cycle)
        schedule.every().sunday.at("04:00").do(self._weekly_old_backup_cleanup)
        
        # Monthly tasks on the 1st at 4 AM
        schedule.every().month.do(self._monthly_deep_analysis)
        
        logger.info("📅 Default schedule configured - daily, weekly, and monthly tasks ready")
    
    def start(self):
        """Start the scheduler in a background thread"""
        if self.running:
            logger.warning("⚠️ Scheduler already running")
            return
        
        self.running = True
        self.scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.scheduler_thread.start()
        
        logger.info("🚀 Scheduler started - automation is now active!")
    
    def stop(self):
        """Stop the scheduler"""
        self.running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
        
        logger.info("⏹️ Scheduler stopped")
    
    def _run_scheduler(self):
        """Main scheduler loop"""
        while self.running:
            try:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
            except Exception as e:
                logger.error(f"❌ Scheduler error: {e}")
                time.sleep(60)
    
    def add_task(self, 
                 name: str, 
                 schedule_spec: str, 
                 task_func: Callable, 
                 *args, **kwargs) -> bool:
        """
        Add a custom scheduled task
        
        Args:
            name: Task name for identification
            schedule_spec: Schedule in format like "daily.at('10:00')" or "every(2).hours"
            task_func: Function to execute
            *args, **kwargs: Arguments for the task function
        """
        try:
            # Parse schedule specification
            if "daily.at" in schedule_spec:
                time_str = schedule_spec.split("'")[1]
                schedule.every().day.at(time_str).do(
                    self._execute_custom_task, name, task_func, *args, **kwargs
                )
            elif "every(" in schedule_spec and ").hours" in schedule_spec:
                hours = int(schedule_spec.split("(")[1].split(")")[0])
                schedule.every(hours).hours.do(
                    self._execute_custom_task, name, task_func, *args, **kwargs
                )
            elif "weekly" in schedule_spec:
                schedule.every().week.do(
                    self._execute_custom_task, name, task_func, *args, **kwargs
                )
            else:
                logger.error(f"❌ Unsupported schedule format: {schedule_spec}")
                return False
            
            logger.info(f"📅 Added custom task: {name} ({schedule_spec})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to add task {name}: {e}")
            return False
    
    def _execute_custom_task(self, name: str, task_func: Callable, *args, **kwargs):
        """Execute a custom task with error handling and logging"""
        start_time = datetime.now()
        
        try:
            logger.info(f"🔄 Executing scheduled task: {name}")
            result = task_func(*args, **kwargs)
            
            # Log task completion
            self._log_task_execution(name, "success", start_time, result)
            
        except Exception as e:
            logger.error(f"❌ Task {name} failed: {e}")
            self._log_task_execution(name, "failed", start_time, {"error": str(e)})
    
    def _daily_memory_backup(self):
        """Daily memory database backup"""
        result = self.backup_manager.backup_memory_database()
        self._log_task_execution("daily_memory_backup", 
                                "success" if result.get("success") else "failed",
                                datetime.now(), result)
    
    def _daily_plugin_backup(self):
        """Daily plugin data backup"""
        result = self.backup_manager.backup_plugin_data()
        self._log_task_execution("daily_plugin_backup",
                                "success" if result.get("success") else "failed", 
                                datetime.now(), result)
    
    def _daily_temp_cleanup(self):
        """Daily temporary file cleanup"""
        result = self.prune_manager.cleanup_temp_files()
        self._log_task_execution("daily_temp_cleanup", "success", datetime.now(), result)
    
    def _weekly_full_backup(self):
        """Weekly full system backup"""
        result = self.backup_manager.create_full_backup()
        self._log_task_execution("weekly_full_backup",
                                "success" if result.get("success") else "failed",
                                datetime.now(), result)
    
    def _weekly_pruning_cycle(self):
        """Weekly storage pruning and rotation"""
        result = self.prune_manager.run_pruning_cycle()
        self._log_task_execution("weekly_pruning_cycle", "success", datetime.now(), result)
    
    def _weekly_old_backup_cleanup(self):
        """Weekly cleanup of old backups"""
        result = self.backup_manager.cleanup_old_backups(days_to_keep=30)
        self._log_task_execution("weekly_backup_cleanup",
                                "success" if result.get("success") else "failed",
                                datetime.now(), result)
    
    def _monthly_deep_analysis(self):
        """Monthly deep storage analysis and optimization"""
        analysis = self.prune_manager.get_storage_analysis()
        archive_candidates = self.prune_manager.identify_archive_candidates()
        
        result = {
            "storage_analysis": analysis,
            "archive_candidates_count": len(archive_candidates),
            "recommendations": analysis.get("recommendations", [])
        }
        
        self._log_task_execution("monthly_deep_analysis", "success", datetime.now(), result)
    
    def _log_task_execution(self, task_name: str, status: str, start_time: datetime, result: Any):
        """Log task execution to history"""
        execution_log = {
            "task_name": task_name,
            "status": status,
            "start_time": start_time.isoformat(),
            "duration_seconds": (datetime.now() - start_time).total_seconds(),
            "result": result
        }
        
        self.task_history.append(execution_log)
        
        # Keep only last 1000 entries
        if len(self.task_history) > 1000:
            self.task_history = self.task_history[-1000:]
        
        # Also log to memory manager for permanent storage
        try:
            self.memory_manager.store_memory(
                content=f"Scheduled task {task_name} completed with status: {status}",
                entry_type="system_task",
                assistant_id="archie_scheduler",
                metadata=execution_log,
                tags=["scheduled", "system", task_name],
                source_method="automation"
            )
        except Exception as e:
            logger.warning(f"Could not store task log to memory: {e}")
    
    def get_schedule_status(self) -> Dict[str, Any]:
        """Get current schedule status and recent task history"""
        next_jobs = []
        
        for job in schedule.jobs:
            next_jobs.append({
                "job": str(job),
                "next_run": job.next_run.isoformat() if job.next_run else None,
                "last_run": job.last_run.isoformat() if job.last_run else None
            })
        
        # Get recent task history
        recent_tasks = sorted(self.task_history, key=lambda x: x['start_time'], reverse=True)[:20]
        
        return {
            "scheduler_running": self.running,
            "total_jobs": len(schedule.jobs),
            "next_jobs": next_jobs,
            "recent_tasks": recent_tasks,
            "uptime_hours": self._get_uptime_hours()
        }
    
    def get_task_statistics(self) -> Dict[str, Any]:
        """Get task execution statistics"""
        if not self.task_history:
            return {"message": "No task history available"}
        
        # Calculate statistics
        success_count = sum(1 for task in self.task_history if task['status'] == 'success')
        failed_count = len(self.task_history) - success_count
        
        # Task frequency
        task_counts = {}
        for task in self.task_history:
            task_name = task['task_name']
            task_counts[task_name] = task_counts.get(task_name, 0) + 1
        
        # Average duration by task
        task_durations = {}
        for task in self.task_history:
            task_name = task['task_name']
            if task_name not in task_durations:
                task_durations[task_name] = []
            task_durations[task_name].append(task['duration_seconds'])
        
        avg_durations = {
            task: sum(durations) / len(durations)
            for task, durations in task_durations.items()
        }
        
        return {
            "total_executions": len(self.task_history),
            "success_rate": round(success_count / len(self.task_history) * 100, 2),
            "failed_count": failed_count,
            "task_counts": task_counts,
            "average_durations": {k: round(v, 2) for k, v in avg_durations.items()},
            "most_recent": self.task_history[-1] if self.task_history else None
        }
    
    def force_run_task(self, task_name: str) -> Dict[str, Any]:
        """Manually trigger a scheduled task"""
        task_map = {
            "memory_backup": self._daily_memory_backup,
            "plugin_backup": self._daily_plugin_backup,
            "temp_cleanup": self._daily_temp_cleanup,
            "full_backup": self._weekly_full_backup,
            "pruning_cycle": self._weekly_pruning_cycle,
            "backup_cleanup": self._weekly_old_backup_cleanup,
            "deep_analysis": self._monthly_deep_analysis
        }
        
        if task_name not in task_map:
            return {
                "success": False,
                "error": f"Unknown task: {task_name}",
                "available_tasks": list(task_map.keys())
            }
        
        try:
            start_time = datetime.now()
            logger.info(f"🚀 Manually executing task: {task_name}")
            
            task_map[task_name]()
            
            duration = (datetime.now() - start_time).total_seconds()
            
            return {
                "success": True,
                "task_name": task_name,
                "duration_seconds": round(duration, 2),
                "executed_at": start_time.isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Manual task execution failed: {e}")
            return {
                "success": False,
                "task_name": task_name,
                "error": str(e)
            }
    
    def _get_uptime_hours(self) -> float:
        """Calculate scheduler uptime in hours"""
        if not self.task_history:
            return 0.0
        
        first_task = min(self.task_history, key=lambda x: x['start_time'])
        start_time = datetime.fromisoformat(first_task['start_time'])
        uptime = datetime.now() - start_time
        
        return round(uptime.total_seconds() / 3600, 2)
    
    def close(self):
        """Clean shutdown"""
        self.stop()
        if self.backup_manager:
            self.backup_manager.close()
        if self.prune_manager:
            self.prune_manager.close()
        if self.memory_manager:
            self.memory_manager.close()
            
        logger.info("🏁 Archie: Scheduler shutting down gracefully")