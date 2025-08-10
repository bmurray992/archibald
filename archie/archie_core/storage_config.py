"""
ArchieOS Storage Configuration
Manages storage paths and hierarchy for local development and Raspberry Pi deployment
"""
import os
from pathlib import Path
from typing import Dict, Optional
from dataclasses import dataclass


@dataclass
class StorageConfig:
    """Storage configuration for ArchieOS"""
    root_path: str
    external_drive: bool = False
    drive_mount_point: str = "/mnt/archie_drive"
    
    
class ArchieStorageConfig:
    """Central storage configuration manager"""
    
    def __init__(self, external_drive: bool = False, custom_root: Optional[str] = None):
        self.external_drive = external_drive
        self.project_root = Path(__file__).parent.parent
        
        if custom_root:
            self.storage_root = Path(custom_root)
        elif external_drive:
            # Raspberry Pi with external drive
            self.storage_root = Path("/mnt/archie_drive/storage")
        else:
            # Local development
            self.storage_root = self.project_root / "storage"
            
        self.ensure_directory_structure()
    
    def ensure_directory_structure(self):
        """Create the complete ArchieOS directory structure"""
        directories = [
            "uploads",      # User uploaded files
            "media",        # Photos, videos, audio
            "memory",       # Daily memory backups
            "plugins",      # Plugin data archives
            "vault",        # Encrypted/secure files
            "exports",      # Export snapshots
            "temp",         # Temporary processing files
            "cold",         # Cold storage (old files)
            "thumbnails",   # Generated thumbnails
            "indexes",      # Search indexes and metadata
        ]
        
        for directory in directories:
            dir_path = self.storage_root / directory
            dir_path.mkdir(parents=True, exist_ok=True)
            
        # Create subdirectories for better organization
        plugin_dirs = ["calendar", "finance", "reminders", "media", "tasks", "research", "journal", "health"]
        for plugin in plugin_dirs:
            for subdir in ["data", "backups", "exports", "temp"]:
                plugin_path = self.storage_root / "plugins" / plugin / subdir
                plugin_path.mkdir(parents=True, exist_ok=True)
    
    def get_path(self, path_type: str, *args) -> Path:
        """Get a specific storage path"""
        base_paths = {
            "uploads": self.storage_root / "uploads",
            "media": self.storage_root / "media", 
            "memory": self.storage_root / "memory",
            "plugins": self.storage_root / "plugins",
            "vault": self.storage_root / "vault",
            "exports": self.storage_root / "exports",
            "temp": self.storage_root / "temp",
            "cold": self.storage_root / "cold",
            "thumbnails": self.storage_root / "thumbnails",
            "indexes": self.storage_root / "indexes",
        }
        
        if path_type not in base_paths:
            raise ValueError(f"Unknown path type: {path_type}")
            
        path = base_paths[path_type]
        
        # Join additional path components
        for arg in args:
            path = path / str(arg)
            
        return path
    
    def get_plugin_path(self, plugin_name: str, subdir: str = "data") -> Path:
        """Get path for a specific plugin's data"""
        return self.get_path("plugins", plugin_name, subdir)
    
    def get_storage_stats(self) -> Dict[str, any]:
        """Get storage usage statistics"""
        stats = {}
        
        for path_type in ["uploads", "media", "memory", "plugins", "vault", "cold"]:
            path = self.get_path(path_type)
            if path.exists():
                size = sum(f.stat().st_size for f in path.rglob('*') if f.is_file())
                file_count = len([f for f in path.rglob('*') if f.is_file()])
                stats[path_type] = {
                    "size_bytes": size,
                    "file_count": file_count,
                    "path": str(path)
                }
            else:
                stats[path_type] = {"size_bytes": 0, "file_count": 0, "path": str(path)}
                
        return stats
    
    def is_external_drive_available(self) -> bool:
        """Check if external drive is mounted and available"""
        if not self.external_drive:
            return True
            
        mount_point = Path("/mnt/archie_drive")
        return mount_point.exists() and mount_point.is_mount()
    
    def get_available_space(self) -> int:
        """Get available space in bytes"""
        import shutil
        return shutil.disk_usage(str(self.storage_root)).free
    
    def get_total_space(self) -> int:
        """Get total space in bytes"""
        import shutil
        return shutil.disk_usage(str(self.storage_root)).total


# Global storage configuration instance
_storage_config = None

def get_storage_config() -> ArchieStorageConfig:
    """Get the global storage configuration instance"""
    global _storage_config
    if _storage_config is None:
        # Check if we're on Raspberry Pi with external drive
        external_drive = os.path.exists("/mnt/archie_drive")
        _storage_config = ArchieStorageConfig(external_drive=external_drive)
    return _storage_config

def init_storage_config(external_drive: bool = False, custom_root: Optional[str] = None):
    """Initialize storage configuration (for testing or custom setups)"""
    global _storage_config
    _storage_config = ArchieStorageConfig(external_drive=external_drive, custom_root=custom_root)
    return _storage_config