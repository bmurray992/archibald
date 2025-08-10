"""
Unit tests for file_manager module
"""
import pytest
import sqlite3
import io
import hashlib
import tempfile
import json
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, mock_open, MagicMock

from archie_core.file_manager import (
    ArchieFileManager,
    FileMetadata
)


class TestFileMetadata:
    """Test the FileMetadata class"""
    
    def test_file_metadata_creation_minimal(self):
        """Test FileMetadata creation with minimal parameters"""
        metadata = FileMetadata()
        
        assert metadata.filename == ''
        assert metadata.original_name == ''
        assert metadata.file_path == ''
        assert metadata.file_size == 0
        assert metadata.mime_type == ''
        assert metadata.file_hash == ''
        assert isinstance(metadata.created_at, datetime)
        assert isinstance(metadata.modified_at, datetime)
        assert metadata.tags == []
        assert metadata.plugin_source == ''
        assert metadata.storage_tier == 'uploads'
        assert metadata.archived is False
        assert metadata.description == ''
        assert metadata.metadata == {}
    
    def test_file_metadata_creation_full(self):
        """Test FileMetadata creation with all parameters"""
        test_time = datetime(2024, 8, 5, 12, 0, 0)
        test_metadata = {'custom': 'data', 'version': 1}
        
        metadata = FileMetadata(
            filename='test.txt',
            original_name='original.txt',
            file_path='/path/to/file',
            file_size=1024,
            mime_type='text/plain',
            file_hash='abc123',
            created_at=test_time,
            modified_at=test_time,
            tags=['test', 'document'],
            plugin_source='test_plugin',
            storage_tier='media',
            archived=True,
            description='Test file',
            metadata=test_metadata
        )
        
        assert metadata.filename == 'test.txt'
        assert metadata.original_name == 'original.txt'
        assert metadata.file_path == '/path/to/file'
        assert metadata.file_size == 1024
        assert metadata.mime_type == 'text/plain'
        assert metadata.file_hash == 'abc123'
        assert metadata.created_at == test_time
        assert metadata.modified_at == test_time
        assert metadata.tags == ['test', 'document']
        assert metadata.plugin_source == 'test_plugin'
        assert metadata.storage_tier == 'media'
        assert metadata.archived is True
        assert metadata.description == 'Test file'
        assert metadata.metadata == test_metadata


