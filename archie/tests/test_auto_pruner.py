"""
Unit tests for auto_pruner module
"""
import pytest
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

from archie_core.auto_pruner import AutoPruner
from archie_core.file_manager import FileMetadata


class TestAutoPruner:
    """Test the AutoPruner class"""
    
    def test_init(self, auto_pruner):
        """Test initialization of auto pruner"""
        assert auto_pruner.file_manager is not None
        assert auto_pruner.storage_config is not None
        assert auto_pruner.logger is not None
        
        # Check default pruning rules
        expected_rules = {
            "uploads_to_cold_days": 90,
            "temp_cleanup_days": 7,
            "backup_retention_days": 30,
        }
        assert auto_pruner.pruning_rules == expected_rules
    
    def test_run_auto_prune_success(self, auto_pruner):
        """Test successful auto-pruning run"""
        with patch.object(auto_pruner, '_move_old_uploads_to_cold') as mock_cold, \
             patch.object(auto_pruner, '_cleanup_temp_files') as mock_temp, \
             patch.object(auto_pruner, '_cleanup_old_thumbnails') as mock_thumb:
            
            # Mock successful results
            mock_cold.return_value = {"moved_count": 5, "errors": []}
            mock_temp.return_value = {"cleaned_count": 3, "errors": []}
            mock_thumb.return_value = {"cleaned_count": 2, "errors": []}
            
            result = auto_pruner.run_auto_prune()
            
            assert result["success"] is True
            assert "timestamp" in result
            assert "actions" in result
            assert len(result["errors"]) == 0
            
            # Check that all cleanup methods were called
            mock_cold.assert_called_once()
            mock_temp.assert_called_once()
            mock_thumb.assert_called_once()
            
            # Check action results
            assert result["actions"]["uploads_to_cold"]["moved_count"] == 5
            assert result["actions"]["temp_cleanup"]["cleaned_count"] == 3
            assert result["actions"]["thumbnail_cleanup"]["cleaned_count"] == 2
    
    def test_run_auto_prune_with_errors(self, auto_pruner):
        """Test auto-pruning with errors"""
        with patch.object(auto_pruner, '_move_old_uploads_to_cold', 
                         side_effect=Exception("Test error")):
            
            result = auto_pruner.run_auto_prune()
            
            assert result["success"] is False
            assert len(result["errors"]) > 0
            assert "Test error" in result["errors"][0]
    
    def test_move_old_uploads_to_cold_no_files(self, auto_pruner):
        """Test moving uploads to cold when no files exist"""
        with patch.object(auto_pruner.file_manager, 'search_files', return_value=[]):
            result = auto_pruner._move_old_uploads_to_cold()
            
            assert result["moved_count"] == 0
            assert len(result["errors"]) == 0
    
    def test_move_old_uploads_to_cold_with_old_files(self, auto_pruner):
        """Test moving old uploads to cold storage"""
        # Create mock file metadata for old files
        old_date = datetime.now() - timedelta(days=100)  # Older than 90 days
        recent_date = datetime.now() - timedelta(days=30)  # Newer than 90 days
        
        old_file = FileMetadata(
            filename="old_file.txt",
            created_at=old_date,
            storage_tier="uploads"
        )
        
        recent_file = FileMetadata(
            filename="recent_file.txt", 
            created_at=recent_date,
            storage_tier="uploads"
        )
        
        mock_files = [old_file, recent_file]
        
        with patch.object(auto_pruner.file_manager, 'search_files', return_value=mock_files):
            result = auto_pruner._move_old_uploads_to_cold()
            
            assert result["moved_count"] == 1  # Only the old file should be moved
            assert len(result["errors"]) == 0
    
    def test_move_old_uploads_to_cold_with_string_dates(self, auto_pruner):
        """Test moving uploads with string-format created_at dates"""
        old_date_str = (datetime.now() - timedelta(days=100)).isoformat()
        
        old_file = FileMetadata(
            filename="old_file.txt",
            created_at=old_date_str,  # String format
            storage_tier="uploads"
        )
        
        with patch.object(auto_pruner.file_manager, 'search_files', return_value=[old_file]):
            result = auto_pruner._move_old_uploads_to_cold()
            
            assert result["moved_count"] == 1
    
    def test_move_old_uploads_to_cold_with_errors(self, auto_pruner):
        """Test handling errors during upload-to-cold movement"""
        # Create a file that will cause an error during processing
        bad_file = FileMetadata(
            filename="bad_file.txt",
            created_at="invalid_date_format",  # This will cause an error
            storage_tier="uploads"
        )
        
        with patch.object(auto_pruner.file_manager, 'search_files', return_value=[bad_file]):
            result = auto_pruner._move_old_uploads_to_cold()
            
            assert result["moved_count"] == 0
            assert len(result["errors"]) > 0
            assert "bad_file.txt" in result["errors"][0]
    
    def test_cleanup_temp_files_no_temp_dir(self, auto_pruner):
        """Test temp file cleanup when temp directory doesn't exist"""
        with patch.object(auto_pruner.storage_config, 'get_path') as mock_get_path:
            mock_path = MagicMock()
            mock_path.exists.return_value = False
            mock_get_path.return_value = mock_path
            
            result = auto_pruner._cleanup_temp_files()
            
            assert result["cleaned_count"] == 0
            assert len(result["errors"]) == 0
    
    def test_cleanup_temp_files_with_old_files(self, auto_pruner, temp_storage_root):
        """Test temp file cleanup with actual old files"""
        # Create temp directory with old files
        temp_dir = temp_storage_root / "temp"
        temp_dir.mkdir(exist_ok=True)
        
        # Create old and recent temp files
        old_file = temp_dir / "old_temp.tmp"
        recent_file = temp_dir / "recent_temp.tmp"
        
        old_file.write_text("old temp content")
        recent_file.write_text("recent temp content")
        
        # Set file modification times
        old_time = (datetime.now() - timedelta(days=10)).timestamp()  # Older than 7 days
        recent_time = (datetime.now() - timedelta(days=2)).timestamp()  # Newer than 7 days
        
        old_file.touch(times=(old_time, old_time))
        recent_file.touch(times=(recent_time, recent_time))
        
        with patch.object(auto_pruner.storage_config, 'get_path', return_value=temp_dir):
            result = auto_pruner._cleanup_temp_files()
            
            assert result["cleaned_count"] == 1  # Only old file should be cleaned
            assert len(result["errors"]) == 0
            
            # Verify old file was deleted, recent file remains
            assert not old_file.exists()
            assert recent_file.exists()
    
    def test_cleanup_temp_files_with_permission_error(self, auto_pruner, temp_storage_root):
        """Test temp file cleanup with permission errors"""
        temp_dir = temp_storage_root / "temp"
        temp_dir.mkdir(exist_ok=True)
        
        # Create a temp file
        temp_file = temp_dir / "temp.tmp"
        temp_file.write_text("temp content")
        
        # Set old modification time
        old_time = (datetime.now() - timedelta(days=10)).timestamp()
        temp_file.touch(times=(old_time, old_time))
        
        with patch.object(auto_pruner.storage_config, 'get_path', return_value=temp_dir), \
             patch.object(Path, 'unlink', side_effect=PermissionError("Permission denied")):
            
            result = auto_pruner._cleanup_temp_files()
            
            assert result["cleaned_count"] == 0
            assert len(result["errors"]) > 0
            assert "Permission denied" in result["errors"][0]
    
    def test_cleanup_old_thumbnails_no_thumbs_dir(self, auto_pruner):
        """Test thumbnail cleanup when thumbnails directory doesn't exist"""
        with patch.object(auto_pruner.storage_config, 'get_path') as mock_get_path:
            mock_path = MagicMock()
            mock_path.exists.return_value = False
            mock_get_path.return_value = mock_path
            
            result = auto_pruner._cleanup_old_thumbnails()
            
            assert result["cleaned_count"] == 0
            assert len(result["errors"]) == 0
    
    def test_cleanup_old_thumbnails_with_old_files(self, auto_pruner, temp_storage_root):
        """Test thumbnail cleanup with actual old files"""
        # Create thumbnails directory with old files
        thumbs_dir = temp_storage_root / "thumbnails"
        thumbs_dir.mkdir(exist_ok=True)
        
        # Create old and recent thumbnail files
        old_thumb = thumbs_dir / "old_thumb.jpg"
        recent_thumb = thumbs_dir / "recent_thumb.jpg"
        
        old_thumb.write_text("old thumbnail")
        recent_thumb.write_text("recent thumbnail")
        
        # Set file modification times (thumbnails use 30-day cutoff)
        old_time = (datetime.now() - timedelta(days=35)).timestamp()  # Older than 30 days
        recent_time = (datetime.now() - timedelta(days=15)).timestamp()  # Newer than 30 days
        
        old_thumb.touch(times=(old_time, old_time))
        recent_thumb.touch(times=(recent_time, recent_time))
        
        with patch.object(auto_pruner.storage_config, 'get_path', return_value=thumbs_dir):
            result = auto_pruner._cleanup_old_thumbnails()
            
            assert result["cleaned_count"] == 1  # Only old thumbnail should be cleaned
            assert len(result["errors"]) == 0
            
            # Verify old thumbnail was deleted, recent remains
            assert not old_thumb.exists()
            assert recent_thumb.exists()
    
    def test_get_pruning_stats_no_files(self, auto_pruner):
        """Test getting pruning stats when no files exist"""
        with patch.object(auto_pruner.file_manager, 'search_files', return_value=[]), \
             patch.object(auto_pruner.file_manager, 'get_storage_stats', 
                         return_value={"database": {"total_files": 0}}):
            
            stats = auto_pruner.get_pruning_stats()
            
            assert stats["uploads_eligible_for_cold"] == 0
            assert stats["temp_files_to_cleanup"] == 0
            assert stats["old_thumbnails"] == 0
            assert stats["total_files_tracked"] == 0
    
    def test_get_pruning_stats_with_eligible_files(self, auto_pruner):
        """Test getting pruning stats with files eligible for pruning"""
        # Create mock files - some old, some recent
        old_date = datetime.now() - timedelta(days=100)
        recent_date = datetime.now() - timedelta(days=30)
        
        old_files = [
            FileMetadata(filename=f"old_{i}.txt", created_at=old_date, storage_tier="uploads")
            for i in range(3)
        ]
        recent_files = [
            FileMetadata(filename=f"recent_{i}.txt", created_at=recent_date, storage_tier="uploads")
            for i in range(2)
        ]
        
        all_files = old_files + recent_files
        
        with patch.object(auto_pruner.file_manager, 'search_files', return_value=all_files), \
             patch.object(auto_pruner.file_manager, 'get_storage_stats', 
                         return_value={"database": {"total_files": 5}}):
            
            stats = auto_pruner.get_pruning_stats()
            
            assert stats["uploads_eligible_for_cold"] == 3  # Only old files
            assert stats["total_files_tracked"] == 5
    
    def test_get_pruning_stats_with_temp_files(self, auto_pruner, temp_storage_root):
        """Test getting pruning stats with temp files to clean"""
        temp_dir = temp_storage_root / "temp"
        temp_dir.mkdir(exist_ok=True)
        
        # Create old temp files
        for i in range(4):
            temp_file = temp_dir / f"old_temp_{i}.tmp"
            temp_file.write_text("temp content")
            old_time = (datetime.now() - timedelta(days=10)).timestamp()
            temp_file.touch(times=(old_time, old_time))
        
        with patch.object(auto_pruner.storage_config, 'get_path', return_value=temp_dir), \
             patch.object(auto_pruner.file_manager, 'search_files', return_value=[]), \
             patch.object(auto_pruner.file_manager, 'get_storage_stats', 
                         return_value={"database": {"total_files": 0}}):
            
            stats = auto_pruner.get_pruning_stats()
            
            assert stats["temp_files_to_cleanup"] == 4
    
    def test_get_pruning_stats_with_errors(self, auto_pruner):
        """Test getting pruning stats when errors occur"""
        with patch.object(auto_pruner.file_manager, 'search_files', 
                         side_effect=Exception("Search failed")):
            
            stats = auto_pruner.get_pruning_stats()
            
            # Should return default values even with errors
            assert stats["uploads_eligible_for_cold"] == 0
            assert stats["temp_files_to_cleanup"] == 0
            assert stats["old_thumbnails"] == 0
            assert stats["total_files_tracked"] == 0
    
    def test_update_pruning_rules_valid(self, auto_pruner):
        """Test updating pruning rules with valid values"""
        new_rules = {
            "uploads_to_cold_days": 120,
            "temp_cleanup_days": 14
        }
        
        result = auto_pruner.update_pruning_rules(new_rules)
        
        assert result is True
        assert auto_pruner.pruning_rules["uploads_to_cold_days"] == 120
        assert auto_pruner.pruning_rules["temp_cleanup_days"] == 14
        assert auto_pruner.pruning_rules["backup_retention_days"] == 30  # Unchanged
    
    def test_update_pruning_rules_invalid_keys(self, auto_pruner):
        """Test updating pruning rules with invalid keys"""
        original_rules = auto_pruner.pruning_rules.copy()
        
        new_rules = {
            "invalid_rule": 100,
            "uploads_to_cold_days": 120  # This should still be applied
        }
        
        result = auto_pruner.update_pruning_rules(new_rules)
        
        assert result is True
        assert auto_pruner.pruning_rules["uploads_to_cold_days"] == 120
        assert "invalid_rule" not in auto_pruner.pruning_rules
    
    def test_update_pruning_rules_invalid_values(self, auto_pruner):
        """Test updating pruning rules with invalid values"""
        original_rules = auto_pruner.pruning_rules.copy()
        
        new_rules = {
            "uploads_to_cold_days": -1,    # Negative value should be ignored
            "temp_cleanup_days": "invalid"  # Non-integer should be ignored
        }
        
        result = auto_pruner.update_pruning_rules(new_rules)
        
        assert result is True
        # Rules should remain unchanged
        assert auto_pruner.pruning_rules == original_rules
    
    def test_update_pruning_rules_exception(self, auto_pruner):
        """Test handling exceptions during rule updates"""
        with patch.object(auto_pruner.logger, 'error') as mock_error:
            # Pass something that will cause an error during iteration
            result = auto_pruner.update_pruning_rules(None)
            
            assert result is False
            mock_error.assert_called_once()
    
    def test_get_pruning_rules(self, auto_pruner):
        """Test getting current pruning rules"""
        rules = auto_pruner.get_pruning_rules()
        
        expected_rules = {
            "uploads_to_cold_days": 90,
            "temp_cleanup_days": 7,
            "backup_retention_days": 30,
        }
        
        assert rules == expected_rules
        
        # Verify it returns a copy (not the original)
        rules["uploads_to_cold_days"] = 999
        assert auto_pruner.pruning_rules["uploads_to_cold_days"] == 90


