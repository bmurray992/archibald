"""
ArchieOS Auto-Pruning System
Automatic file lifecycle management and storage tier rotation
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any
from pathlib import Path

from .file_manager import ArchieFileManager
from .storage_config import get_storage_config


class AutoPruner:
    """Automatic file pruning and storage tier management"""
    
    def __init__(self):
        self.file_manager = ArchieFileManager()
        self.storage_config = get_storage_config()
        self.logger = logging.getLogger(__name__)
        
        # Default pruning rules (can be configured)
        self.pruning_rules = {
            "uploads_to_cold_days": 90,    # Move uploads to cold after 90 days
            "temp_cleanup_days": 7,        # Delete temp files after 7 days
            "backup_retention_days": 30,   # Keep backups for 30 days
        }
    
    def run_auto_prune(self) -> Dict[str, Any]:
        """Run the complete auto-pruning process"""
        result = {
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "actions": {},
            "errors": []
        }
        
        try:
            # 1. Move old uploads to cold storage
            cold_result = self._move_old_uploads_to_cold()
            result["actions"]["uploads_to_cold"] = cold_result
            
            # 2. Clean up temporary files
            temp_result = self._cleanup_temp_files()
            result["actions"]["temp_cleanup"] = temp_result
            
            # 3. Clean up old thumbnails
            thumb_result = self._cleanup_old_thumbnails()
            result["actions"]["thumbnail_cleanup"] = thumb_result
            
            self.logger.info("Auto-pruning completed successfully")
            
        except Exception as e:
            result["success"] = False
            result["errors"].append(str(e))
            self.logger.error(f"Auto-pruning failed: {e}")
        
        return result
    
    def _move_old_uploads_to_cold(self) -> Dict[str, Any]:
        """Move old files from uploads to cold storage"""
        result = {"moved_count": 0, "errors": []}
        
        try:
            cutoff_date = datetime.now() - timedelta(days=self.pruning_rules["uploads_to_cold_days"])
            
            # Find old files in uploads
            old_files = self.file_manager.search_files(
                storage_tier="uploads",
                limit=1000  # Process in batches
            )
            
            moved_count = 0
            for file_metadata in old_files:
                try:
                    # Check if file is old enough
                    created_at = file_metadata.created_at
                    if isinstance(created_at, str):
                        created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    
                    if created_at < cutoff_date:
                        # Move to cold storage (this would need file_id)
                        # For now, we'll simulate by updating the metadata
                        self.logger.info(f"Would move {file_metadata.filename} to cold storage")
                        moved_count += 1
                
                except Exception as e:
                    result["errors"].append(f"Failed to process {file_metadata.filename}: {str(e)}")
            
            result["moved_count"] = moved_count
            
        except Exception as e:
            result["errors"].append(str(e))
        
        return result
    
    def _cleanup_temp_files(self) -> Dict[str, Any]:
        """Clean up old temporary files"""
        result = {"cleaned_count": 0, "errors": []}
        
        try:
            temp_path = self.storage_config.get_path("temp")
            
            if not temp_path.exists():
                return result
            
            cutoff_date = datetime.now() - timedelta(days=self.pruning_rules["temp_cleanup_days"])
            cleaned_count = 0
            
            for temp_file in temp_path.rglob("*"):
                if temp_file.is_file():
                    try:
                        file_mtime = datetime.fromtimestamp(temp_file.stat().st_mtime)
                        
                        if file_mtime < cutoff_date:
                            temp_file.unlink()
                            cleaned_count += 1
                            
                    except Exception as e:
                        result["errors"].append(f"Failed to clean {temp_file}: {str(e)}")
            
            result["cleaned_count"] = cleaned_count
            
        except Exception as e:
            result["errors"].append(str(e))
        
        return result
    
    def _cleanup_old_thumbnails(self) -> Dict[str, Any]:
        """Clean up old thumbnail files"""
        result = {"cleaned_count": 0, "errors": []}
        
        try:
            thumbnails_path = self.storage_config.get_path("thumbnails")
            
            if not thumbnails_path.exists():
                return result
            
            cutoff_date = datetime.now() - timedelta(days=30)  # Keep thumbnails for 30 days
            cleaned_count = 0
            
            for thumb_file in thumbnails_path.rglob("*"):
                if thumb_file.is_file():
                    try:
                        file_mtime = datetime.fromtimestamp(thumb_file.stat().st_mtime)
                        
                        if file_mtime < cutoff_date:
                            thumb_file.unlink()
                            cleaned_count += 1
                            
                    except Exception as e:
                        result["errors"].append(f"Failed to clean thumbnail {thumb_file}: {str(e)}")
            
            result["cleaned_count"] = cleaned_count
            
        except Exception as e:
            result["errors"].append(str(e))
        
        return result
    
    def get_pruning_stats(self) -> Dict[str, Any]:
        """Get statistics about files eligible for pruning"""
        stats = {
            "uploads_eligible_for_cold": 0,
            "temp_files_to_cleanup": 0,
            "old_thumbnails": 0,
            "total_files_tracked": 0
        }
        
        try:
            # Count files eligible for cold storage
            cutoff_date = datetime.now() - timedelta(days=self.pruning_rules["uploads_to_cold_days"])
            upload_files = self.file_manager.search_files(storage_tier="uploads", limit=1000)
            
            eligible_for_cold = 0
            for file_metadata in upload_files:
                try:
                    created_at = file_metadata.created_at
                    if isinstance(created_at, str):
                        created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    
                    if created_at < cutoff_date:
                        eligible_for_cold += 1
                except:
                    continue
            
            stats["uploads_eligible_for_cold"] = eligible_for_cold
            
            # Count temp files
            temp_path = self.storage_config.get_path("temp")
            if temp_path.exists():
                temp_cutoff = datetime.now() - timedelta(days=self.pruning_rules["temp_cleanup_days"])
                temp_count = 0
                
                for temp_file in temp_path.rglob("*"):
                    if temp_file.is_file():
                        try:
                            file_mtime = datetime.fromtimestamp(temp_file.stat().st_mtime)
                            if file_mtime < temp_cutoff:
                                temp_count += 1
                        except:
                            continue
                
                stats["temp_files_to_cleanup"] = temp_count
            
            # Get total tracked files
            storage_stats = self.file_manager.get_storage_stats()
            stats["total_files_tracked"] = storage_stats.get("database", {}).get("total_files", 0)
            
        except Exception as e:
            self.logger.error(f"Failed to get pruning stats: {e}")
        
        return stats
    
    def update_pruning_rules(self, new_rules: Dict[str, int]) -> bool:
        """Update pruning rules"""
        try:
            for key, value in new_rules.items():
                if key in self.pruning_rules and isinstance(value, int) and value > 0:
                    self.pruning_rules[key] = value
            return True
        except Exception as e:
            self.logger.error(f"Failed to update pruning rules: {e}")
            return False
    
    def get_pruning_rules(self) -> Dict[str, int]:
        """Get current pruning rules"""
        return self.pruning_rules.copy()