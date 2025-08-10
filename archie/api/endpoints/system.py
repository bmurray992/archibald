"""
ArchieOS System Management API Endpoints
"""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field

from archie_core.backup_manager import BackupManager
from archie_core.prune_manager import PruneManager
from archie_core.auto_pruner import AutoPruner
from archie_core.scheduler import ArchieScheduler
from archie_core.auth_manager import AuthManager
from archie_core.personality import ArchiePersonality
from api.endpoints.auth import require_auth

router = APIRouter(prefix="/system", tags=["system"])


class SystemResponse(BaseModel):
    """Standard system response"""
    success: bool
    message: str
    data: Optional[dict] = None
    archie_says: Optional[str] = None


class BackupRequest(BaseModel):
    """Backup request parameters"""
    backup_type: str = Field(..., description="Type of backup: memory, plugins, or full")
    plugin_name: Optional[str] = Field(None, description="Specific plugin for plugin backup")


class TaskRequest(BaseModel):
    """Scheduled task request"""
    task_name: str = Field(..., description="Name of the task to execute")


def get_backup_manager() -> BackupManager:
    """Get backup manager instance"""
    return BackupManager()


def get_prune_manager() -> PruneManager:
    """Get prune manager instance"""
    return PruneManager()


def get_auto_pruner() -> AutoPruner:
    """Get auto-pruner instance"""
    return AutoPruner()


def get_scheduler() -> ArchieScheduler:
    """Get scheduler instance"""
    return ArchieScheduler()


def get_auth_manager() -> AuthManager:
    """Get auth manager instance"""
    return AuthManager()


def get_personality() -> ArchiePersonality:
    """Get personality instance"""
    return ArchiePersonality()


@router.get("/status", response_model=SystemResponse)
async def get_system_status(
    token_name: str = Depends(require_auth("read")),
    personality: ArchiePersonality = Depends(get_personality)
):
    """Get comprehensive system status"""
    try:
        # Collect system information
        status = {
            "timestamp": datetime.now().isoformat(),
            "archie_version": "2.0.0",
            "authenticated_as": token_name,
            "services": {
                "backup_manager": "active",
                "prune_manager": "active", 
                "scheduler": "active",
                "auth_manager": "active"
            }
        }
        
        return SystemResponse(
            success=True,
            message="System status retrieved",
            data=status,
            archie_says="All systems operational! The memory vault is secure and running smoothly."
        )
        
    except Exception as e:
        return SystemResponse(
            success=False,
            message=f"Failed to get system status: {str(e)}",
            archie_says=personality.format_response("error")
        )


@router.post("/backup", response_model=SystemResponse)
async def create_backup(
    backup_req: BackupRequest,
    backup_mgr: BackupManager = Depends(get_backup_manager),
    personality: ArchiePersonality = Depends(get_personality),
    token_name: str = Depends(require_auth("write"))
):
    """Create a system backup"""
    try:
        if backup_req.backup_type == "memory":
            result = backup_mgr.backup_memory_database()
        elif backup_req.backup_type == "plugins":
            result = backup_mgr.backup_plugin_data(backup_req.plugin_name)
        elif backup_req.backup_type == "full":
            result = backup_mgr.create_full_backup()
        else:
            raise HTTPException(status_code=400, detail="Invalid backup type")
        
        if result.get("success"):
            archie_comment = f"Excellent! I've created a {backup_req.backup_type} backup. Your memories are now doubly secure!"
        else:
            archie_comment = "Oh dear! The backup process encountered some difficulties."
        
        return SystemResponse(
            success=result.get("success", False),
            message=f"{backup_req.backup_type.title()} backup completed",
            data=result,
            archie_says=archie_comment
        )
        
    except Exception as e:
        return SystemResponse(
            success=False,
            message=f"Backup failed: {str(e)}",
            archie_says=personality.format_response("error")
        )


@router.post("/restore", response_model=SystemResponse)
async def restore_backup(
    backup_file: str = Query(..., description="Path to backup file"),
    backup_mgr: BackupManager = Depends(get_backup_manager),
    personality: ArchiePersonality = Depends(get_personality),
    token_name: str = Depends(require_auth("write"))
):
    """Restore from a backup file"""
    try:
        result = backup_mgr.restore_from_backup(backup_file)
        
        if result.get("success"):
            archie_comment = f"Restoration complete! I've carefully restored your memories from the backup."
        else:
            archie_comment = "The restoration process hit a snag. The backup file might be corrupted."
        
        return SystemResponse(
            success=result.get("success", False),
            message="Restore operation completed",
            data=result,
            archie_says=archie_comment
        )
        
    except Exception as e:
        return SystemResponse(
            success=False,
            message=f"Restore failed: {str(e)}",
            archie_says=personality.format_response("error")
        )


