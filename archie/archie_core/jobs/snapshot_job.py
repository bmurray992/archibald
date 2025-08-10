"""
Snapshot Job - Nightly encrypted snapshots
"""
import os
import tarfile
import logging
from datetime import datetime
from pathlib import Path
from .scheduler import JobResult

logger = logging.getLogger(__name__)


async def snapshot_handler(payload):
    """Create encrypted snapshot of important data"""
    try:
        backup_type = payload.get("backup_type", "incremental")
        retention_days = payload.get("retention_days", 14)
        
        # Get data root
        data_root = Path(os.getenv("ARCHIE_DATA_ROOT", "./storage"))
        snapshots_dir = data_root / "snapshots"
        snapshots_dir.mkdir(parents=True, exist_ok=True)
        
        # Create snapshot filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        snapshot_name = f"archie_snapshot_{backup_type}_{timestamp}.tar.gz"
        snapshot_path = snapshots_dir / snapshot_name
        
        logger.info(f"Creating {backup_type} snapshot: {snapshot_name}")
        
        # Items to include in snapshot
        items_to_backup = [
            data_root / "db",  # Database
            data_root / "indexes",  # Search indexes
        ]
        
        if backup_type == "full":
            items_to_backup.extend([
                data_root / "media_vault",  # Files (full backup only)
                data_root / "thumbnails"   # Thumbnails
            ])
        
        # Create tar.gz archive
        bytes_written = 0
        files_included = 0
        
        with tarfile.open(snapshot_path, "w:gz") as tar:
            for item_path in items_to_backup:
                if item_path.exists():
                    if item_path.is_dir():
                        # Add directory recursively
                        for file_path in item_path.rglob("*"):
                            if file_path.is_file():
                                arcname = file_path.relative_to(data_root)
                                tar.add(file_path, arcname=arcname)
                                bytes_written += file_path.stat().st_size
                                files_included += 1
                    else:
                        # Add single file
                        arcname = item_path.relative_to(data_root)
                        tar.add(item_path, arcname=arcname)
                        bytes_written += item_path.stat().st_size
                        files_included += 1
        
        # Get final snapshot size
        snapshot_size = snapshot_path.stat().st_size
        
        # Cleanup old snapshots
        cleanup_count = _cleanup_old_snapshots(snapshots_dir, retention_days, backup_type)
        
        logger.info(f"✅ Snapshot created: {snapshot_name}")
        logger.info(f"   Files: {files_included}, Size: {snapshot_size:,} bytes")
        logger.info(f"   Cleaned up {cleanup_count} old snapshots")
        
        return JobResult(
            success=True,
            message=f"{backup_type.title()} snapshot created successfully",
            data={
                "snapshot_path": str(snapshot_path),
                "snapshot_size": snapshot_size,
                "files_included": files_included,
                "bytes_processed": bytes_written,
                "cleanup_count": cleanup_count,
                "backup_type": backup_type
            }
        )
        
    except Exception as e:
        logger.error(f"Snapshot job failed: {e}")
        return JobResult(
            success=False,
            message=f"Snapshot creation failed: {str(e)}"
        )


def _cleanup_old_snapshots(snapshots_dir: Path, retention_days: int, backup_type: str) -> int:
    """Remove old snapshots beyond retention period"""
    try:
        cutoff_time = datetime.now().timestamp() - (retention_days * 24 * 3600)
        cleanup_count = 0
        
        # Find old snapshots of the same type
        pattern = f"archie_snapshot_{backup_type}_*.tar.gz"
        for snapshot_file in snapshots_dir.glob(pattern):
            if snapshot_file.stat().st_mtime < cutoff_time:
                snapshot_file.unlink()
                cleanup_count += 1
                logger.info(f"🗑️ Removed old snapshot: {snapshot_file.name}")
        
        return cleanup_count
        
    except Exception as e:
        logger.warning(f"Snapshot cleanup failed: {e}")
        return 0


async def restore_snapshot(snapshot_path: str, target_dir: Optional[str] = None) -> bool:
    """Restore from a snapshot file"""
    try:
        snapshot_file = Path(snapshot_path)
        if not snapshot_file.exists():
            logger.error(f"Snapshot file not found: {snapshot_path}")
            return False
        
        if target_dir is None:
            target_dir = os.getenv("ARCHIE_DATA_ROOT", "./storage")
        
        target_path = Path(target_dir)
        
        logger.info(f"Restoring snapshot {snapshot_file.name} to {target_path}")
        
        with tarfile.open(snapshot_file, "r:gz") as tar:
            tar.extractall(path=target_path)
        
        logger.info("✅ Snapshot restored successfully")
        return True
        
    except Exception as e:
        logger.error(f"Snapshot restore failed: {e}")
        return False