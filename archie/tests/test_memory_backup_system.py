"""
Unit tests for memory_backup_system module
"""
import pytest
import json
import sqlite3
import shutil
from datetime import datetime, date, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open

from archie_core.memory_backup_system import MemoryBackupSystem


class TestMemoryBackupSystem:
    """Test the MemoryBackupSystem class"""
    
    def test_init(self, memory_backup_system):
        """Test initialization of memory backup system"""
        assert memory_backup_system.storage_config is not None
        assert memory_backup_system.memory_backup_path.exists()
        assert memory_backup_system.plugin_backup_path.exists()
    
    def test_create_daily_backup_basic(self, memory_backup_system):
        """Test basic daily backup creation"""
        backup_date = date(2024, 8, 5)
        
        result = memory_backup_system.create_daily_backup(backup_date)
        
        assert isinstance(result, dict)
        assert result["backup_date"] == "2024-08-05"
        assert "timestamp" in result
        assert "components" in result
        assert "success" in result
        assert "errors" in result
        
        # Check that manifest was created
        manifest_path = memory_backup_system.memory_backup_path / "backup_manifest_20240805.json"
        assert manifest_path.exists()
    
    def test_create_daily_backup_default_date(self, memory_backup_system):
        """Test daily backup with default date (today)"""
        result = memory_backup_system.create_daily_backup()
        
        today = date.today()
        assert result["backup_date"] == today.isoformat()
    
    def test_backup_memory_database_exists(self, memory_backup_system, mock_memory_db):
        """Test backing up existing memory database"""
        # Move mock db to expected location
        memory_db_path = memory_backup_system.storage_config.project_root / "database" / "memory.db"
        memory_db_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(mock_memory_db, memory_db_path)
        
        backup_date = date(2024, 8, 5)
        result = memory_backup_system._backup_memory_database(backup_date)
        
        assert result["success"] is True
        assert result["file_count"] == 1
        assert result["size_bytes"] > 0
        assert "backup_path" in result
        
        # Verify backup file exists
        backup_path = Path(result["backup_path"])
        assert backup_path.exists()
        assert backup_path.name == "memory_backup_20240805.db"
    
    def test_backup_memory_database_not_exists(self, memory_backup_system):
        """Test backing up non-existent memory database"""
        backup_date = date(2024, 8, 5)
        result = memory_backup_system._backup_memory_database(backup_date)
        
        assert result["success"] is False
        assert result["file_count"] == 0
        assert result["message"] == "Memory database not found"
    
    def test_backup_plugin_states_empty(self, memory_backup_system):
        """Test backing up plugin states when no plugins exist"""
        backup_date = date(2024, 8, 5)
        result = memory_backup_system._backup_plugin_states(backup_date)
        
        assert result["success"] is True
        assert result["plugins_backed_up"] == 0
        assert result["total_files"] == 0
        assert result["size_bytes"] == 0
    
    def test_backup_plugin_states_with_data(self, memory_backup_system):
        """Test backing up plugin states with actual data"""
        backup_date = date(2024, 8, 5)
        
        # Create test plugin data
        plugin_name = "test_plugin"
        plugin_data_path = memory_backup_system.storage_config.get_plugin_path(plugin_name, "data")
        plugin_data_path.mkdir(parents=True, exist_ok=True)
        
        # Create test JSON files
        test_data1 = {"key1": "value1", "timestamp": "2024-08-05"}
        test_data2 = {"key2": "value2", "config": True}
        
        (plugin_data_path / "data1.json").write_text(json.dumps(test_data1))
        (plugin_data_path / "data2.json").write_text(json.dumps(test_data2))
        
        result = memory_backup_system._backup_plugin_states(backup_date)
        
        assert result["success"] is True
        assert result["plugins_backed_up"] == 1
        assert result["total_files"] == 2
        assert result["size_bytes"] > 0
        assert "plugin_details" in result
        assert plugin_name in result["plugin_details"]
        
        # Check the specific plugin backup
        plugin_result = result["plugin_details"][plugin_name]
        assert plugin_result["success"] is True
        assert plugin_result["file_count"] == 2
        
        # Verify backup file was created
        backup_path = Path(plugin_result["backup_path"])
        assert backup_path.exists()
        
        # Verify backup content
        with open(backup_path) as f:
            backup_content = json.load(f)
        
        assert backup_content["plugin_name"] == plugin_name
        assert backup_content["backup_date"] == "2024-08-05"
        assert "data1.json" in backup_content["data"]
        assert "data2.json" in backup_content["data"]
        assert backup_content["data"]["data1.json"] == test_data1
        assert backup_content["data"]["data2.json"] == test_data2
    
    def test_backup_single_plugin_no_data(self, memory_backup_system):
        """Test backing up plugin with no data"""
        backup_date = date(2024, 8, 5)
        plugin_name = "empty_plugin"
        
        result = memory_backup_system._backup_single_plugin(plugin_name, backup_date)
        
        assert result["success"] is True  # Should succeed even with no data
        assert result["file_count"] == 0
        assert result["size_bytes"] == 0
        assert "No data found" in result["message"]
    
    def test_backup_single_plugin_invalid_json(self, memory_backup_system):
        """Test backing up plugin with invalid JSON files"""
        backup_date = date(2024, 8, 5)
        plugin_name = "invalid_plugin"
        
        # Create plugin data directory with invalid JSON
        plugin_data_path = memory_backup_system.storage_config.get_plugin_path(plugin_name, "data")
        plugin_data_path.mkdir(parents=True, exist_ok=True)
        
        # Create invalid JSON file
        (plugin_data_path / "invalid.json").write_text("{ invalid json }")
        
        with patch.object(memory_backup_system.logger, 'warning') as mock_warning:
            result = memory_backup_system._backup_single_plugin(plugin_name, backup_date)
            
            assert result["success"] is True
            assert result["file_count"] == 1  # Still counts the file
            mock_warning.assert_called_once()
    
    def test_backup_file_metadata_exists(self, memory_backup_system, file_manager):
        """Test backing up existing file metadata database"""
        backup_date = date(2024, 8, 5)
        
        # File manager creates the database, so it should exist
        result = memory_backup_system._backup_file_metadata(backup_date)
        
        assert result["success"] is True
        assert result["file_count"] == 1
        assert result["size_bytes"] > 0
        assert "backup_path" in result
        
        # Verify backup file exists
        backup_path = Path(result["backup_path"])
        assert backup_path.exists()
        assert backup_path.name == "files_metadata_backup_20240805.db"
    
    def test_backup_file_metadata_not_exists(self, memory_backup_system):
        """Test backing up non-existent file metadata database"""
        backup_date = date(2024, 8, 5)
        
        # Remove the files.db if it exists
        file_db_path = memory_backup_system.storage_config.get_path("indexes", "files.db")
        if file_db_path.exists():
            file_db_path.unlink()
        
        result = memory_backup_system._backup_file_metadata(backup_date)
        
        assert result["success"] is True  # Should succeed even if not found
        assert result["file_count"] == 0
        assert "not found" in result["message"]
    
    def test_backup_system_config_exists(self, memory_backup_system):
        """Test backing up system configuration"""
        backup_date = date(2024, 8, 5)
        
        # Create test config files
        config_dir = memory_backup_system.storage_config.project_root / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        
        test_config = {"setting1": "value1", "setting2": True}
        (config_dir / "test_config.json").write_text(json.dumps(test_config))
        
        result = memory_backup_system._backup_system_config(backup_date)
        
        assert result["success"] is True
        assert result["file_count"] == 1
        assert result["size_bytes"] > 0
        assert "backup_path" in result
        
        # Verify backup content
        backup_path = Path(result["backup_path"])
        assert backup_path.exists()
        
        with open(backup_path) as f:
            backup_content = json.load(f)
        
        assert backup_content["backup_date"] == "2024-08-05"
        assert "test_config.json" in backup_content["configs"]
        assert backup_content["configs"]["test_config.json"] == test_config
    
    def test_backup_system_config_not_exists(self, memory_backup_system):
        """Test backing up system config when config dir doesn't exist"""
        backup_date = date(2024, 8, 5)
        
        # Ensure config directory doesn't exist
        config_dir = memory_backup_system.storage_config.project_root / "config"
        if config_dir.exists():
            shutil.rmtree(config_dir)
        
        result = memory_backup_system._backup_system_config(backup_date)
        
        assert result["success"] is True  # Should succeed even if not found
        assert result["file_count"] == 0
        assert "not found" in result["message"]
    
    def test_create_backup_manifest(self, memory_backup_system):
        """Test creating backup manifest"""
        backup_date = date(2024, 8, 5)
        backup_info = {
            "backup_date": "2024-08-05",
            "timestamp": "2024-08-05T12:00:00",
            "components": {"memory": {"success": True}},
            "success": True,
            "errors": []
        }
        
        memory_backup_system._create_backup_manifest(backup_date, backup_info)
        
        manifest_path = memory_backup_system.memory_backup_path / "backup_manifest_20240805.json"
        assert manifest_path.exists()
        
        with open(manifest_path) as f:
            saved_manifest = json.load(f)
        
        assert saved_manifest == backup_info
    
    @patch.object(MemoryBackupSystem, '_restore_memory_database')
    @patch.object(MemoryBackupSystem, '_restore_plugin_states')
    @patch.object(MemoryBackupSystem, '_restore_file_metadata')
    def test_restore_from_backup_success(self, mock_restore_files, mock_restore_plugins, 
                                        mock_restore_memory, memory_backup_system):
        """Test successful restore from backup"""
        backup_date = date(2024, 8, 5)
        
        # Create a test manifest
        backup_info = {
            "backup_date": "2024-08-05",
            "timestamp": "2024-08-05T12:00:00",
            "components": {
                "memory": {"success": True},
                "plugins": {"success": True},
                "files": {"success": True}
            },
            "success": True
        }
        
        manifest_path = memory_backup_system.memory_backup_path / "backup_manifest_20240805.json"
        with open(manifest_path, 'w') as f:
            json.dump(backup_info, f)
        
        # Mock successful restores
        mock_restore_memory.return_value = True
        mock_restore_plugins.return_value = True
        mock_restore_files.return_value = True
        
        result = memory_backup_system.restore_from_backup(backup_date)
        
        assert result["success"] is True
        assert result["components_restored"] == 3
        assert set(result["restored_components"]) == {"memory", "plugins", "files"}
        
        mock_restore_memory.assert_called_once_with(backup_date)
        mock_restore_plugins.assert_called_once_with(backup_date)
        mock_restore_files.assert_called_once_with(backup_date)
    
    def test_restore_from_backup_no_manifest(self, memory_backup_system):
        """Test restore when no backup manifest exists"""
        backup_date = date(2024, 8, 5)
        
        result = memory_backup_system.restore_from_backup(backup_date)
        
        assert result["success"] is False
        assert "No backup found" in result["message"]
    
    def test_restore_memory_database_success(self, memory_backup_system, mock_memory_db):
        """Test successful memory database restore"""
        backup_date = date(2024, 8, 5)
        
        # Create a backup file
        backup_filename = f"memory_backup_{backup_date.strftime('%Y%m%d')}.db"
        backup_path = memory_backup_system.memory_backup_path / backup_filename
        shutil.copy2(mock_memory_db, backup_path)
        
        result = memory_backup_system._restore_memory_database(backup_date)
        
        assert result is True
        
        # Verify database was restored
        memory_db_path = memory_backup_system.storage_config.project_root / "database" / "memory.db"
        assert memory_db_path.exists()
    
    def test_restore_memory_database_no_backup(self, memory_backup_system):
        """Test memory database restore when backup doesn't exist"""
        backup_date = date(2024, 8, 5)
        
        result = memory_backup_system._restore_memory_database(backup_date)
        
        assert result is False
    
    def test_restore_plugin_states_success(self, memory_backup_system):
        """Test successful plugin states restore"""
        backup_date = date(2024, 8, 5)
        plugin_name = "test_plugin"
        
        # Create a plugin backup
        plugin_backup_path = memory_backup_system.storage_config.get_plugin_path(plugin_name, "backups")
        plugin_backup_path.mkdir(parents=True, exist_ok=True)
        
        backup_data = {
            "plugin_name": plugin_name,
            "backup_date": "2024-08-05",
            "timestamp": "2024-08-05T12:00:00",
            "data": {
                "config.json": {"setting": "value"},
                "data.json": {"items": [1, 2, 3]}
            }
        }
        
        backup_filename = f"{plugin_name}_backup_20240805.json"
        backup_file = plugin_backup_path / backup_filename
        with open(backup_file, 'w') as f:
            json.dump(backup_data, f)
        
        result = memory_backup_system._restore_plugin_states(backup_date)
        
        assert result is True
        
        # Verify plugin data was restored
        plugin_data_path = memory_backup_system.storage_config.get_plugin_path(plugin_name, "data")
        config_file = plugin_data_path / "config.json"
        data_file = plugin_data_path / "data.json"
        
        assert config_file.exists()
        assert data_file.exists()
        
        with open(config_file) as f:
            assert json.load(f) == {"setting": "value"}
        
        with open(data_file) as f:
            assert json.load(f) == {"items": [1, 2, 3]}
    
    def test_restore_plugin_states_no_backups(self, memory_backup_system):
        """Test plugin states restore when no backups exist"""
        backup_date = date(2024, 8, 5)
        
        result = memory_backup_system._restore_plugin_states(backup_date)
        
        assert result is False
    
    def test_restore_file_metadata_success(self, memory_backup_system):
        """Test successful file metadata restore"""
        backup_date = date(2024, 8, 5)
        
        # Create a test database backup
        backup_filename = f"files_metadata_backup_{backup_date.strftime('%Y%m%d')}.db"
        backup_path = memory_backup_system.memory_backup_path / backup_filename
        
        # Create a simple test database
        with sqlite3.connect(str(backup_path)) as conn:
            conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
            conn.execute("INSERT INTO test (name) VALUES ('test_data')")
            conn.commit()
        
        result = memory_backup_system._restore_file_metadata(backup_date)
        
        assert result is True
        
        # Verify database was restored
        file_db_path = memory_backup_system.storage_config.get_path("indexes", "files.db")
        assert file_db_path.exists()
        
        # Verify content
        with sqlite3.connect(str(file_db_path)) as conn:
            cursor = conn.execute("SELECT name FROM test")
            assert cursor.fetchone()[0] == "test_data"
    
    def test_restore_file_metadata_no_backup(self, memory_backup_system):
        """Test file metadata restore when backup doesn't exist"""
        backup_date = date(2024, 8, 5)
        
        result = memory_backup_system._restore_file_metadata(backup_date)
        
        assert result is False
    
    def test_list_available_backups(self, memory_backup_system):
        """Test listing available backups"""
        # Create test backup manifests
        test_backups = [
            {
                "backup_date": "2024-08-03",
                "timestamp": "2024-08-03T12:00:00",
                "success": True,
                "components": {"memory": {"success": True}}
            },
            {
                "backup_date": "2024-08-04",
                "timestamp": "2024-08-04T12:00:00",
                "success": False,
                "components": {"memory": {"success": False}}
            }
        ]
        
        for backup in test_backups:
            date_str = backup["backup_date"].replace("-", "")
            manifest_path = memory_backup_system.memory_backup_path / f"backup_manifest_{date_str}.json"
            with open(manifest_path, 'w') as f:
                json.dump(backup, f)
        
        backups = memory_backup_system.list_available_backups()
        
        assert len(backups) == 2
        assert backups[0]["backup_date"] == "2024-08-03"
        assert backups[0]["success"] is True
        assert backups[1]["backup_date"] == "2024-08-04"
        assert backups[1]["success"] is False
    
    def test_list_available_backups_empty(self, memory_backup_system):
        """Test listing backups when none exist"""
        backups = memory_backup_system.list_available_backups()
        
        assert len(backups) == 0
    
    def test_cleanup_old_backups(self, memory_backup_system):
        """Test cleaning up old backup files"""
        # Create test backup files with different dates
        old_date = date.today() - timedelta(days=40)
        recent_date = date.today() - timedelta(days=10)
        
        old_files = [
            f"memory_backup_{old_date.strftime('%Y%m%d')}.db",
            f"config_backup_{old_date.strftime('%Y%m%d')}.json"
        ]
        
        recent_files = [
            f"memory_backup_{recent_date.strftime('%Y%m%d')}.db",
            f"config_backup_{recent_date.strftime('%Y%m%d')}.json"
        ]
        
        # Create the files
        for filename in old_files + recent_files:
            (memory_backup_system.memory_backup_path / filename).write_text("test data")
        
        result = memory_backup_system.cleanup_old_backups(keep_days=30)
        
        assert result["success"] is True
        assert result["cleaned_count"] == 2  # Should clean up 2 old files
        
        # Verify old files were deleted
        for filename in old_files:
            assert not (memory_backup_system.memory_backup_path / filename).exists()
        
        # Verify recent files were kept
        for filename in recent_files:
            assert (memory_backup_system.memory_backup_path / filename).exists()
    
    def test_cleanup_old_backups_no_files(self, memory_backup_system):
        """Test cleanup when no backup files exist"""
        result = memory_backup_system.cleanup_old_backups()
        
        assert result["success"] is True
        assert result["cleaned_count"] == 0
    
    def test_cleanup_old_backups_invalid_filenames(self, memory_backup_system):
        """Test cleanup with files that don't match expected pattern"""
        # Create files with invalid date patterns
        invalid_files = [
            "memory_backup_invalid.db",
            "config_backup_.json",
            "not_a_backup_file.txt"
        ]
        
        for filename in invalid_files:
            (memory_backup_system.memory_backup_path / filename).write_text("test data")
        
        result = memory_backup_system.cleanup_old_backups()
        
        assert result["success"] is True
        assert result["cleaned_count"] == 0  # Should skip invalid files
        
        # Files should still exist
        for filename in invalid_files:
            assert (memory_backup_system.memory_backup_path / filename).exists()


