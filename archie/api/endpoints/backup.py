"""
ArchieOS Backup API Endpoints
Memory and state backup management
"""
from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field

from archie_core.memory_backup_system import MemoryBackupSystem
from archie_core.personality import ArchiePersonality
from api.endpoints.auth import require_auth


router = APIRouter(prefix="/backup", tags=["backup"])


class BackupResponse(BaseModel):
    """Standard backup response"""
    success: bool
    message: str
    data: Optional[dict] = None
    archie_says: Optional[str] = None


class BackupInfo(BaseModel):
    """Backup information model"""
    backup_date: str
    timestamp: str
    success: bool
    components: List[str]
    manifest_path: str


def get_backup_system() -> MemoryBackupSystem:
    """Dependency to get backup system instance"""
    return MemoryBackupSystem()


def get_personality() -> ArchiePersonality:
    """Dependency to get personality instance"""
    return ArchiePersonality()


@router.post("/create", response_model=BackupResponse)
async def create_backup(
    backup_date: Optional[str] = Query(None, description="Backup date (YYYY-MM-DD), defaults to today"),
    backup_system: MemoryBackupSystem = Depends(get_backup_system),
    personality: ArchiePersonality = Depends(get_personality),
    token_name: str = Depends(require_auth("write"))
):
    """Create a comprehensive daily backup"""
    try:
        # Parse backup date if provided
        target_date = None
        if backup_date:
            try:
                target_date = datetime.strptime(backup_date, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        
        # Create backup
        backup_result = backup_system.create_daily_backup(target_date)
        
        if backup_result["success"]:
            components = list(backup_result["components"].keys())
            archie_comment = f"Splendid! I've created a comprehensive backup covering {', '.join(components)}. All your digital memories are safely preserved!"
            
            return BackupResponse(
                success=True,
                message=f"Backup created successfully for {backup_result['backup_date']}",
                data=backup_result,
                archie_says=archie_comment
            )
        else:
            archie_comment = "Oh dear! I encountered some issues creating the backup. Let me review what went wrong."
            
            return BackupResponse(
                success=False,
                message="Backup creation failed",
                data=backup_result,
                archie_says=archie_comment
            )
        
    except HTTPException:
        raise
    except Exception as e:
        return BackupResponse(
            success=False,
            message=f"Backup creation failed: {str(e)}",
            archie_says=personality.format_response("error")
        )


@router.get("/list", response_model=BackupResponse)
async def list_backups(
    backup_system: MemoryBackupSystem = Depends(get_backup_system),
    personality: ArchiePersonality = Depends(get_personality),
    token_name: str = Depends(require_auth("read"))
):
    """List all available backups"""
    try:
        backups = backup_system.list_available_backups()
        
        archie_comment = f"I have {len(backups)} backup archives in my memory vaults, all perfectly organized and ready for restoration if needed!"
        
        return BackupResponse(
            success=True,
            message=f"Found {len(backups)} backup archives",
            data={"backups": backups, "total": len(backups)},
            archie_says=archie_comment
        )
        
    except Exception as e:
        return BackupResponse(
            success=False,
            message=f"Failed to list backups: {str(e)}",
            archie_says=personality.format_response("error")
        )


@router.post("/restore", response_model=BackupResponse)
async def restore_backup(
    backup_date: str = Query(..., description="Backup date to restore (YYYY-MM-DD)"),
    backup_system: MemoryBackupSystem = Depends(get_backup_system),
    personality: ArchiePersonality = Depends(get_personality),
    token_name: str = Depends(require_auth("write"))
):
    """Restore system from a specific backup"""
    try:
        # Parse backup date
        try:
            target_date = datetime.strptime(backup_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        
        # Perform restoration
        restore_result = backup_system.restore_from_backup(target_date)
        
        if restore_result["success"]:
            components = restore_result.get("restored_components", [])
            archie_comment = f"Excellent! I've successfully restored your system from the {backup_date} backup. Components restored: {', '.join(components)}. Everything is back to its proper place!"
            
            return BackupResponse(
                success=True,
                message=f"System restored from backup {backup_date}",
                data=restore_result,
                archie_says=archie_comment
            )
        else:
            archie_comment = f"I'm afraid I couldn't restore from the {backup_date} backup. {restore_result.get('message', 'Unknown error occurred.')}"
            
            return BackupResponse(
                success=False,
                message=restore_result.get("message", "Restore failed"),
                data=restore_result,
                archie_says=archie_comment
            )
        
    except HTTPException:
        raise
    except Exception as e:
        return BackupResponse(
            success=False,
            message=f"Restoration failed: {str(e)}",
            archie_says=personality.format_response("error")
        )


@router.delete("/cleanup", response_model=BackupResponse)
async def cleanup_old_backups(
    keep_days: int = Query(30, ge=1, le=365, description="Number of days to keep backups"),
    backup_system: MemoryBackupSystem = Depends(get_backup_system),
    personality: ArchiePersonality = Depends(get_personality),
    token_name: str = Depends(require_auth("delete"))
):
    """Clean up old backup files"""
    try:
        cleanup_result = backup_system.cleanup_old_backups(keep_days)
        
        if cleanup_result["success"]:
            cleaned_count = cleanup_result["cleaned_count"]
            if cleaned_count > 0:
                archie_comment = f"Tidy-up complete! I've cleared out {cleaned_count} old backup files while keeping the recent {keep_days} days of backups. The archive is now perfectly organized!"
            else:
                archie_comment = f"The backup archives are already perfectly clean! All backups within the last {keep_days} days are preserved."
            
            return BackupResponse(
                success=True,
                message=cleanup_result["message"],
                data=cleanup_result,
                archie_says=archie_comment
            )
        else:
            return BackupResponse(
                success=False,
                message=cleanup_result["message"],
                data=cleanup_result,
                archie_says="I encountered some difficulty cleaning up the old backups."
            )
        
    except Exception as e:
        return BackupResponse(
            success=False,
            message=f"Cleanup failed: {str(e)}",
            archie_says=personality.format_response("error")
        )


@router.get("/status", response_model=BackupResponse)
async def backup_status(
    backup_system: MemoryBackupSystem = Depends(get_backup_system),
    personality: ArchiePersonality = Depends(get_personality),
    token_name: str = Depends(require_auth("read"))
):
    """Get backup system status and recent backup information"""
    try:
        # Get recent backups
        backups = backup_system.list_available_backups()
        
        # Find today's backup
        today = date.today().isoformat()
        today_backup = next((b for b in backups if b["backup_date"] == today), None)
        
        # Get latest backup
        latest_backup = backups[0] if backups else None
        
        status_data = {
            "total_backups": len(backups),
            "latest_backup": latest_backup,
            "today_backup_exists": today_backup is not None,
            "today_backup": today_backup,
            "backup_system_active": True
        }
        
        if today_backup:
            archie_comment = f"All systems running smoothly! Today's backup is safely stored, and I have {len(backups)} total backup archives in the vaults."
        elif latest_backup:
            latest_date = latest_backup["backup_date"]
            archie_comment = f"The backup system is operational. The most recent backup is from {latest_date}. I have {len(backups)} backup archives total."
        else:
            archie_comment = "The backup system is ready, but no backups have been created yet. Shall I create the first one?"
        
        return BackupResponse(
            success=True,
            message="Backup status retrieved",
            data=status_data,
            archie_says=archie_comment
        )
        
    except Exception as e:
        return BackupResponse(
            success=False,
            message=f"Failed to get backup status: {str(e)}",
            archie_says=personality.format_response("error")
        )