@router.post("/prune", response_model=SystemResponse)
async def run_pruning_cycle(
    prune_mgr: PruneManager = Depends(get_prune_manager),
    personality: ArchiePersonality = Depends(get_personality),
    token_name: str = Depends(require_auth("write"))
):
    """Run a complete pruning cycle"""
    try:
        result = prune_mgr.run_pruning_cycle()
        
        files_moved = result.get("files_moved", 0)
        files_compressed = result.get("files_compressed", 0)
        space_freed = result.get("space_freed_mb", 0)
        
        archie_comment = (f"Splendid tidying session! I've moved {files_moved} files, "
                         f"compressed {files_compressed} for efficiency, and freed up "
                         f"{space_freed:.1f}MB of space. The archives are now even more organized!")
        
        return SystemResponse(
            success=True,
            message="Pruning cycle completed",
            data=result,
            archie_says=archie_comment
        )
        
    except Exception as e:
        return SystemResponse(
            success=False,
            message=f"Pruning failed: {str(e)}",
            archie_says=personality.format_response("error")
        )


@router.get("/prune/candidates", response_model=SystemResponse)
async def get_archive_candidates(
    prune_mgr: PruneManager = Depends(get_prune_manager),
    personality: ArchiePersonality = Depends(get_personality),
    token_name: str = Depends(require_auth("read"))
):
    """Get files that are candidates for archival"""
    try:
        candidates = prune_mgr.identify_archive_candidates()
        
        candidate_count = len(candidates)
        total_size = sum(c.get("size_mb", 0) for c in candidates)
        
        if candidate_count > 0:
            archie_comment = (f"I've found {candidate_count} files that might be ready for archival, "
                             f"totaling {total_size:.1f}MB. Shall I help you review them?")
        else:
            archie_comment = "Excellent! No files need archiving at the moment. Everything is optimally organized."
        
        return SystemResponse(
            success=True,
            message=f"Found {candidate_count} archive candidates",
            data={"candidates": candidates, "total_size_mb": total_size},
            archie_says=archie_comment
        )
        
    except Exception as e:
        return SystemResponse(
            success=False,
            message=f"Analysis failed: {str(e)}",
            archie_says=personality.format_response("error")
        )


@router.post("/auto-prune/run", response_model=SystemResponse)
async def run_auto_prune(
    auto_pruner: AutoPruner = Depends(get_auto_pruner),
    personality: ArchiePersonality = Depends(get_personality),
    token_name: str = Depends(require_auth("write"))
):
    """Run the automatic pruning and storage tier management"""
    try:
        prune_result = auto_pruner.run_auto_prune()
        
        if prune_result["success"]:
            actions = prune_result["actions"]
            total_moved = actions.get("uploads_to_cold", {}).get("moved_count", 0)
            total_cleaned = (actions.get("temp_cleanup", {}).get("cleaned_count", 0) + 
                           actions.get("thumbnail_cleanup", {}).get("cleaned_count", 0))
            
            archie_comment = f"Auto-pruning complete! I've optimized the storage by moving {total_moved} files to cold storage and cleaned up {total_cleaned} temporary files. Everything is perfectly organized!"
        else:
            archie_comment = "I encountered some issues during auto-pruning. Let me review what needs attention."
        
        return SystemResponse(
            success=prune_result["success"],
            message="Auto-pruning completed" if prune_result["success"] else "Auto-pruning had issues",
            data=prune_result,
            archie_says=archie_comment
        )
        
    except Exception as e:
        return SystemResponse(
            success=False,
            message=f"Auto-pruning failed: {str(e)}",
            archie_says=personality.format_response("error")
        )


@router.get("/auto-prune/stats", response_model=SystemResponse)
async def get_auto_prune_stats(
    auto_pruner: AutoPruner = Depends(get_auto_pruner),
    personality: ArchiePersonality = Depends(get_personality),
    token_name: str = Depends(require_auth("read"))
):
    """Get statistics about files eligible for auto-pruning"""
    try:
        stats = auto_pruner.get_pruning_stats()
        
        eligible_files = (stats["uploads_eligible_for_cold"] + 
                         stats["temp_files_to_cleanup"] + 
                         stats["old_thumbnails"])
        
        if eligible_files > 0:
            archie_comment = f"I found {eligible_files} files that could benefit from optimization: {stats['uploads_eligible_for_cold']} ready for cold storage, {stats['temp_files_to_cleanup']} temporary files to clean, and {stats['old_thumbnails']} old thumbnails."
        else:
            archie_comment = f"Excellent! All {stats['total_files_tracked']} tracked files are perfectly optimized. No pruning needed!"
        
        return SystemResponse(
            success=True,
            message="Auto-pruning statistics retrieved",
            data=stats,
            archie_says=archie_comment
        )
        
    except Exception as e:
        return SystemResponse(
            success=False,
            message=f"Failed to get pruning stats: {str(e)}",
            archie_says=personality.format_response("error")
        )