class TestErrorHandling:
    """Test error handling and edge cases"""
    
    @patch('shutil.copy2')
    def test_backup_memory_database_copy_error(self, mock_copy, memory_backup_system, mock_memory_db):
        """Test handling file copy errors during memory database backup"""
        # Set up memory database
        memory_db_path = memory_backup_system.storage_config.project_root / "database" / "memory.db"
        memory_db_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(mock_memory_db, memory_db_path)
        
        # Mock copy to raise an error
        mock_copy.side_effect = PermissionError("Permission denied")
        
        backup_date = date(2024, 8, 5)
        result = memory_backup_system._backup_memory_database(backup_date)
        
        assert result["success"] is False
        assert "Permission denied" in result["message"]
    
    @patch('builtins.open', side_effect=PermissionError("Permission denied"))
    def test_create_backup_manifest_error(self, mock_open, memory_backup_system):
        """Test handling errors during manifest creation"""
        backup_date = date(2024, 8, 5)
        backup_info = {"test": "data"}
        
        with patch.object(memory_backup_system.logger, 'error') as mock_error:
            memory_backup_system._create_backup_manifest(backup_date, backup_info)
            mock_error.assert_called_once()
    
    def test_create_daily_backup_with_exception(self, memory_backup_system):
        """Test daily backup when an exception occurs"""
        backup_date = date(2024, 8, 5)
        
        with patch.object(memory_backup_system, '_backup_memory_database', 
                         side_effect=Exception("Test error")):
            result = memory_backup_system.create_daily_backup(backup_date)
            
            assert result["success"] is False
            assert len(result["errors"]) > 0
            assert "Test error" in result["errors"][0]
    
    @patch('json.load', side_effect=json.JSONDecodeError("Invalid JSON", "", 0))
    def test_restore_from_backup_corrupt_manifest(self, mock_json_load, memory_backup_system):
        """Test restore when backup manifest is corrupted"""
        backup_date = date(2024, 8, 5)
        
        # Create a corrupt manifest file
        manifest_path = memory_backup_system.memory_backup_path / "backup_manifest_20240805.json"
        manifest_path.write_text("{ corrupt json }")
        
        result = memory_backup_system.restore_from_backup(backup_date)
        
        assert result["success"] is False
        assert len(result["errors"]) > 0
    
    @patch.object(MemoryBackupSystem, '_restore_plugin_states', 
                  side_effect=Exception("Plugin restore error"))
    def test_restore_with_component_failure(self, mock_restore_plugins, memory_backup_system):
        """Test restore when one component fails"""
        backup_date = date(2024, 8, 5)
        
        # Create a valid manifest
        backup_info = {
            "backup_date": "2024-08-05",
            "success": True,
            "components": {"plugins": {"success": True}}
        }
        
        manifest_path = memory_backup_system.memory_backup_path / "backup_manifest_20240805.json"
        with open(manifest_path, 'w') as f:
            json.dump(backup_info, f)
        
        result = memory_backup_system.restore_from_backup(backup_date)
        
        # Should still succeed overall, just with fewer components restored
        assert result["success"] is True
        assert result["components_restored"] < 3  # Less than all components