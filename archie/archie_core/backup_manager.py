"""
ArchieOS Backup Manager - Automated memory and file backup system
"""
import os
import json
import sqlite3
import shutil
import tarfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


class BackupManager:
    """
    Manages automated backups of memory and plugin data for ArchieOS
    """
    
    def __init__(self, 
                 memory_db_path: str = None,
                 storage_path: str = None,
                 backup_path: str = None):
        # Set paths
        base_dir = Path(__file__).parent.parent
        
        if memory_db_path is None:
            memory_db_path = base_dir / "database" / "memory.db"
        if storage_path is None:
            storage_path = base_dir / "storage"
        if backup_path is None:
            backup_path = storage_path / "backups"
        
        self.memory_db_path = Path(memory_db_path)
        self.storage_path = Path(storage_path)
        self.backup_path = Path(backup_path)
        
        # Create backup directories
        self.backup_path.mkdir(parents=True, exist_ok=True)
        (self.backup_path / "memory").mkdir(exist_ok=True)
        (self.backup_path / "plugins").mkdir(exist_ok=True)
        (self.backup_path / "exports").mkdir(exist_ok=True)
        
        logger.info("💾 Archie: Backup Manager initialized - Ready to preserve your memories!")
    
    def backup_memory_database(self) -> Dict[str, Any]:
        """
        Backup the entire memory database
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"memory_backup_{timestamp}.db"
        backup_file = self.backup_path / "memory" / backup_filename
        
        try:
            # Copy database file
            if self.memory_db_path.exists():
                shutil.copy2(self.memory_db_path, backup_file)
                
                # Verify backup
                file_size = backup_file.stat().st_size
                
                logger.info(f"✅ Memory database backed up: {backup_filename} ({file_size} bytes)")
                
                return {
                    "success": True,
                    "backup_file": str(backup_file),
                    "size_bytes": file_size,
                    "timestamp": timestamp
                }
            else:
                logger.warning("⚠️ Memory database not found for backup")
                return {
                    "success": False,
                    "error": "Memory database not found"
                }
                
        except Exception as e:
            logger.error(f"❌ Memory backup failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def backup_plugin_data(self, plugin_name: str = None) -> Dict[str, Any]:
        """
        Backup plugin-specific data to JSON
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results = []
        
        try:
            # If specific plugin requested
            if plugin_name:
                plugins = [plugin_name]
            else:
                # Backup all plugins
                plugins_dir = self.storage_path / "plugins"
                plugins = [d.name for d in plugins_dir.iterdir() if d.is_dir()]
            
            for plugin in plugins:
                plugin_data = self._extract_plugin_data(plugin)
                
                if plugin_data:
                    # Save to JSON
                    backup_filename = f"{plugin}_backup_{timestamp}.json"
                    backup_file = self.backup_path / "plugins" / backup_filename
                    
                    with open(backup_file, 'w') as f:
                        json.dump(plugin_data, f, indent=2)
                    
                    results.append({
                        "plugin": plugin,
                        "backup_file": str(backup_file),
                        "entries_count": len(plugin_data.get("memories", [])),
                        "files_count": len(plugin_data.get("files", []))
                    })
                    
                    logger.info(f"✅ Plugin {plugin} backed up successfully")
            
            return {
                "success": True,
                "backups": results,
                "timestamp": timestamp
            }
            
        except Exception as e:
            logger.error(f"❌ Plugin backup failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def create_full_backup(self) -> Dict[str, Any]:
        """
        Create a complete ArchieOS backup archive
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_name = f"archie_full_backup_{timestamp}.tar.gz"
        archive_path = self.backup_path / "exports" / archive_name
        
        try:
            with tarfile.open(archive_path, "w:gz") as tar:
                # Backup memory database
                if self.memory_db_path.exists():
                    tar.add(self.memory_db_path, arcname="memory.db")
                
                # Backup all plugin folders
                plugins_dir = self.storage_path / "plugins"
                if plugins_dir.exists():
                    for plugin_dir in plugins_dir.iterdir():
                        if plugin_dir.is_dir():
                            tar.add(plugin_dir, arcname=f"plugins/{plugin_dir.name}")
                
                # Backup media folder
                media_dir = self.storage_path / "media"
                if media_dir.exists():
                    tar.add(media_dir, arcname="media")
                
                # Add backup metadata
                metadata = {
                    "backup_timestamp": timestamp,
                    "archie_version": "2.0.0",
                    "backup_type": "full",
                    "created_by": "ArchieOS Backup Manager"
                }
                
                metadata_file = self.backup_path / "temp_metadata.json"
                with open(metadata_file, 'w') as f:
                    json.dump(metadata, f, indent=2)
                
                tar.add(metadata_file, arcname="backup_metadata.json")
                metadata_file.unlink()  # Clean up temp file
            
            archive_size = archive_path.stat().st_size
            
            logger.info(f"🎉 Full backup created: {archive_name} ({archive_size / 1024 / 1024:.2f} MB)")
            
            return {
                "success": True,
                "archive_path": str(archive_path),
                "archive_size_mb": round(archive_size / 1024 / 1024, 2),
                "timestamp": timestamp
            }
            
        except Exception as e:
            logger.error(f"❌ Full backup failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def restore_from_backup(self, backup_file: str) -> Dict[str, Any]:
        """
        Restore from a backup file (database or archive)
        """
        backup_path = Path(backup_file)
        
        if not backup_path.exists():
            return {
                "success": False,
                "error": "Backup file not found"
            }
        
        try:
            # Determine backup type
            if backup_path.suffix == '.db':
                # Restore memory database
                return self._restore_database(backup_path)
            elif backup_path.suffix in ['.gz', '.tar']:
                # Restore from archive
                return self._restore_archive(backup_path)
            elif backup_path.suffix == '.json':
                # Restore plugin data
                return self._restore_plugin_data(backup_path)
            else:
                return {
                    "success": False,
                    "error": "Unknown backup format"
                }
                
        except Exception as e:
            logger.error(f"❌ Restore failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def cleanup_old_backups(self, days_to_keep: int = 30) -> Dict[str, Any]:
        """
        Remove backups older than specified days
        """
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        removed_count = 0
        freed_space = 0
        
        try:
            # Check all backup directories
            for backup_dir in [self.backup_path / "memory", 
                             self.backup_path / "plugins",
                             self.backup_path / "exports"]:
                if backup_dir.exists():
                    for backup_file in backup_dir.iterdir():
                        if backup_file.is_file():
                            file_time = datetime.fromtimestamp(backup_file.stat().st_mtime)
                            if file_time < cutoff_date:
                                file_size = backup_file.stat().st_size
                                backup_file.unlink()
                                removed_count += 1
                                freed_space += file_size
            
            logger.info(f"🧹 Cleaned up {removed_count} old backups, freed {freed_space / 1024 / 1024:.2f} MB")
            
            return {
                "success": True,
                "removed_count": removed_count,
                "freed_space_mb": round(freed_space / 1024 / 1024, 2),
                "days_kept": days_to_keep
            }
            
        except Exception as e:
            logger.error(f"❌ Backup cleanup failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_backup_schedule_status(self) -> Dict[str, Any]:
        """
        Get information about backup schedules and recent backups
        """
        recent_backups = []
        
        # Check for recent backups
        for backup_type, backup_dir in [
            ("memory", self.backup_path / "memory"),
            ("plugins", self.backup_path / "plugins"),
            ("full", self.backup_path / "exports")
        ]:
            if backup_dir.exists():
                backups = sorted(backup_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True)
                if backups:
                    latest = backups[0]
                    recent_backups.append({
                        "type": backup_type,
                        "filename": latest.name,
                        "timestamp": datetime.fromtimestamp(latest.stat().st_mtime).isoformat(),
                        "size_mb": round(latest.stat().st_size / 1024 / 1024, 2)
                    })
        
        # Calculate total backup size
        total_size = sum(f.stat().st_size for f in self.backup_path.rglob("*") if f.is_file())
        
        return {
            "backup_path": str(self.backup_path),
            "recent_backups": recent_backups,
            "total_backup_size_mb": round(total_size / 1024 / 1024, 2),
            "backup_count": len(list(self.backup_path.rglob("*")))
        }
    
    def _extract_plugin_data(self, plugin_name: str) -> Optional[Dict[str, Any]]:
        """
        Extract plugin-specific data from memory and files
        """
        plugin_data = {
            "plugin": plugin_name,
            "backup_timestamp": datetime.now().isoformat(),
            "memories": [],
            "files": []
        }
        
        # Extract memories from database
        if self.memory_db_path.exists():
            try:
                conn = sqlite3.connect(self.memory_db_path)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Get plugin-specific memories
                cursor.execute("""
                    SELECT * FROM memory_entries 
                    WHERE plugin_source = ? AND archived = FALSE
                    ORDER BY created_at DESC
                """, (plugin_name,))
                
                for row in cursor.fetchall():
                    plugin_data["memories"].append(dict(row))
                
                conn.close()
            except Exception as e:
                logger.warning(f"Could not extract memories for {plugin_name}: {e}")
        
        # Get plugin files info
        plugin_dir = self.storage_path / "plugins" / plugin_name
        if plugin_dir.exists():
            for meta_file in plugin_dir.rglob("*.meta.json"):
                try:
                    with open(meta_file, 'r') as f:
                        file_info = json.load(f)
                        plugin_data["files"].append(file_info)
                except:
                    pass
        
        return plugin_data if (plugin_data["memories"] or plugin_data["files"]) else None
    
    def _restore_database(self, backup_file: Path) -> Dict[str, Any]:
        """
        Restore memory database from backup
        """
        # Create safety backup of current database
        if self.memory_db_path.exists():
            safety_backup = self.memory_db_path.with_suffix('.db.pre_restore')
            shutil.copy2(self.memory_db_path, safety_backup)
        
        # Restore from backup
        shutil.copy2(backup_file, self.memory_db_path)
        
        logger.info(f"✅ Database restored from {backup_file.name}")
        
        return {
            "success": True,
            "restored_from": str(backup_file),
            "restore_type": "database"
        }
    
    def _restore_archive(self, archive_file: Path) -> Dict[str, Any]:
        """
        Restore from full backup archive
        """
        temp_dir = self.backup_path / "temp_restore"
        temp_dir.mkdir(exist_ok=True)
        
        # Extract archive
        with tarfile.open(archive_file, "r:gz") as tar:
            tar.extractall(temp_dir)
        
        # Restore components
        restored_items = []
        
        # Restore memory database
        temp_db = temp_dir / "memory.db"
        if temp_db.exists():
            if self.memory_db_path.exists():
                shutil.copy2(self.memory_db_path, self.memory_db_path.with_suffix('.db.pre_restore'))
            shutil.copy2(temp_db, self.memory_db_path)
            restored_items.append("memory_database")
        
        # Restore plugins
        temp_plugins = temp_dir / "plugins"
        if temp_plugins.exists():
            for plugin_dir in temp_plugins.iterdir():
                if plugin_dir.is_dir():
                    target_dir = self.storage_path / "plugins" / plugin_dir.name
                    if target_dir.exists():
                        shutil.rmtree(target_dir)
                    shutil.copytree(plugin_dir, target_dir)
                    restored_items.append(f"plugin_{plugin_dir.name}")
        
        # Clean up temp directory
        shutil.rmtree(temp_dir)
        
        logger.info(f"✅ Full restore completed from {archive_file.name}")
        
        return {
            "success": True,
            "restored_from": str(archive_file),
            "restore_type": "full_archive",
            "restored_items": restored_items
        }
    
    def _restore_plugin_data(self, json_file: Path) -> Dict[str, Any]:
        """
        Restore plugin data from JSON backup
        """
        with open(json_file, 'r') as f:
            plugin_data = json.load(f)
        
        plugin_name = plugin_data.get("plugin")
        restored_memories = 0
        
        # Restore memories to database
        if plugin_data.get("memories") and self.memory_db_path.exists():
            try:
                conn = sqlite3.connect(self.memory_db_path)
                cursor = conn.cursor()
                
                for memory in plugin_data["memories"]:
                    # Check if memory already exists
                    cursor.execute("SELECT id FROM memory_entries WHERE id = ?", (memory.get("id"),))
                    if not cursor.fetchone():
                        # Insert memory
                        columns = list(memory.keys())
                        placeholders = ",".join("?" * len(columns))
                        values = [memory[col] for col in columns]
                        
                        cursor.execute(f"""
                            INSERT INTO memory_entries ({",".join(columns)})
                            VALUES ({placeholders})
                        """, values)
                        restored_memories += 1
                
                conn.commit()
                conn.close()
            except Exception as e:
                logger.error(f"Failed to restore memories: {e}")
        
        logger.info(f"✅ Plugin {plugin_name} restored: {restored_memories} memories")
        
        return {
            "success": True,
            "restored_from": str(json_file),
            "restore_type": "plugin_data",
            "plugin": plugin_name,
            "restored_memories": restored_memories
        }
    
    def close(self):
        """Clean shutdown"""
        logger.info("🏁 Archie: Backup Manager shutting down")