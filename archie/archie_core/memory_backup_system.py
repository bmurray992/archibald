"""
ArchieOS Memory Backup System
Automated daily backup of plugin states, memory data, and system configurations
"""
import json
import sqlite3
import shutil
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Any, Optional
import logging

from .storage_config import get_storage_config
from .memory_manager import MemoryManager


class MemoryBackupSystem:
    """Comprehensive memory and state backup system"""
    
    def __init__(self):
        self.storage_config = get_storage_config()
        self.logger = logging.getLogger(__name__)
        
        # Ensure backup directories exist
        self.memory_backup_path = self.storage_config.get_path("memory")
        self.plugin_backup_path = self.storage_config.get_path("plugins")
        
    def create_daily_backup(self, backup_date: Optional[date] = None) -> Dict[str, Any]:
        """Create a comprehensive daily backup"""
        if backup_date is None:
            backup_date = date.today()
            
        backup_info = {
            "backup_date": backup_date.isoformat(),
            "timestamp": datetime.now().isoformat(),
            "components": {},
            "success": True,
            "errors": []
        }
        
        try:
            # 1. Backup memory database
            memory_result = self._backup_memory_database(backup_date)
            backup_info["components"]["memory"] = memory_result
            
            # 2. Backup plugin states
            plugin_result = self._backup_plugin_states(backup_date)
            backup_info["components"]["plugins"] = plugin_result
            
            # 3. Backup file metadata
            file_result = self._backup_file_metadata(backup_date)
            backup_info["components"]["files"] = file_result
            
            # 4. Backup system configuration
            config_result = self._backup_system_config(backup_date)
            backup_info["components"]["config"] = config_result
            
            # 5. Create backup manifest
            self._create_backup_manifest(backup_date, backup_info)
            
            self.logger.info(f"Daily backup completed successfully for {backup_date}")
            
        except Exception as e:
            backup_info["success"] = False
            backup_info["errors"].append(str(e))
            self.logger.error(f"Daily backup failed: {e}")
            
        return backup_info
    
    def _backup_memory_database(self, backup_date: date) -> Dict[str, Any]:
        """Backup the memory database"""
        result = {"success": False, "file_count": 0, "size_bytes": 0}
        
        try:
            memory_db_path = self.storage_config.project_root / "database" / "memory.db"
            if not memory_db_path.exists():
                result["message"] = "Memory database not found"
                return result
            
            # Create backup filename
            backup_filename = f"memory_backup_{backup_date.strftime('%Y%m%d')}.db"
            backup_path = self.memory_backup_path / backup_filename
            
            # Copy database file
            shutil.copy2(memory_db_path, backup_path)
            
            result["success"] = True
            result["file_count"] = 1
            result["size_bytes"] = backup_path.stat().st_size
            result["backup_path"] = str(backup_path)
            result["message"] = f"Memory database backed up to {backup_filename}"
            
        except Exception as e:
            result["message"] = f"Memory backup failed: {str(e)}"
            
        return result
    
    def _backup_plugin_states(self, backup_date: date) -> Dict[str, Any]:
        """Backup all plugin states and data"""
        result = {"success": False, "plugins_backed_up": 0, "total_files": 0, "size_bytes": 0}
        plugin_results = {}
        
        try:
            # Get all plugin directories
            plugin_base = self.storage_config.get_path("plugins")
            
            if not plugin_base.exists():
                result["message"] = "Plugin directory not found"
                return result
            
            total_files = 0
            total_size = 0
            
            for plugin_dir in plugin_base.iterdir():
                if plugin_dir.is_dir():
                    plugin_name = plugin_dir.name
                    plugin_result = self._backup_single_plugin(plugin_name, backup_date)
                    plugin_results[plugin_name] = plugin_result
                    
                    if plugin_result["success"]:
                        total_files += plugin_result["file_count"]
                        total_size += plugin_result["size_bytes"]
            
            result["success"] = True
            result["plugins_backed_up"] = len([p for p in plugin_results.values() if p["success"]])
            result["total_files"] = total_files
            result["size_bytes"] = total_size
            result["plugin_details"] = plugin_results
            result["message"] = f"Backed up {result['plugins_backed_up']} plugins"
            
        except Exception as e:
            result["message"] = f"Plugin backup failed: {str(e)}"
            
        return result
    
    def _backup_single_plugin(self, plugin_name: str, backup_date: date) -> Dict[str, Any]:
        """Backup a single plugin's data"""
        result = {"success": False, "file_count": 0, "size_bytes": 0}
        
        try:
            plugin_data_path = self.storage_config.get_plugin_path(plugin_name, "data")
            plugin_backup_path = self.storage_config.get_plugin_path(plugin_name, "backups")
            
            if not plugin_data_path.exists():
                result["message"] = f"No data found for plugin {plugin_name}"
                result["success"] = True  # Not an error
                return result
            
            # Create backup archive name
            backup_filename = f"{plugin_name}_backup_{backup_date.strftime('%Y%m%d')}.json"
            backup_file_path = plugin_backup_path / backup_filename
            
            # Collect all plugin data
            plugin_data = {
                "plugin_name": plugin_name,
                "backup_date": backup_date.isoformat(),
                "timestamp": datetime.now().isoformat(),
                "data": {}
            }
            
            # Archive all JSON files in the plugin data directory
            json_files = list(plugin_data_path.glob("*.json"))
            for json_file in json_files:
                try:
                    with open(json_file, 'r') as f:
                        plugin_data["data"][json_file.name] = json.load(f)
                except json.JSONDecodeError:
                    self.logger.warning(f"Could not read JSON file: {json_file}")
            
            # Save backup
            with open(backup_file_path, 'w') as f:
                json.dump(plugin_data, f, indent=2, default=str)
            
            result["success"] = True
            result["file_count"] = len(json_files)
            result["size_bytes"] = backup_file_path.stat().st_size
            result["backup_path"] = str(backup_file_path)
            result["message"] = f"Plugin {plugin_name} backed up successfully"
            
        except Exception as e:
            result["message"] = f"Plugin {plugin_name} backup failed: {str(e)}"
            
        return result
    
    def _backup_file_metadata(self, backup_date: date) -> Dict[str, Any]:
        """Backup file metadata database"""
        result = {"success": False, "file_count": 0, "size_bytes": 0}
        
        try:
            file_db_path = self.storage_config.get_path("indexes", "files.db")
            
            if not file_db_path.exists():
                result["message"] = "File metadata database not found"
                result["success"] = True  # Not an error for new systems
                return result
            
            # Create backup filename
            backup_filename = f"files_metadata_backup_{backup_date.strftime('%Y%m%d')}.db"
            backup_path = self.memory_backup_path / backup_filename
            
            # Copy database file
            shutil.copy2(file_db_path, backup_path)
            
            result["success"] = True
            result["file_count"] = 1
            result["size_bytes"] = backup_path.stat().st_size
            result["backup_path"] = str(backup_path)
            result["message"] = f"File metadata backed up to {backup_filename}"
            
        except Exception as e:
            result["message"] = f"File metadata backup failed: {str(e)}"
            
        return result
    
    def _backup_system_config(self, backup_date: date) -> Dict[str, Any]:
        """Backup system configuration files"""
        result = {"success": False, "file_count": 0, "size_bytes": 0}
        
        try:
            config_dir = self.storage_config.project_root / "config"
            
            if not config_dir.exists():
                result["message"] = "Config directory not found"
                result["success"] = True
                return result
            
            # Create config backup
            backup_filename = f"config_backup_{backup_date.strftime('%Y%m%d')}.json"
            backup_path = self.memory_backup_path / backup_filename
            
            config_data = {
                "backup_date": backup_date.isoformat(),
                "timestamp": datetime.now().isoformat(),
                "configs": {}
            }
            
            # Backup JSON config files
            config_files = list(config_dir.glob("*.json"))
            for config_file in config_files:
                try:
                    with open(config_file, 'r') as f:
                        config_data["configs"][config_file.name] = json.load(f)
                except json.JSONDecodeError:
                    self.logger.warning(f"Could not read config file: {config_file}")
            
            # Save backup
            with open(backup_path, 'w') as f:
                json.dump(config_data, f, indent=2, default=str)
            
            result["success"] = True
            result["file_count"] = len(config_files)
            result["size_bytes"] = backup_path.stat().st_size
            result["backup_path"] = str(backup_path)
            result["message"] = f"System config backed up successfully"
            
        except Exception as e:
            result["message"] = f"Config backup failed: {str(e)}"
            
        return result
    
    def _create_backup_manifest(self, backup_date: date, backup_info: Dict[str, Any]):
        """Create a manifest file for the backup"""
        manifest_filename = f"backup_manifest_{backup_date.strftime('%Y%m%d')}.json"
        manifest_path = self.memory_backup_path / manifest_filename
        
        try:
            with open(manifest_path, 'w') as f:
                json.dump(backup_info, f, indent=2, default=str)
        except Exception as e:
            self.logger.error(f"Failed to create backup manifest: {e}")
    
    def restore_from_backup(self, backup_date: date) -> Dict[str, Any]:
        """Restore system from a specific backup"""
        result = {"success": False, "components_restored": 0, "errors": []}
        
        try:
            # Check if backup exists
            manifest_path = self.memory_backup_path / f"backup_manifest_{backup_date.strftime('%Y%m%d')}.json"
            
            if not manifest_path.exists():
                result["message"] = f"No backup found for {backup_date}"
                return result
            
            # Load backup manifest
            with open(manifest_path, 'r') as f:
                backup_manifest = json.load(f)
            
            restored_components = []
            
            # Restore memory database
            if self._restore_memory_database(backup_date):
                restored_components.append("memory")
            
            # Restore plugin states
            if self._restore_plugin_states(backup_date):
                restored_components.append("plugins")
            
            # Restore file metadata
            if self._restore_file_metadata(backup_date):
                restored_components.append("files")
            
            result["success"] = True
            result["components_restored"] = len(restored_components)
            result["restored_components"] = restored_components
            result["message"] = f"Successfully restored from backup {backup_date}"
            
        except Exception as e:
            result["message"] = f"Restore failed: {str(e)}"
            result["errors"].append(str(e))
        
        return result
    
    def _restore_memory_database(self, backup_date: date) -> bool:
        """Restore memory database from backup"""
        try:
            backup_filename = f"memory_backup_{backup_date.strftime('%Y%m%d')}.db"
            backup_path = self.memory_backup_path / backup_filename
            
            if not backup_path.exists():
                return False
            
            # Restore to original location
            memory_db_path = self.storage_config.project_root / "database" / "memory.db"
            memory_db_path.parent.mkdir(parents=True, exist_ok=True)
            
            shutil.copy2(backup_path, memory_db_path)
            return True
            
        except Exception as e:
            self.logger.error(f"Memory database restore failed: {e}")
            return False
    
    def _restore_plugin_states(self, backup_date: date) -> bool:
        """Restore plugin states from backup"""
        try:
            # Find all plugin backups for the date
            backup_pattern = f"*_backup_{backup_date.strftime('%Y%m%d')}.json"
            plugin_backups = []
            
            for plugin_dir in self.storage_config.get_path("plugins").iterdir():
                if plugin_dir.is_dir():
                    backup_dir = plugin_dir / "backups"
                    if backup_dir.exists():
                        plugin_backups.extend(backup_dir.glob(backup_pattern))
            
            for backup_file in plugin_backups:
                try:
                    with open(backup_file, 'r') as f:
                        backup_data = json.load(f)
                    
                    plugin_name = backup_data["plugin_name"]
                    plugin_data_path = self.storage_config.get_plugin_path(plugin_name, "data")
                    plugin_data_path.mkdir(parents=True, exist_ok=True)
                    
                    # Restore each data file
                    for filename, data in backup_data["data"].items():
                        restore_path = plugin_data_path / filename
                        with open(restore_path, 'w') as f:
                            json.dump(data, f, indent=2, default=str)
                            
                except Exception as e:
                    self.logger.error(f"Failed to restore plugin backup {backup_file}: {e}")
            
            return len(plugin_backups) > 0
            
        except Exception as e:
            self.logger.error(f"Plugin restore failed: {e}")
            return False
    
    def _restore_file_metadata(self, backup_date: date) -> bool:
        """Restore file metadata database from backup"""
        try:
            backup_filename = f"files_metadata_backup_{backup_date.strftime('%Y%m%d')}.db"
            backup_path = self.memory_backup_path / backup_filename
            
            if not backup_path.exists():
                return False
            
            # Restore to original location
            file_db_path = self.storage_config.get_path("indexes", "files.db")
            file_db_path.parent.mkdir(parents=True, exist_ok=True)
            
            shutil.copy2(backup_path, file_db_path)
            return True
            
        except Exception as e:
            self.logger.error(f"File metadata restore failed: {e}")
            return False
    
    def list_available_backups(self) -> List[Dict[str, Any]]:
        """List all available backup dates and their status"""
        backups = []
        
        try:
            backup_manifests = list(self.memory_backup_path.glob("backup_manifest_*.json"))
            
            for manifest_path in sorted(backup_manifests):
                try:
                    with open(manifest_path, 'r') as f:
                        manifest = json.load(f)
                    
                    backups.append({
                        "backup_date": manifest["backup_date"],
                        "timestamp": manifest["timestamp"],
                        "success": manifest["success"],
                        "components": list(manifest["components"].keys()),
                        "manifest_path": str(manifest_path)
                    })
                except Exception as e:
                    self.logger.error(f"Failed to read backup manifest {manifest_path}: {e}")
        
        except Exception as e:
            self.logger.error(f"Failed to list backups: {e}")
        
        return backups
    
    def cleanup_old_backups(self, keep_days: int = 30) -> Dict[str, Any]:
        """Clean up backups older than specified days"""
        result = {"success": False, "cleaned_count": 0, "errors": []}
        
        try:
            cutoff_date = datetime.now().date()
            cutoff_date = date(cutoff_date.year, cutoff_date.month, cutoff_date.day - keep_days)
            
            # Find old backup files
            old_files = []
            for backup_file in self.memory_backup_path.glob("*backup_*.db"):
                old_files.append(backup_file)
            for backup_file in self.memory_backup_path.glob("*backup_*.json"):
                old_files.append(backup_file)
            
            cleaned_count = 0
            for backup_file in old_files:
                # Extract date from filename
                try:
                    date_str = backup_file.stem.split('_')[-1]
                    file_date = datetime.strptime(date_str, '%Y%m%d').date()
                    
                    if file_date < cutoff_date:
                        backup_file.unlink()
                        cleaned_count += 1
                except (ValueError, IndexError):
                    # Skip files that don't match expected pattern
                    continue
            
            result["success"] = True
            result["cleaned_count"] = cleaned_count
            result["message"] = f"Cleaned up {cleaned_count} old backup files"
            
        except Exception as e:
            result["message"] = f"Backup cleanup failed: {str(e)}"
            result["errors"].append(str(e))
        
        return result