class TestArchieFileManager:
    """Test the ArchieFileManager class"""
    
    def test_init_creates_database(self, file_manager):
        """Test that initialization creates the database and tables"""
        assert file_manager.db_path.exists()
        
        with sqlite3.connect(str(file_manager.db_path)) as conn:
            # Check that tables exist
            cursor = conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name IN ('files', 'file_tags')
            """)
            tables = [row[0] for row in cursor.fetchall()]
            
            assert 'files' in tables
            assert 'file_tags' in tables
            
            # Check that indexes exist
            cursor = conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='index' AND name LIKE 'idx_%'
            """)
            indexes = [row[0] for row in cursor.fetchall()]
            
            expected_indexes = ['idx_files_hash', 'idx_files_created_at', 
                              'idx_files_plugin', 'idx_tags_tag']
            for expected_idx in expected_indexes:
                assert expected_idx in indexes
    
    def test_calculate_file_hash(self, file_manager, sample_text_file):
        """Test file hash calculation"""
        file_hash = file_manager.calculate_file_hash(sample_text_file)
        
        # Verify it's a valid SHA-256 hash
        assert len(file_hash) == 64
        assert all(c in '0123456789abcdef' for c in file_hash.lower())
        
        # Verify it's consistent
        file_hash2 = file_manager.calculate_file_hash(sample_text_file)
        assert file_hash == file_hash2
        
        # Verify it matches manual calculation
        with open(sample_text_file, 'rb') as f:
            content = f.read()
        
        expected_hash = hashlib.sha256(content).hexdigest()
        assert file_hash == expected_hash
    
    def test_store_file_basic(self, file_manager, sample_file_content):
        """Test basic file storage"""
        content_io = io.BytesIO(sample_file_content)
        
        filename, metadata = file_manager.store_file(
            file_content=content_io,
            original_filename='test.txt'
        )
        
        assert filename.startswith('test_')
        assert filename.endswith('.txt')
        assert isinstance(metadata, FileMetadata)
        assert metadata.original_name == 'test.txt'
        assert metadata.file_size == len(sample_file_content)
        assert metadata.mime_type == 'text/plain'
        assert metadata.storage_tier == 'uploads'
        assert metadata.plugin_source == ''
        assert metadata.tags == []
        assert metadata.description == ''
        assert metadata.metadata == {}
        
        # Verify file was actually written
        file_path = Path(metadata.file_path)
        assert file_path.exists()
        assert file_path.read_bytes() == sample_file_content
    
    def test_store_file_with_metadata(self, file_manager, sample_file_content):
        """Test file storage with all metadata"""
        content_io = io.BytesIO(sample_file_content)
        
        filename, metadata = file_manager.store_file(
            file_content=content_io,
            original_filename='test.txt',
            storage_tier='media',
            plugin_source='test_plugin',
            tags=['test', 'document', 'important'],
            description='A test document',
            metadata={'version': 1, 'author': 'test'}
        )
        
        assert metadata.storage_tier == 'media'
        assert metadata.plugin_source == 'test_plugin'
        assert metadata.tags == ['test', 'document', 'important']
        assert metadata.description == 'A test document'
        assert metadata.metadata == {'version': 1, 'author': 'test'}
        
        # Verify file was stored in correct tier
        assert 'media' in metadata.file_path
    
    def test_store_file_duplicate_detection(self, file_manager, sample_file_content):
        """Test that duplicate files are detected and not stored twice"""
        content_io1 = io.BytesIO(sample_file_content)
        content_io2 = io.BytesIO(sample_file_content)
        
        # Store first file
        filename1, metadata1 = file_manager.store_file(
            file_content=content_io1,
            original_filename='test1.txt'
        )
        
        # Store identical content with different name
        filename2, metadata2 = file_manager.store_file(
            file_content=content_io2,
            original_filename='test2.txt'
        )
        
        # Should return the same file
        assert filename2 == filename1
        assert metadata2.file_hash == metadata1.file_hash
        assert metadata2.file_path == metadata1.file_path
    
    def test_store_file_special_characters(self, file_manager, sample_file_content):
        """Test file storage with special characters in filename"""
        content_io = io.BytesIO(sample_file_content)
        
        filename, metadata = file_manager.store_file(
            file_content=content_io,
            original_filename='test file with spaces & symbols!@#.txt'
        )
        
        # Filename should be sanitized
        assert 'test file with spaces' in filename
        assert '&' not in filename
        assert '!' not in filename
        assert '@' not in filename
        assert '#' not in filename
        assert filename.endswith('.txt')
    
    def test_save_file_metadata(self, file_manager):
        """Test saving file metadata to database"""
        metadata = FileMetadata(
            filename='test.txt',
            original_name='original.txt',
            file_path='/path/to/file.txt',
            file_size=1024,
            mime_type='text/plain',
            file_hash='abc123def456',
            plugin_source='test_plugin',
            storage_tier='uploads',
            archived=False,
            description='Test file',
            tags=['test', 'document'],
            metadata={'version': 1}
        )
        
        file_id = file_manager.save_file_metadata(metadata)
        
        assert isinstance(file_id, int)
        assert file_id > 0
        
        # Verify data was saved
        with sqlite3.connect(str(file_manager.db_path)) as conn:
            cursor = conn.execute("SELECT * FROM files WHERE id = ?", (file_id,))
            row = cursor.fetchone()
            
            assert row is not None
            assert row[1] == 'test.txt'  # filename
            assert row[2] == 'original.txt'  # original_name
            assert row[3] == '/path/to/file.txt'  # file_path
            assert row[4] == 1024  # file_size
            assert row[5] == 'text/plain'  # mime_type
            assert row[6] == 'abc123def456'  # file_hash
            
            # Check tags were saved
            cursor = conn.execute("SELECT tag FROM file_tags WHERE file_id = ?", (file_id,))
            tags = [row[0] for row in cursor.fetchall()]
            assert set(tags) == {'test', 'document'}
    
    def test_get_file_by_hash(self, populated_storage):
        """Test retrieving file by hash"""
        # Get a file we know exists
        recent_files = populated_storage.get_recent_files(limit=1)
        assert len(recent_files) > 0
        
        test_file = recent_files[0]
        
        # Retrieve by hash
        found_file = populated_storage.get_file_by_hash(test_file.file_hash)
        
        assert found_file is not None
        assert found_file.file_hash == test_file.file_hash
        assert found_file.filename == test_file.filename
    
    def test_get_file_by_hash_not_found(self, file_manager):
        """Test retrieving non-existent file by hash"""
        fake_hash = 'nonexistent' + '0' * 54  # 64 char hash
        
        result = file_manager.get_file_by_hash(fake_hash)
        
        assert result is None
    
    def test_get_file_by_filename(self, populated_storage):
        """Test retrieving file by filename"""
        # Get a file we know exists
        recent_files = populated_storage.get_recent_files(limit=1)
        assert len(recent_files) > 0
        
        test_file = recent_files[0]
        
        # Retrieve by filename
        found_file = populated_storage.get_file_by_filename(test_file.filename)
        
        assert found_file is not None
        assert found_file.filename == test_file.filename
        assert found_file.file_hash == test_file.file_hash
    
    def test_search_files_by_query(self, populated_storage):
        """Test searching files by text query"""
        results = populated_storage.search_files(query='test')
        
        assert len(results) > 0
        # All results should contain 'test' in filename, original name, or description
        for result in results:
            found = ('test' in result.filename.lower() or 
                    'test' in result.original_name.lower() or
                    'test' in result.description.lower())
            assert found
    
    def test_search_files_by_tags(self, populated_storage):
        """Test searching files by tags"""
        results = populated_storage.search_files(tags=['json'])
        
        assert len(results) > 0
        # All results should have the 'json' tag
        for result in results:
            assert 'json' in result.tags
    
    def test_search_files_by_plugin(self, populated_storage):
        """Test searching files by plugin source"""
        results = populated_storage.search_files(plugin_source='test_plugin')
        
        assert len(results) > 0
        # All results should be from test_plugin
        for result in results:
            assert result.plugin_source == 'test_plugin'
    
    def test_search_files_by_storage_tier(self, populated_storage):
        """Test searching files by storage tier"""
        results = populated_storage.search_files(storage_tier='uploads')
        
        assert len(results) > 0
        # All results should be in uploads tier
        for result in results:
            assert result.storage_tier == 'uploads'
    
    def test_search_files_combined_criteria(self, populated_storage):
        """Test searching files with multiple criteria"""
        results = populated_storage.search_files(
            query='test',
            tags=['test'],
            plugin_source='test_plugin'
        )
        
        assert len(results) > 0
        # Results should match all criteria
        for result in results:
            assert 'test' in result.filename.lower() or 'test' in result.description.lower()
            assert 'test' in result.tags
            assert result.plugin_source == 'test_plugin'
    
    def test_search_files_limit(self, populated_storage):
        """Test search result limiting"""
        results = populated_storage.search_files(limit=1)
        
        assert len(results) <= 1
    
    def test_get_recent_files(self, populated_storage):
        """Test getting recently uploaded files"""
        results = populated_storage.get_recent_files(limit=2)
        
        assert len(results) <= 2
        # Results should be sorted by creation time (newest first)
        if len(results) > 1:
            assert results[0].created_at >= results[1].created_at
    
    def test_get_files_by_plugin(self, populated_storage):
        """Test getting files by plugin"""
        results = populated_storage.get_files_by_plugin('test_plugin')
        
        assert len(results) > 0
        for result in results:
            assert result.plugin_source == 'test_plugin'
    
    def test_move_to_cold_storage(self, populated_storage):
        """Test moving file to cold storage"""
        # Get a file to move
        recent_files = populated_storage.get_recent_files(limit=1)
        assert len(recent_files) > 0
        
        test_file = recent_files[0]
        original_path = Path(test_file.file_path)
        
        # Get file ID from database
        with sqlite3.connect(str(populated_storage.db_path)) as conn:
            cursor = conn.execute("SELECT id FROM files WHERE filename = ?", (test_file.filename,))
            file_id = cursor.fetchone()[0]
        
        # Move to cold storage
        success = populated_storage.move_to_cold_storage(file_id)
        
        assert success is True
        
        # Verify file was moved
        assert not original_path.exists()
        
        # Verify database was updated
        updated_file = populated_storage.get_file_by_filename(test_file.filename)
        assert updated_file.storage_tier == 'cold'
        assert bool(updated_file.archived) is True  # SQLite returns 1 for TRUE
        assert 'cold' in updated_file.file_path
        
        # Verify new file exists
        new_path = Path(updated_file.file_path)
        assert new_path.exists()
    
    def test_move_to_cold_storage_nonexistent_file(self, file_manager):
        """Test moving non-existent file to cold storage"""
        success = file_manager.move_to_cold_storage(99999)
        
        assert success is False
    
    def test_delete_file(self, populated_storage):
        """Test deleting a file"""
        # Get a file to delete
        recent_files = populated_storage.get_recent_files(limit=1)
        assert len(recent_files) > 0
        
        test_file = recent_files[0]
        original_path = Path(test_file.file_path)
        
        # Delete the file
        success = populated_storage.delete_file(test_file.filename)
        
        assert success is True
        
        # Verify file was deleted from filesystem
        assert not original_path.exists()
        
        # Verify file was deleted from database
        deleted_file = populated_storage.get_file_by_filename(test_file.filename)
        assert deleted_file is None
    
    def test_delete_file_nonexistent(self, file_manager):
        """Test deleting non-existent file"""
        success = file_manager.delete_file('nonexistent.txt')
        
        assert success is False
    
    def test_get_storage_stats(self, populated_storage):
        """Test getting storage statistics"""
        stats = populated_storage.get_storage_stats()
        
        # Should include storage config stats
        assert 'uploads' in stats
        assert 'media' in stats
        
        # Should include database stats
        assert 'database' in stats
        assert 'total_files' in stats['database']
        assert 'total_size' in stats['database']
        assert 'by_tier' in stats['database']
        
        # Should have some files from populated storage
        assert stats['database']['total_files'] > 0
        assert stats['database']['total_size'] > 0
    
    def test_row_to_metadata_conversion(self, file_manager):
        """Test converting database row to FileMetadata object"""
        # Create a file first
        content_io = io.BytesIO(b'test content')
        filename, original_metadata = file_manager.store_file(
            file_content=content_io,
            original_filename='test.txt',
            tags=['test', 'conversion'],
            metadata={'test': True}
        )
        
        # Get the raw row from database
        with sqlite3.connect(str(file_manager.db_path)) as conn:
            cursor = conn.execute("SELECT * FROM files WHERE filename = ?", (filename,))
            row = cursor.fetchone()
            
            # Convert to metadata
            metadata = file_manager._row_to_metadata(conn, row)
            
            assert isinstance(metadata, FileMetadata)
            assert metadata.filename == filename
            assert metadata.original_name == 'test.txt'
            assert set(metadata.tags) == {'test', 'conversion'}  # Tags may be in different order
            assert metadata.metadata == {'test': True}
    
    def test_row_to_metadata_with_malformed_json(self, file_manager):
        """Test handling malformed JSON in metadata field"""
        # Manually insert a record with malformed JSON
        with sqlite3.connect(str(file_manager.db_path)) as conn:
            cursor = conn.execute("""
                INSERT INTO files (
                    filename, original_name, file_path, file_size, 
                    mime_type, file_hash, plugin_source, storage_tier, 
                    archived, description, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                'test_malformed.txt', 'test.txt', '/path/to/file',
                100, 'text/plain', 'hash123', 'test', 'uploads',
                False, 'Test', 'invalid json {'
            ))
            file_id = cursor.lastrowid
            
            # Get the row
            cursor = conn.execute("SELECT * FROM files WHERE id = ?", (file_id,))
            row = cursor.fetchone()
            
            # Convert to metadata - should handle malformed JSON gracefully
            metadata = file_manager._row_to_metadata(conn, row)
            
            assert metadata.metadata == {}  # Should default to empty dict


class TestEdgeCasesAndErrorHandling:
    """Test edge cases and error handling"""
    
    def test_store_file_empty_content(self, file_manager):
        """Test storing empty file"""
        content_io = io.BytesIO(b'')
        
        filename, metadata = file_manager.store_file(
            file_content=content_io,
            original_filename='empty.txt'
        )
        
        assert metadata.file_size == 0
        assert Path(metadata.file_path).exists()
        assert Path(metadata.file_path).read_bytes() == b''
    
    def test_store_file_no_extension(self, file_manager):
        """Test storing file without extension"""
        content_io = io.BytesIO(b'test content')
        
        filename, metadata = file_manager.store_file(
            file_content=content_io,
            original_filename='noext'
        )
        
        assert not filename.endswith('.')
        assert metadata.original_name == 'noext'
    
    def test_store_file_unknown_mime_type(self, file_manager):
        """Test storing file with unknown extension"""
        content_io = io.BytesIO(b'test content')
        
        filename, metadata = file_manager.store_file(
            file_content=content_io,
            original_filename='test.unknownext'
        )
        
        assert metadata.mime_type == 'application/octet-stream'
    
    def test_search_files_empty_criteria(self, file_manager):
        """Test searching with no criteria"""
        results = file_manager.search_files()
        
        # Should return some results (up to limit)
        assert len(results) <= 50  # default limit
    
    def test_search_files_no_matches(self, file_manager):
        """Test searching with criteria that match nothing"""
        results = file_manager.search_files(query='impossible_to_match_string_12345')
        
        assert len(results) == 0
    
    @patch('archie_core.file_manager.shutil.move')
    def test_move_to_cold_storage_filesystem_error(self, mock_move, populated_storage):
        """Test handling filesystem errors during cold storage move"""
        mock_move.side_effect = PermissionError("Permission denied")
        
        recent_files = populated_storage.get_recent_files(limit=1)
        test_file = recent_files[0]
        
        with sqlite3.connect(str(populated_storage.db_path)) as conn:
            cursor = conn.execute("SELECT id FROM files WHERE filename = ?", (test_file.filename,))
            file_id = cursor.fetchone()[0]
        
        # Should handle the error gracefully
        with pytest.raises(PermissionError):
            populated_storage.move_to_cold_storage(file_id)
    
    def test_calculate_file_hash_large_file(self, file_manager, temp_storage_root):
        """Test hash calculation for large file"""
        large_file = temp_storage_root / "large_file.bin"
        
        # Create a file larger than the chunk size (4096 bytes)
        large_content = b'a' * 10000
        large_file.write_bytes(large_content)
        
        file_hash = file_manager.calculate_file_hash(large_file)
        
        # Verify hash is correct
        expected_hash = hashlib.sha256(large_content).hexdigest()
        assert file_hash == expected_hash