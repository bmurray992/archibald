"""
Unit tests for storage_config module
"""
import pytest
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

from archie_core.storage_config import (
    ArchieStorageConfig, 
    get_storage_config, 
    init_storage_config,
    StorageConfig
)


class TestStorageConfig:
    """Test the StorageConfig dataclass"""
    
    def test_storage_config_creation(self):
        """Test StorageConfig creation with default values"""
        config = StorageConfig(root_path="/test/path")
        
        assert config.root_path == "/test/path"
        assert config.external_drive is False
        assert config.drive_mount_point == "/mnt/archie_drive"
    
    def test_storage_config_with_external_drive(self):
        """Test StorageConfig creation with external drive"""
        config = StorageConfig(
            root_path="/test/path",
            external_drive=True,
            drive_mount_point="/custom/mount"
        )
        
        assert config.root_path == "/test/path"
        assert config.external_drive is True
        assert config.drive_mount_point == "/custom/mount"


class TestArchieStorageConfig:
    """Test the ArchieStorageConfig class"""
    
    def test_init_local_development(self, temp_storage_root):
        """Test initialization for local development"""
        config = ArchieStorageConfig(custom_root=str(temp_storage_root))
        
        assert config.storage_root == temp_storage_root
        assert config.external_drive is False
        assert config.project_root.name == "archie"
    
    def test_init_external_drive(self, temp_storage_root):
        """Test initialization with external drive"""
        config = ArchieStorageConfig(
            external_drive=True, 
            custom_root=str(temp_storage_root)
        )
        
        assert config.storage_root == temp_storage_root
        assert config.external_drive is True
    
    def test_init_raspberry_pi_path(self, temp_storage_root):
        """Test initialization with Raspberry Pi path"""
        # Use temp directory instead of actual /mnt path
        mock_pi_path = temp_storage_root / "mnt_archie_drive" / "storage"
        config = ArchieStorageConfig(external_drive=True, custom_root=str(mock_pi_path))
        
        assert config.storage_root == mock_pi_path
        assert config.external_drive is True
    
    def test_directory_structure_creation(self, temp_storage_root):
        """Test that all required directories are created"""
        config = ArchieStorageConfig(custom_root=str(temp_storage_root))
        
        expected_dirs = [
            "uploads", "media", "memory", "plugins", "vault",
            "exports", "temp", "cold", "thumbnails", "indexes"
        ]
        
        for dir_name in expected_dirs:
            dir_path = temp_storage_root / dir_name
            assert dir_path.exists(), f"Directory {dir_name} should exist"
            assert dir_path.is_dir(), f"{dir_name} should be a directory"
    
    def test_plugin_subdirectories_creation(self, temp_storage_root):
        """Test that plugin subdirectories are created"""
        config = ArchieStorageConfig(custom_root=str(temp_storage_root))
        
        plugin_names = ["calendar", "finance", "reminders", "media", 
                       "tasks", "research", "journal", "health"]
        subdirs = ["data", "backups", "exports", "temp"]
        
        for plugin in plugin_names:
            for subdir in subdirs:
                plugin_path = temp_storage_root / "plugins" / plugin / subdir
                assert plugin_path.exists(), f"Plugin dir {plugin}/{subdir} should exist"
    
    def test_get_path_valid_types(self, temp_storage_root):
        """Test getting paths for valid path types"""
        config = ArchieStorageConfig(custom_root=str(temp_storage_root))
        
        valid_types = ["uploads", "media", "memory", "plugins", "vault",
                      "exports", "temp", "cold", "thumbnails", "indexes"]
        
        for path_type in valid_types:
            path = config.get_path(path_type)
            assert path == temp_storage_root / path_type
            assert isinstance(path, Path)
    
    def test_get_path_with_args(self, temp_storage_root):
        """Test getting paths with additional arguments"""
        config = ArchieStorageConfig(custom_root=str(temp_storage_root))
        
        path = config.get_path("uploads", "subfolder", "file.txt")
        expected = temp_storage_root / "uploads" / "subfolder" / "file.txt"
        assert path == expected
    
    def test_get_path_invalid_type(self, temp_storage_root):
        """Test getting path with invalid type raises ValueError"""
        config = ArchieStorageConfig(custom_root=str(temp_storage_root))
        
        with pytest.raises(ValueError, match="Unknown path type: invalid"):
            config.get_path("invalid")
    
    def test_get_plugin_path(self, temp_storage_root):
        """Test getting plugin-specific paths"""
        config = ArchieStorageConfig(custom_root=str(temp_storage_root))
        
        # Test default data subdirectory
        path = config.get_plugin_path("calendar")
        expected = temp_storage_root / "plugins" / "calendar" / "data"
        assert path == expected
        
        # Test custom subdirectory
        path = config.get_plugin_path("calendar", "backups")
        expected = temp_storage_root / "plugins" / "calendar" / "backups"
        assert path == expected
    
    def test_get_storage_stats_empty(self, temp_storage_root):
        """Test getting storage statistics for empty directories"""
        config = ArchieStorageConfig(custom_root=str(temp_storage_root))
        
        stats = config.get_storage_stats()
        
        expected_types = ["uploads", "media", "memory", "plugins", "vault", "cold"]
        for path_type in expected_types:
            assert path_type in stats
            assert stats[path_type]["size_bytes"] == 0
            assert stats[path_type]["file_count"] == 0
            assert "path" in stats[path_type]
    
    def test_get_storage_stats_with_files(self, temp_storage_root):
        """Test getting storage statistics with actual files"""
        config = ArchieStorageConfig(custom_root=str(temp_storage_root))
        
        # Create test files
        uploads_dir = temp_storage_root / "uploads"
        test_file = uploads_dir / "test.txt"
        test_content = "Hello, world!"
        test_file.write_text(test_content)
        
        stats = config.get_storage_stats()
        
        assert stats["uploads"]["size_bytes"] == len(test_content.encode())
        assert stats["uploads"]["file_count"] == 1
    
    def test_is_external_drive_available_local(self, temp_storage_root):
        """Test external drive availability check for local development"""
        config = ArchieStorageConfig(custom_root=str(temp_storage_root))
        
        # Should return True for local development (no external drive)
        assert config.is_external_drive_available() is True
    
    def test_is_external_drive_available_external(self, temp_storage_root):
        """Test external drive availability check for external drive"""
        config = ArchieStorageConfig(external_drive=True, custom_root=str(temp_storage_root))
        
        with patch('pathlib.Path.exists') as mock_exists, \
             patch('pathlib.Path.is_mount') as mock_is_mount:
            
            # Test when drive is available
            mock_exists.return_value = True
            mock_is_mount.return_value = True
            assert config.is_external_drive_available() is True
            
            # Test when drive is not mounted
            mock_exists.return_value = True
            mock_is_mount.return_value = False
            assert config.is_external_drive_available() is False
            
            # Test when mount point doesn't exist
            mock_exists.return_value = False
            assert config.is_external_drive_available() is False
    
    def test_get_available_space(self, temp_storage_root):
        """Test getting available disk space"""
        config = ArchieStorageConfig(custom_root=str(temp_storage_root))
        
        with patch('shutil.disk_usage') as mock_disk_usage:
            # Create a mock named tuple like shutil.disk_usage returns
            from collections import namedtuple
            DiskUsage = namedtuple('usage', 'total used free')
            mock_disk_usage.return_value = DiskUsage(1000000, 400000, 600000)
            
            available_space = config.get_available_space()
            assert available_space == 600000
            
            mock_disk_usage.assert_called_once_with(str(temp_storage_root))
    
    def test_get_total_space(self, temp_storage_root):
        """Test getting total disk space"""
        config = ArchieStorageConfig(custom_root=str(temp_storage_root))
        
        with patch('shutil.disk_usage') as mock_disk_usage:
            # Create a mock named tuple like shutil.disk_usage returns
            from collections import namedtuple
            DiskUsage = namedtuple('usage', 'total used free')
            mock_disk_usage.return_value = DiskUsage(1000000, 400000, 600000)
            
            total_space = config.get_total_space()
            assert total_space == 1000000
            
            mock_disk_usage.assert_called_once_with(str(temp_storage_root))