class TestEdgeCasesAndErrorHandling:
    """Test edge cases and error handling"""
    
    def test_cleanup_temp_files_nested_directories(self, auto_pruner, temp_storage_root):
        """Test temp file cleanup with nested directory structure"""
        temp_dir = temp_storage_root / "temp"
        nested_dir = temp_dir / "subdir" / "nested"
        nested_dir.mkdir(parents=True, exist_ok=True)
        
        # Create old files in nested directories
        old_file1 = temp_dir / "root_old.tmp"
        old_file2 = nested_dir / "nested_old.tmp"
        
        old_file1.write_text("root content")
        old_file2.write_text("nested content")
        
        # Set old modification times
        old_time = (datetime.now() - timedelta(days=10)).timestamp()
        old_file1.touch(times=(old_time, old_time))
        old_file2.touch(times=(old_time, old_time))
        
        with patch.object(auto_pruner.storage_config, 'get_path', return_value=temp_dir):
            result = auto_pruner._cleanup_temp_files()
            
            assert result["cleaned_count"] == 2  # Both files should be found and cleaned
            assert len(result["errors"]) == 0
    
    def test_move_old_uploads_iso_format_with_z_suffix(self, auto_pruner):
        """Test handling ISO format dates with Z suffix"""
        old_date_str = (datetime.now() - timedelta(days=100)).isoformat() + "Z"
        
        old_file = FileMetadata(
            filename="old_file.txt",
            created_at=old_date_str,
            storage_tier="uploads"
        )
        
        with patch.object(auto_pruner.file_manager, 'search_files', return_value=[old_file]):
            result = auto_pruner._move_old_uploads_to_cold()
            
            assert result["moved_count"] == 1
            assert len(result["errors"]) == 0
    
    def test_get_pruning_stats_with_bad_dates(self, auto_pruner):
        """Test pruning stats calculation with files that have bad date formats"""
        bad_files = [
            FileMetadata(filename="bad1.txt", created_at="invalid_date", storage_tier="uploads"),
            FileMetadata(filename="bad2.txt", created_at=None, storage_tier="uploads"),
            FileMetadata(filename="good.txt", created_at=datetime.now() - timedelta(days=100), storage_tier="uploads")
        ]
        
        with patch.object(auto_pruner.file_manager, 'search_files', return_value=bad_files), \
             patch.object(auto_pruner.file_manager, 'get_storage_stats', 
                         return_value={"database": {"total_files": 3}}):
            
            stats = auto_pruner.get_pruning_stats()
            
            # Should handle bad dates gracefully and only count the good file
            assert stats["uploads_eligible_for_cold"] == 1
            assert stats["total_files_tracked"] == 3
    
    def test_cleanup_with_readonly_files(self, auto_pruner, temp_storage_root):
        """Test cleanup behavior with read-only files"""
        temp_dir = temp_storage_root / "temp"
        temp_dir.mkdir(exist_ok=True)
        
        readonly_file = temp_dir / "readonly.tmp"
        readonly_file.write_text("readonly content")
        
        # Set old modification time
        old_time = (datetime.now() - timedelta(days=10)).timestamp()
        readonly_file.touch(times=(old_time, old_time))
        
        # Make file read-only
        readonly_file.chmod(0o444)
        
        with patch.object(auto_pruner.storage_config, 'get_path', return_value=temp_dir):
            result = auto_pruner._cleanup_temp_files()
            
            # Should handle permission errors gracefully
            if result["cleaned_count"] == 0:
                assert len(result["errors"]) > 0
            # If cleanup succeeded, that's also fine (depends on OS permissions)