@router.get("/schedule/status", response_model=SystemResponse)
async def get_schedule_status(
    scheduler: ArchieScheduler = Depends(get_scheduler),
    personality: ArchiePersonality = Depends(get_personality),
    token_name: str = Depends(require_auth("read"))
):
    """Get scheduler status and upcoming tasks"""
    try:
        status = scheduler.get_schedule_status()
        
        jobs_count = status.get("total_jobs", 0)
        recent_tasks = len(status.get("recent_tasks", []))
        
        archie_comment = (f"The automation system is humming along nicely! "
                         f"{jobs_count} scheduled tasks are ready, and I've completed "
                         f"{recent_tasks} tasks recently.")
        
        return SystemResponse(
            success=True,
            message="Schedule status retrieved",
            data=status,
            archie_says=archie_comment
        )
        
    except Exception as e:
        return SystemResponse(
            success=False,
            message=f"Failed to get schedule status: {str(e)}",
            archie_says=personality.format_response("error")
        )


@router.get("/schedule/stats", response_model=SystemResponse)
async def get_task_statistics(
    scheduler: ArchieScheduler = Depends(get_scheduler),
    personality: ArchiePersonality = Depends(get_personality),
    token_name: str = Depends(require_auth("read"))
):
    """Get task execution statistics"""
    try:
        stats = scheduler.get_task_statistics()
        
        success_rate = stats.get("success_rate", 0)
        total_executions = stats.get("total_executions", 0)
        
        if success_rate >= 95:
            archie_comment = f"Outstanding! {success_rate}% success rate across {total_executions} task executions. I'm quite proud of this reliability!"
        elif success_rate >= 80:
            archie_comment = f"Good performance with {success_rate}% success rate. There's always room for improvement!"
        else:
            archie_comment = f"The {success_rate}% success rate suggests we need some maintenance attention."
        
        return SystemResponse(
            success=True,
            message="Task statistics retrieved",
            data=stats,
            archie_says=archie_comment
        )
        
    except Exception as e:
        return SystemResponse(
            success=False,
            message=f"Failed to get statistics: {str(e)}",
            archie_says=personality.format_response("error")
        )


@router.post("/schedule/run", response_model=SystemResponse)
async def run_scheduled_task(
    task_req: TaskRequest,
    scheduler: ArchieScheduler = Depends(get_scheduler),
    personality: ArchiePersonality = Depends(get_personality),
    token_name: str = Depends(require_auth("write"))
):
    """Manually run a scheduled task"""
    try:
        result = scheduler.force_run_task(task_req.task_name)
        
        if result.get("success"):
            duration = result.get("duration_seconds", 0)
            archie_comment = f"Task '{task_req.task_name}' executed successfully in {duration:.1f} seconds. Manual intervention complete!"
        else:
            error = result.get("error", "Unknown error")
            archie_comment = f"The {task_req.task_name} task encountered difficulties: {error}"
        
        return SystemResponse(
            success=result.get("success", False),
            message=f"Task {task_req.task_name} execution completed",
            data=result,
            archie_says=archie_comment
        )
        
    except Exception as e:
        return SystemResponse(
            success=False,
            message=f"Task execution failed: {str(e)}",
            archie_says=personality.format_response("error")
        )


@router.get("/auth/tokens", response_model=SystemResponse)
async def list_auth_tokens(
    auth_mgr: AuthManager = Depends(get_auth_manager),
    personality: ArchiePersonality = Depends(get_personality),
    token_name: str = Depends(require_auth("read"))
):
    """List all authentication tokens (without exposing actual tokens)"""
    try:
        tokens = auth_mgr.list_tokens()
        stats = auth_mgr.get_auth_stats()
        
        active_count = stats.get("active_tokens", 0)
        
        archie_comment = f"I'm managing {active_count} active authentication tokens. Security is paramount!"
        
        return SystemResponse(
            success=True,
            message="Authentication tokens listed",
            data={"tokens": tokens, "stats": stats},
            archie_says=archie_comment
        )
        
    except Exception as e:
        return SystemResponse(
            success=False,
            message=f"Failed to list tokens: {str(e)}",
            archie_says=personality.format_response("error")
        )


@router.get("/storage/analysis", response_model=SystemResponse)
async def get_storage_analysis(
    prune_mgr: PruneManager = Depends(get_prune_manager),
    personality: ArchiePersonality = Depends(get_personality),
    token_name: str = Depends(require_auth("read"))
):
    """Get detailed storage analysis and recommendations"""
    try:
        analysis = prune_mgr.get_storage_analysis()
        
        recommendations = analysis.get("recommendations", [])
        tiers = analysis.get("tiers", {})
        
        if recommendations:
            archie_comment = f"I've analyzed the storage tiers and have {len(recommendations)} recommendations for optimization."
        else:
            archie_comment = "Excellent! The storage system is optimally organized with no immediate recommendations."
        
        return SystemResponse(
            success=True,
            message="Storage analysis completed",
            data=analysis,
            archie_says=archie_comment
        )
        
    except Exception as e:
        return SystemResponse(
            success=False,
            message=f"Storage analysis failed: {str(e)}",
            archie_says=personality.format_response("error")
        )