class TestGlobalStorageConfig:
    """Test global storage configuration functions"""
    
    @patch('os.path.exists')
    @patch.object(ArchieStorageConfig, 'ensure_directory_structure')
    def test_get_storage_config_raspberry_pi(self, mock_ensure_dirs, mock_exists):
        """Test getting storage config on Raspberry Pi"""
        mock_exists.return_value = True
        
        config = get_storage_config()
        
        assert config.external_drive is True
        assert str(config.storage_root) == "/mnt/archie_drive/storage"
        mock_exists.assert_called_once_with("/mnt/archie_drive")
    
    @patch('os.path.exists')
    def test_get_storage_config_local(self, mock_exists):
        """Test getting storage config for local development"""
        mock_exists.return_value = False
        
        config = get_storage_config()
        
        assert config.external_drive is False
        assert config.storage_root.name == "storage"
        mock_exists.assert_called_once_with("/mnt/archie_drive")
    
    def test_get_storage_config_singleton(self):
        """Test that get_storage_config returns the same instance"""
        config1 = get_storage_config()
        config2 = get_storage_config()
        
        assert config1 is config2
    
    def test_init_storage_config_override(self, temp_storage_root):
        """Test initializing storage config with custom parameters"""
        config = init_storage_config(
            external_drive=True, 
            custom_root=str(temp_storage_root)
        )
        
        assert config.external_drive is True
        assert config.storage_root == temp_storage_root
        
        # Test that get_storage_config now returns this instance
        same_config = get_storage_config()
        assert same_config is config


class TestEdgeCases:
    """Test edge cases and error conditions"""
    
    def test_storage_config_with_nonexistent_custom_root(self, temp_storage_root):
        """Test behavior with non-existent custom root"""
        non_existent_path = temp_storage_root / "nonexistent" / "nested" / "path"
        
        # Should not raise an error during initialization
        config = ArchieStorageConfig(custom_root=str(non_existent_path))
        
        # But directories should be created
        assert non_existent_path.exists()
    
    def test_get_path_with_empty_args(self, temp_storage_root):
        """Test get_path with empty additional arguments"""
        config = ArchieStorageConfig(custom_root=str(temp_storage_root))
        
        path = config.get_path("uploads", "", None)
        # Should handle empty strings gracefully
        expected = temp_storage_root / "uploads" / "" / "None"
        assert path == expected
    
    def test_get_storage_stats_with_nested_files(self, temp_storage_root):
        """Test storage stats calculation with nested directory structure"""
        config = ArchieStorageConfig(custom_root=str(temp_storage_root))
        
        # Create nested files
        nested_dir = temp_storage_root / "media" / "photos" / "2024"
        nested_dir.mkdir(parents=True)
        
        file1 = nested_dir / "photo1.jpg"
        file2 = nested_dir / "photo2.jpg"
        
        file1.write_bytes(b"fake jpg data 1" * 100)
        file2.write_bytes(b"fake jpg data 2" * 200)
        
        stats = config.get_storage_stats()
        
        # Should count all files recursively
        expected_size = len(b"fake jpg data 1" * 100) + len(b"fake jpg data 2" * 200)
        assert stats["media"]["size_bytes"] == expected_size
        assert stats["media"]["file_count"] == 2