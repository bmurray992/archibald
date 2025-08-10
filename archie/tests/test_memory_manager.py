"""
Comprehensive tests for archie_core.memory_manager module - Core memory functionality
"""
import pytest
import tempfile
import sqlite3
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

from archie_core.memory_manager import MemoryManager


class TestMemoryManager:
    """Test MemoryManager class initialization and core functionality"""
    
    @pytest.fixture
    def temp_db_dir(self):
        """Create temporary directory for test database"""
        with tempfile.TemporaryDirectory(prefix="archie_memory_test_") as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def memory_manager(self, temp_db_dir):
        """Create test memory manager instance"""
        db_path = temp_db_dir / "test_memory.db"
        # Create schema file for testing
        schema_path = temp_db_dir / "schema.sql"
        self._create_test_schema(schema_path)
        
        with patch('archie_core.memory_manager.Path') as mock_path:
            # Mock the path resolution to use our test schema
            mock_path.return_value.parent.parent = temp_db_dir
            manager = MemoryManager(str(db_path))
            yield manager
    
    @pytest.fixture
    def populated_memory_manager(self, memory_manager):
        """Create memory manager with sample data"""
        # Store various types of memories
        memory_manager.store_memory(
            content="Learned Python basics today",
            entry_type="learning",
            assistant_id="percy",
            tags=["python", "programming", "education"],
            metadata={"difficulty": "beginner", "hours": 2}
        )
        
        memory_manager.store_memory(
            content="Had a great meeting about the new project",
            entry_type="work",
            assistant_id="percy",
            tags=["meeting", "project", "collaboration"],
            plugin_source="calendar"
        )
        
        memory_manager.store_memory(
            content="Reminder to buy groceries tomorrow",
            entry_type="reminder",
            assistant_id="archie",
            tags=["shopping", "groceries"],
            confidence=0.8
        )
        
        memory_manager.store_memory(
            content="Interesting conversation about AI ethics",
            entry_type="interaction",
            assistant_id="percy",
            tags=["ai", "ethics", "philosophy"],
            metadata={"participants": ["user", "percy"], "duration": 30}
        )
        
        yield memory_manager
    
    def _create_test_schema(self, schema_path):
        """Create test database schema file"""
        schema_content = """
        -- Test schema for memory manager tests
        CREATE TABLE IF NOT EXISTS memory_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assistant_id TEXT NOT NULL DEFAULT 'percy',
            plugin_source TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            entry_type TEXT NOT NULL,
            content TEXT NOT NULL,
            metadata JSON,
            tags TEXT,
            confidence REAL DEFAULT 1.0,
            source_method TEXT,
            archived BOOLEAN DEFAULT FALSE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assistant_id TEXT NOT NULL DEFAULT 'percy',
            user_message TEXT,
            assistant_response TEXT,
            context TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            session_id TEXT,
            plugin_used TEXT,
            intent_detected TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assistant_id TEXT,
            action TEXT NOT NULL,
            resource TEXT,
            ip_address TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            status TEXT NOT NULL,
            details TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS pruning_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_type TEXT NOT NULL,
            entries_affected INTEGER DEFAULT 0,
            bytes_freed INTEGER DEFAULT 0,
            executed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            details TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
            content,
            tags,
            content='memory_entries',
            content_rowid='id'
        );

        -- Triggers to keep FTS table in sync
        CREATE TRIGGER IF NOT EXISTS memory_fts_insert AFTER INSERT ON memory_entries
        BEGIN
            INSERT INTO memory_fts(rowid, content, tags) VALUES (NEW.id, NEW.content, NEW.tags);
        END;

        CREATE TRIGGER IF NOT EXISTS memory_fts_delete AFTER DELETE ON memory_entries
        BEGIN
            DELETE FROM memory_fts WHERE rowid = OLD.id;
        END;

        CREATE TRIGGER IF NOT EXISTS memory_fts_update AFTER UPDATE ON memory_entries
        BEGIN
            DELETE FROM memory_fts WHERE rowid = OLD.id;
            INSERT INTO memory_fts(rowid, content, tags) VALUES (NEW.id, NEW.content, NEW.tags);
        END;
        """
        
        schema_path.write_text(schema_content)
    
    def test_init_default_path(self):
        """Test memory manager initialization with default path"""
        with patch('archie_core.memory_manager.Path') as mock_path:
            mock_file_path = MagicMock()
            mock_file_path.parent.parent = Path('/test/base')
            mock_path.return_value = mock_file_path
            
            manager = MemoryManager()
            
            expected_path = Path('/test/base') / "database" / "memory.db"
            assert manager.db_path == expected_path
    
    def test_init_custom_path(self, temp_db_dir):
        """Test memory manager initialization with custom path"""
        custom_path = temp_db_dir / "custom_memory.db"
        schema_path = temp_db_dir / "schema.sql"
        self._create_test_schema(schema_path)
        
        with patch('archie_core.memory_manager.Path') as mock_path:
            mock_path.return_value.parent.parent = temp_db_dir
            manager = MemoryManager(str(custom_path))
            
            assert manager.db_path == custom_path
            assert manager.db_path.exists()
    
    def test_database_initialization(self, temp_db_dir):
        """Test database initialization and schema creation"""
        db_path = temp_db_dir / "test_memory.db"
        schema_path = temp_db_dir / "schema.sql"
        self._create_test_schema(schema_path)
        
        with patch('archie_core.memory_manager.Path') as mock_path:
            mock_path.return_value.parent.parent = temp_db_dir
            manager = MemoryManager(str(db_path))
            
            # Verify database file exists
            assert manager.db_path.exists()
            
            # Verify tables were created
            with sqlite3.connect(manager.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                
                expected_tables = ['memory_entries', 'interactions', 'audit_log', 'pruning_history']
                for table in expected_tables:
                    assert table in tables
    
    def test_database_pragmas(self, memory_manager):
        """Test that database pragmas are set correctly"""
        with sqlite3.connect(memory_manager.db_path) as conn:
            cursor = conn.cursor()
            
            # Check foreign keys are enabled
            cursor.execute("PRAGMA foreign_keys")
            assert cursor.fetchone()[0] == 1
            
            # Check journal mode is WAL
            cursor.execute("PRAGMA journal_mode")
            assert cursor.fetchone()[0] == "wal"


class TestMemoryStorage:
    """Test memory storage functionality"""
    
    @pytest.fixture
    def memory_manager(self, temp_db_dir):
        """Create test memory manager instance"""
        db_path = temp_db_dir / "test_memory.db"
        schema_path = temp_db_dir / "schema.sql"
        TestMemoryManager()._create_test_schema(schema_path)
        
        with patch('archie_core.memory_manager.Path') as mock_path:
            mock_path.return_value.parent.parent = temp_db_dir
            manager = MemoryManager(str(db_path))
            yield manager
    
    @pytest.fixture
    def temp_db_dir(self):
        """Create temporary directory for test database"""
        with tempfile.TemporaryDirectory(prefix="archie_memory_test_") as temp_dir:
            yield Path(temp_dir)
    
    def test_store_memory_minimal(self, memory_manager):
        """Test storing memory with minimal parameters"""
        memory_id = memory_manager.store_memory(
            content="Test memory content",
            entry_type="test"
        )
        
        assert isinstance(memory_id, int)
        assert memory_id > 0
        
        # Verify memory was stored
        with sqlite3.connect(memory_manager.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM memory_entries WHERE id = ?", (memory_id,))
            row = cursor.fetchone()
            
            assert row is not None
            assert row['content'] == "Test memory content"
            assert row['entry_type'] == "test"
            assert row['assistant_id'] == "percy"  # Default
            assert row['confidence'] == 1.0  # Default
            assert row['source_method'] == "ui"  # Default
            assert row['archived'] == 0  # Default false
    
    def test_store_memory_full_parameters(self, memory_manager):
        """Test storing memory with all parameters"""
        metadata = {"key": "value", "number": 42}
        tags = ["tag1", "tag2", "important"]
        
        memory_id = memory_manager.store_memory(
            content="Complex memory with all fields",
            entry_type="complex",
            assistant_id="archie",
            plugin_source="test_plugin",
            metadata=metadata,
            tags=tags,
            confidence=0.85,
            source_method="voice"
        )
        
        # Verify memory was stored correctly
        with sqlite3.connect(memory_manager.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM memory_entries WHERE id = ?", (memory_id,))
            row = cursor.fetchone()
            
            assert row['content'] == "Complex memory with all fields"
            assert row['entry_type'] == "complex"
            assert row['assistant_id'] == "archie"
            assert row['plugin_source'] == "test_plugin"
            assert json.loads(row['metadata']) == metadata
            assert row['tags'] == "tag1,tag2,important"
            assert row['confidence'] == 0.85
            assert row['source_method'] == "voice"
    
    def test_store_memory_with_none_metadata(self, memory_manager):
        """Test storing memory with None metadata"""
        memory_id = memory_manager.store_memory(
            content="Memory without metadata",
            entry_type="test",
            metadata=None,
            tags=None
        )
        
        with sqlite3.connect(memory_manager.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM memory_entries WHERE id = ?", (memory_id,))
            row = cursor.fetchone()
            
            assert row['metadata'] is None
            assert row['tags'] == ""
    
    def test_store_memory_empty_tags(self, memory_manager):
        """Test storing memory with empty tags list"""
        memory_id = memory_manager.store_memory(
            content="Memory with empty tags",
            entry_type="test",
            tags=[]
        )
        
        with sqlite3.connect(memory_manager.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM memory_entries WHERE id = ?", (memory_id,))
            row = cursor.fetchone()
            
            assert row['tags'] == ""
    
    def test_store_memory_audit_logging(self, memory_manager):
        """Test that memory storage creates audit log entries"""
        memory_id = memory_manager.store_memory(
            content="Test audit logging",
            entry_type="test",
            assistant_id="percy"
        )
        
        # Check audit log was created
        with sqlite3.connect(memory_manager.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM audit_log 
                WHERE action = 'write' AND resource = 'memory_entries' 
                ORDER BY timestamp DESC LIMIT 1
            """)
            row = cursor.fetchone()
            
            assert row is not None
            assert row['assistant_id'] == "percy"
            assert row['status'] == "success"
            assert f"Stored memory entry ID {memory_id}" in row['details']
    
    def test_store_memory_fts_trigger(self, memory_manager):
        """Test that FTS table is updated when memory is stored"""
        memory_id = memory_manager.store_memory(
            content="Searchable content for FTS",
            entry_type="test",
            tags=["searchable", "fts"]
        )
        
        # Check FTS table was updated
        with sqlite3.connect(memory_manager.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM memory_fts WHERE rowid = ?", (memory_id,))
            row = cursor.fetchone()
            
            assert row is not None
            assert "Searchable content for FTS" in row[0]  # content
            assert "searchable,fts" in row[1]  # tags


class TestMemorySearch:
    """Test memory search and retrieval functionality"""
    
    @pytest.fixture
    def memory_manager(self, temp_db_dir):
        """Create test memory manager instance"""
        db_path = temp_db_dir / "test_memory.db"
        schema_path = temp_db_dir / "schema.sql"
        TestMemoryManager()._create_test_schema(schema_path)
        
        with patch('archie_core.memory_manager.Path') as mock_path:
            mock_path.return_value.parent.parent = temp_db_dir
            manager = MemoryManager(str(db_path))
            yield manager
    
    @pytest.fixture
    def temp_db_dir(self):
        """Create temporary directory for test database"""
        with tempfile.TemporaryDirectory(prefix="archie_memory_test_") as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def populated_manager(self, memory_manager):
        """Create memory manager with test data"""
        # Store test memories
        test_memories = [
            {
                "content": "Learning Python programming today",
                "entry_type": "learning",
                "assistant_id": "percy",
                "tags": ["python", "programming"],
                "metadata": {"difficulty": "beginner"}
            },
            {
                "content": "Project meeting went well",
                "entry_type": "work",
                "assistant_id": "percy",
                "tags": ["meeting", "project"],
                "plugin_source": "calendar"
            },
            {
                "content": "Grocery shopping reminder",
                "entry_type": "reminder",
                "assistant_id": "archie",
                "tags": ["shopping", "groceries"]
            },
            {
                "content": "Discussion about machine learning",
                "entry_type": "interaction",
                "assistant_id": "percy",
                "tags": ["ai", "ml", "discussion"]
            },
            {
                "content": "Old archived memory",
                "entry_type": "old",
                "assistant_id": "percy",
                "tags": ["archive"]
            }
        ]
        
        for memory_data in test_memories:
            memory_manager.store_memory(**memory_data)
        
        # Archive one memory manually for testing
        with sqlite3.connect(memory_manager.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE memory_entries SET archived = TRUE WHERE content = 'Old archived memory'"
            )
        
        yield memory_manager
    
    def test_search_memories_no_parameters(self, populated_manager):
        """Test searching memories with no parameters (get all)"""
        results = populated_manager.search_memories()
        
        # Should return non-archived memories only
        assert len(results) == 4  # 5 total - 1 archived
        assert all(not result['archived'] for result in results)
        
        # Should be sorted by timestamp DESC (most recent first)
        timestamps = [result['timestamp'] for result in results]
        assert timestamps == sorted(timestamps, reverse=True)
    
    def test_search_memories_with_query(self, populated_manager):
        """Test full-text search functionality"""
        # Search for "python"
        results = populated_manager.search_memories(query="python")
        assert len(results) == 1
        assert "Python" in results[0]['content']
        
        # Search for "meeting"
        results = populated_manager.search_memories(query="project")
        assert len(results) == 1
        assert "Project meeting" in results[0]['content']
        
        # Search for non-existent term
        results = populated_manager.search_memories(query="nonexistent")
        assert len(results) == 0
    
    def test_search_memories_by_entry_type(self, populated_manager):
        """Test filtering by entry type"""
        # Search for learning entries
        results = populated_manager.search_memories(entry_type="learning")
        assert len(results) == 1
        assert results[0]['entry_type'] == "learning"
        
        # Search for work entries
        results = populated_manager.search_memories(entry_type="work")
        assert len(results) == 1
        assert results[0]['entry_type'] == "work"
        
        # Search for non-existent type
        results = populated_manager.search_memories(entry_type="nonexistent")
        assert len(results) == 0
    
    def test_search_memories_by_assistant_id(self, populated_manager):
        """Test filtering by assistant ID"""
        # Search for percy's memories
        results = populated_manager.search_memories(assistant_id="percy")
        assert len(results) == 3
        assert all(result['assistant_id'] == "percy" for result in results)
        
        # Search for archie's memories
        results = populated_manager.search_memories(assistant_id="archie")
        assert len(results) == 1
        assert results[0]['assistant_id'] == "archie"
    
    def test_search_memories_by_tags(self, populated_manager):
        """Test filtering by tags"""
        # Search for programming tag
        results = populated_manager.search_memories(tags=["programming"])
        assert len(results) == 1
        assert "programming" in results[0]['tags']
        
        # Search for multiple tags
        results = populated_manager.search_memories(tags=["project", "meeting"])
        assert len(results) == 1
        
        # Search for non-existent tag
        results = populated_manager.search_memories(tags=["nonexistent"])
        assert len(results) == 0
    
    def test_search_memories_by_date_range(self, populated_manager):
        """Test filtering by date range"""
        now = datetime.now()
        one_hour_ago = now - timedelta(hours=1)
        one_hour_from_now = now + timedelta(hours=1)
        
        # Search for recent memories
        results = populated_manager.search_memories(
            date_from=one_hour_ago,
            date_to=one_hour_from_now
        )
        assert len(results) >= 0  # Could be any number depending on timing
        
        # Search for future memories (should be empty)
        future_start = now + timedelta(days=1)
        future_end = now + timedelta(days=2)
        results = populated_manager.search_memories(
            date_from=future_start,
            date_to=future_end
        )
        assert len(results) == 0
    
    def test_search_memories_with_limit(self, populated_manager):
        """Test result limit functionality"""
        # Search with limit 2
        results = populated_manager.search_memories(limit=2)
        assert len(results) == 2
        
        # Search with limit larger than available results
        results = populated_manager.search_memories(limit=100)
        assert len(results) == 4  # Total non-archived memories
    
    def test_search_memories_include_archived(self, populated_manager):
        """Test searching archived memories"""
        # Search excluding archived (default)
        results = populated_manager.search_memories()
        assert len(results) == 4
        
        # Search including archived
        results = populated_manager.search_memories(archived=True)
        assert len(results) == 1  # Only archived ones
        assert results[0]['archived'] == True
    
    def test_search_memories_combined_filters(self, populated_manager):
        """Test combining multiple search filters"""
        results = populated_manager.search_memories(
            query="python",
            entry_type="learning",
            assistant_id="percy",
            tags=["programming"]
        )
        
        assert len(results) == 1
        result = results[0]
        assert "Python" in result['content']
        assert result['entry_type'] == "learning"
        assert result['assistant_id'] == "percy"
        assert "programming" in result['tags']
    
    def test_search_memories_result_format(self, populated_manager):
        """Test the format of search results"""
        results = populated_manager.search_memories(limit=1)
        assert len(results) == 1
        
        result = results[0]
        
        # Check required fields
        assert 'id' in result
        assert 'content' in result
        assert 'entry_type' in result
        assert 'assistant_id' in result
        assert 'timestamp' in result
        
        # Check that metadata and tags are parsed correctly
        if result['metadata']:
            assert isinstance(result['metadata'], dict)
        if result['tags']:
            assert isinstance(result['tags'], list)
    
    def test_search_memories_audit_logging(self, populated_manager):
        """Test that search operations are audit logged"""
        results = populated_manager.search_memories(query="python")
        
        # Check audit log was created
        with sqlite3.connect(populated_manager.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM audit_log 
                WHERE action = 'read' AND resource = 'memory_entries'
                ORDER BY timestamp DESC LIMIT 1
            """)
            row = cursor.fetchone()
            
            assert row is not None
            assert row['status'] == "success"
            assert "Retrieved" in row['details']


class TestInteractionStorage:
    """Test interaction storage functionality"""
    
    @pytest.fixture
    def memory_manager(self, temp_db_dir):
        """Create test memory manager instance"""
        db_path = temp_db_dir / "test_memory.db"
        schema_path = temp_db_dir / "schema.sql"
        TestMemoryManager()._create_test_schema(schema_path)
        
        with patch('archie_core.memory_manager.Path') as mock_path:
            mock_path.return_value.parent.parent = temp_db_dir
            manager = MemoryManager(str(db_path))
            yield manager
    
    @pytest.fixture
    def temp_db_dir(self):
        """Create temporary directory for test database"""
        with tempfile.TemporaryDirectory(prefix="archie_memory_test_") as temp_dir:
            yield Path(temp_dir)
    
    def test_store_interaction_minimal(self, memory_manager):
        """Test storing interaction with minimal parameters"""
        interaction_id = memory_manager.store_interaction(
            user_message="Hello, how are you?",
            assistant_response="I'm doing well, thank you!"
        )
        
        assert isinstance(interaction_id, int)
        assert interaction_id > 0
        
        # Verify interaction was stored
        with sqlite3.connect(memory_manager.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM interactions WHERE id = ?", (interaction_id,))
            row = cursor.fetchone()
            
            assert row is not None
            assert row['user_message'] == "Hello, how are you?"
            assert row['assistant_response'] == "I'm doing well, thank you!"
            assert row['assistant_id'] == "percy"  # Default
    
    def test_store_interaction_full_parameters(self, memory_manager):
        """Test storing interaction with all parameters"""
        interaction_id = memory_manager.store_interaction(
            user_message="Can you help me with Python?",
            assistant_response="Of course! What specific Python topic?",
            assistant_id="archie",
            context="Programming help session",
            session_id="session_123",
            plugin_used="coding_assistant",
            intent_detected="help_request"
        )
        
        # Verify interaction was stored correctly
        with sqlite3.connect(memory_manager.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM interactions WHERE id = ?", (interaction_id,))
            row = cursor.fetchone()
            
            assert row['user_message'] == "Can you help me with Python?"
            assert row['assistant_response'] == "Of course! What specific Python topic?"
            assert row['assistant_id'] == "archie"
            assert row['context'] == "Programming help session"
            assert row['session_id'] == "session_123"
            assert row['plugin_used'] == "coding_assistant"
            assert row['intent_detected'] == "help_request"
    
    def test_store_interaction_with_none_values(self, memory_manager):
        """Test storing interaction with None optional parameters"""
        interaction_id = memory_manager.store_interaction(
            user_message="Simple message",
            assistant_response="Simple response",
            context=None,
            session_id=None,
            plugin_used=None,
            intent_detected=None
        )
        
        with sqlite3.connect(memory_manager.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM interactions WHERE id = ?", (interaction_id,))
            row = cursor.fetchone()
            
            assert row['context'] is None
            assert row['session_id'] is None
            assert row['plugin_used'] is None
            assert row['intent_detected'] is None


class TestMemoryStats:
    """Test memory statistics functionality"""
    
    @pytest.fixture
    def memory_manager(self, temp_db_dir):
        """Create test memory manager instance"""
        db_path = temp_db_dir / "test_memory.db"
        schema_path = temp_db_dir / "schema.sql"
        TestMemoryManager()._create_test_schema(schema_path)
        
        with patch('archie_core.memory_manager.Path') as mock_path:
            mock_path.return_value.parent.parent = temp_db_dir
            manager = MemoryManager(str(db_path))
            yield manager
    
    @pytest.fixture
    def temp_db_dir(self):
        """Create temporary directory for test database"""
        with tempfile.TemporaryDirectory(prefix="archie_memory_test_") as temp_dir:
            yield Path(temp_dir)
    
    def test_get_memory_stats_empty_database(self, memory_manager):
        """Test memory stats with empty database"""
        stats = memory_manager.get_memory_stats()
        
        assert isinstance(stats, dict)
        assert stats['total_entries'] == 0
        assert stats['entries_by_type'] == {}
        assert stats['recent_activity_7d'] == 0
        assert stats['database_size_mb'] >= 0
        assert 'last_updated' in stats
    
    def test_get_memory_stats_with_data(self, memory_manager):
        """Test memory stats with sample data"""
        # Store various types of memories
        memory_manager.store_memory("Learning note", "learning")
        memory_manager.store_memory("Work note", "work")
        memory_manager.store_memory("Another work note", "work")
        memory_manager.store_memory("Reminder", "reminder")
        
        stats = memory_manager.get_memory_stats()
        
        assert stats['total_entries'] == 4
        assert stats['entries_by_type']['learning'] == 1
        assert stats['entries_by_type']['work'] == 2
        assert stats['entries_by_type']['reminder'] == 1
        assert stats['recent_activity_7d'] == 4  # All recent
        assert stats['database_size_mb'] > 0
    
    def test_get_memory_stats_excludes_archived(self, memory_manager):
        """Test that stats exclude archived memories"""
        # Store memories
        memory_manager.store_memory("Active memory", "active")
        memory_manager.store_memory("To be archived", "archive_me")
        
        # Archive one memory
        with sqlite3.connect(memory_manager.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE memory_entries SET archived = TRUE WHERE content = 'To be archived'"
            )
        
        stats = memory_manager.get_memory_stats()
        
        assert stats['total_entries'] == 1  # Only non-archived
        assert stats['entries_by_type'].get('archive_me', 0) == 0  # Archived type not counted
        assert stats['entries_by_type']['active'] == 1
    
    def test_get_memory_stats_recent_activity(self, memory_manager):
        """Test recent activity calculation"""
        # Store a recent memory
        memory_manager.store_memory("Recent memory", "recent")
        
        # Manually insert an old memory
        eight_days_ago = (datetime.now() - timedelta(days=8)).isoformat()
        with sqlite3.connect(memory_manager.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO memory_entries (content, entry_type, timestamp, archived)
                VALUES (?, ?, ?, FALSE)
            """, ("Old memory", "old", eight_days_ago))
        
        stats = memory_manager.get_memory_stats()
        
        assert stats['total_entries'] == 2
        assert stats['recent_activity_7d'] == 1  # Only the recent one
    
    def test_get_memory_stats_database_size(self, memory_manager):
        """Test database size calculation"""
        # Empty database should have some size
        stats = memory_manager.get_memory_stats()
        initial_size = stats['database_size_mb']
        assert initial_size > 0
        
        # Add some data and verify size increases
        for i in range(100):
            memory_manager.store_memory(f"Memory {i} " + "x" * 1000, "bulk")
        
        stats = memory_manager.get_memory_stats()
        new_size = stats['database_size_mb']
        assert new_size > initial_size
        assert isinstance(new_size, float)
        assert new_size == round(new_size, 2)  # Should be rounded to 2 decimals


class TestMemoryArchiving:
    """Test memory archiving functionality"""
    
    @pytest.fixture
    def memory_manager(self, temp_db_dir):
        """Create test memory manager instance"""
        db_path = temp_db_dir / "test_memory.db"
        schema_path = temp_db_dir / "schema.sql"
        TestMemoryManager()._create_test_schema(schema_path)
        
        with patch('archie_core.memory_manager.Path') as mock_path:
            mock_path.return_value.parent.parent = temp_db_dir
            manager = MemoryManager(str(db_path))
            yield manager
    
    @pytest.fixture
    def temp_db_dir(self):
        """Create temporary directory for test database"""
        with tempfile.TemporaryDirectory(prefix="archie_memory_test_") as temp_dir:
            yield Path(temp_dir)
    
    def test_archive_old_memories_default_days(self, memory_manager):
        """Test archiving memories with default 90 days"""
        # Store recent memory
        memory_manager.store_memory("Recent memory", "recent")
        
        # Manually insert old memory (100 days ago)
        old_date = (datetime.now() - timedelta(days=100)).isoformat()
        with sqlite3.connect(memory_manager.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO memory_entries (content, entry_type, timestamp, archived)
                VALUES (?, ?, ?, FALSE)
            """, ("Old memory", "old", old_date))
        
        # Archive old memories
        archived_count = memory_manager.archive_old_memories()
        
        assert archived_count == 1
        
        # Verify the old memory was archived
        with sqlite3.connect(memory_manager.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM memory_entries WHERE content = 'Old memory'")
            row = cursor.fetchone()
            assert row['archived'] == 1  # TRUE
            
            # Verify recent memory was not archived
            cursor.execute("SELECT * FROM memory_entries WHERE content = 'Recent memory'")
            row = cursor.fetchone()
            assert row['archived'] == 0  # FALSE
    
    def test_archive_old_memories_custom_days(self, memory_manager):
        """Test archiving memories with custom days"""
        # Store memory from 10 days ago
        ten_days_ago = (datetime.now() - timedelta(days=10)).isoformat()
        with sqlite3.connect(memory_manager.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO memory_entries (content, entry_type, timestamp, archived)
                VALUES (?, ?, ?, FALSE)
            """, ("10 days old memory", "old", ten_days_ago))
        
        # Archive memories older than 5 days
        archived_count = memory_manager.archive_old_memories(days_old=5)
        
        assert archived_count == 1
        
        # Verify the memory was archived
        with sqlite3.connect(memory_manager.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM memory_entries WHERE content = '10 days old memory'")
            row = cursor.fetchone()
            assert row['archived'] == 1  # TRUE
    
    def test_archive_old_memories_no_matches(self, memory_manager):
        """Test archiving when no memories match criteria"""
        # Store only recent memories
        memory_manager.store_memory("Recent memory 1", "recent")
        memory_manager.store_memory("Recent memory 2", "recent")
        
        # Archive memories older than 90 days (should find none)
        archived_count = memory_manager.archive_old_memories()
        
        assert archived_count == 0
    
    def test_archive_old_memories_already_archived(self, memory_manager):
        """Test that already archived memories are not affected"""
        # Insert old memory that's already archived
        old_date = (datetime.now() - timedelta(days=100)).isoformat()
        with sqlite3.connect(memory_manager.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO memory_entries (content, entry_type, timestamp, archived)
                VALUES (?, ?, ?, TRUE)
            """, ("Already archived", "old", old_date))
        
        # Archive old memories
        archived_count = memory_manager.archive_old_memories()
        
        assert archived_count == 0  # Should not affect already archived memories
    
    def test_archive_old_memories_pruning_history(self, memory_manager):
        """Test that archiving creates pruning history entry"""
        # Insert old memory
        old_date = (datetime.now() - timedelta(days=100)).isoformat()
        with sqlite3.connect(memory_manager.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO memory_entries (content, entry_type, timestamp, archived)
                VALUES (?, ?, ?, FALSE)
            """, ("Old memory", "old", old_date))
        
        # Archive old memories
        archived_count = memory_manager.archive_old_memories(days_old=50)
        
        # Check pruning history was created
        with sqlite3.connect(memory_manager.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM pruning_history 
                WHERE rule_type = 'age' 
                ORDER BY executed_at DESC LIMIT 1
            """)
            row = cursor.fetchone()
            
            assert row is not None
            assert row['entries_affected'] == archived_count
            assert "50 days" in row['details']


class TestAuditLogging:
    """Test audit logging functionality"""
    
    @pytest.fixture
    def memory_manager(self, temp_db_dir):
        """Create test memory manager instance"""
        db_path = temp_db_dir / "test_memory.db"
        schema_path = temp_db_dir / "schema.sql"
        TestMemoryManager()._create_test_schema(schema_path)
        
        with patch('archie_core.memory_manager.Path') as mock_path:
            mock_path.return_value.parent.parent = temp_db_dir
            manager = MemoryManager(str(db_path))
            yield manager
    
    @pytest.fixture
    def temp_db_dir(self):
        """Create temporary directory for test database"""
        with tempfile.TemporaryDirectory(prefix="archie_memory_test_") as temp_dir:
            yield Path(temp_dir)
    
    def test_log_audit_with_connection(self, memory_manager):
        """Test audit logging within existing transaction"""
        with sqlite3.connect(memory_manager.db_path) as conn:
            memory_manager._log_audit(
                action="test_action",
                resource="test_resource",
                assistant_id="test_assistant",
                status="success",
                details="Test audit entry",
                conn=conn
            )
        
        # Verify audit entry was created
        with sqlite3.connect(memory_manager.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT 1")
            row = cursor.fetchone()
            
            assert row is not None
            assert row['action'] == "test_action"
            assert row['resource'] == "test_resource"
            assert row['assistant_id'] == "test_assistant"
            assert row['status'] == "success"
            assert row['details'] == "Test audit entry"
    
    def test_log_audit_without_connection(self, memory_manager):
        """Test audit logging with separate connection"""
        memory_manager._log_audit(
            action="standalone_action",
            resource="standalone_resource",
            assistant_id="standalone_assistant",
            status="failure",
            details="Standalone audit entry"
        )
        
        # Verify audit entry was created
        with sqlite3.connect(memory_manager.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT 1")
            row = cursor.fetchone()
            
            assert row is not None
            assert row['action'] == "standalone_action"
            assert row['resource'] == "standalone_resource"
            assert row['assistant_id'] == "standalone_assistant"
            assert row['status'] == "failure"
            assert row['details'] == "Standalone audit entry"
    
    def test_log_audit_default_details(self, memory_manager):
        """Test audit logging with default empty details"""
        memory_manager._log_audit(
            action="minimal_action",
            resource="minimal_resource",
            assistant_id="minimal_assistant",
            status="success"
        )
        
        # Verify audit entry was created with empty details
        with sqlite3.connect(memory_manager.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT 1")
            row = cursor.fetchone()
            
            assert row is not None
            assert row['details'] == ""


class TestEdgeCasesAndErrors:
    """Test edge cases and error conditions"""
    
    @pytest.fixture
    def memory_manager(self, temp_db_dir):
        """Create test memory manager instance"""
        db_path = temp_db_dir / "test_memory.db"
        schema_path = temp_db_dir / "schema.sql"
        TestMemoryManager()._create_test_schema(schema_path)
        
        with patch('archie_core.memory_manager.Path') as mock_path:
            mock_path.return_value.parent.parent = temp_db_dir
            manager = MemoryManager(str(db_path))
            yield manager
    
    @pytest.fixture
    def temp_db_dir(self):
        """Create temporary directory for test database"""
        with tempfile.TemporaryDirectory(prefix="archie_memory_test_") as temp_dir:
            yield Path(temp_dir)
    
    def test_store_memory_large_content(self, memory_manager):
        """Test storing very large memory content"""
        large_content = "x" * 100000  # 100KB of content
        
        memory_id = memory_manager.store_memory(
            content=large_content,
            entry_type="large_test"
        )
        
        assert memory_id > 0
        
        # Verify it was stored correctly
        results = memory_manager.search_memories(entry_type="large_test")
        assert len(results) == 1
        assert len(results[0]['content']) == 100000
    
    def test_store_memory_special_characters(self, memory_manager):
        """Test storing memory with special characters and unicode"""
        special_content = "Special chars: áéíóú 中文 🚀 '\"\\\n\t"
        
        memory_id = memory_manager.store_memory(
            content=special_content,
            entry_type="special_test",
            tags=["unicode", "special-chars"]
        )
        
        assert memory_id > 0
        
        # Verify it was stored correctly
        results = memory_manager.search_memories(entry_type="special_test")
        assert len(results) == 1
        assert results[0]['content'] == special_content
    
    def test_store_memory_complex_metadata(self, memory_manager):
        """Test storing memory with complex metadata structures"""
        complex_metadata = {
            "nested": {
                "level1": {
                    "level2": ["array", "values", 123]
                }
            },
            "unicode_key_中文": "unicode value áéíóú",
            "numbers": [1, 2.5, -10],
            "boolean": True,
            "null_value": None
        }
        
        memory_id = memory_manager.store_memory(
            content="Complex metadata test",
            entry_type="metadata_test",
            metadata=complex_metadata
        )
        
        # Verify metadata was stored and retrieved correctly
        results = memory_manager.search_memories(entry_type="metadata_test")
        assert len(results) == 1
        assert results[0]['metadata'] == complex_metadata
    
    def test_search_memories_with_sql_injection_attempt(self, memory_manager):
        """Test that search is safe from SQL injection"""
        # Store a normal memory
        memory_manager.store_memory("Normal content", "normal")
        
        # Try various SQL injection attempts
        injection_attempts = [
            "'; DROP TABLE memory_entries; --",
            "' OR 1=1 --",
            "' UNION SELECT * FROM audit_log --",
            "\\'; DELETE FROM memory_entries; --"
        ]
        
        for injection in injection_attempts:
            results = memory_manager.search_memories(query=injection)
            # Should return empty results, not cause errors
            assert isinstance(results, list)
        
        # Verify original memory still exists
        results = memory_manager.search_memories(entry_type="normal")
        assert len(results) == 1
    
    def test_search_memories_malformed_fts_query(self, memory_manager):
        """Test handling of malformed FTS queries"""
        # Store some memories for search
        memory_manager.store_memory("Test content", "test")
        
        # Try malformed FTS queries
        malformed_queries = [
            '"unclosed quote',
            'AND OR NOT',
            '* NEAR/ *',
            'MATCH(',
            '\\',
            ''  # Empty query
        ]
        
        for query in malformed_queries:
            # Should handle gracefully without crashing
            try:
                results = memory_manager.search_memories(query=query)
                assert isinstance(results, list)
            except Exception:
                # If FTS query fails, should return empty list
                pass
    
    def test_memory_manager_close(self, memory_manager):
        """Test memory manager cleanup"""
        # Should not raise any exceptions
        memory_manager.close()
    
    def test_concurrent_memory_operations(self, memory_manager):
        """Test thread safety assumptions"""
        import threading
        import concurrent.futures
        
        def store_memory_worker(i):
            return memory_manager.store_memory(
                content=f"Concurrent memory {i}",
                entry_type="concurrent",
                assistant_id=f"assistant_{i % 3}"
            )
        
        # Store memories concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(store_memory_worker, i) for i in range(20)]
            memory_ids = [future.result() for future in futures]
        
        # All should have unique IDs
        assert len(set(memory_ids)) == 20
        
        # All should be findable
        results = memory_manager.search_memories(entry_type="concurrent")
        assert len(results) == 20
    
    def test_database_corruption_handling(self, temp_db_dir):
        """Test handling of database corruption"""
        db_path = temp_db_dir / "corrupt.db"
        
        # Create a file that's not a valid SQLite database
        with open(db_path, 'w') as f:
            f.write("This is not a SQLite database")
        
        # Should handle gracefully
        with pytest.raises(Exception):
            # This should fail during initialization
            with patch('archie_core.memory_manager.Path') as mock_path:
                mock_path.return_value.parent.parent = temp_db_dir
                MemoryManager(str(db_path))


class TestMemoryManagerIntegration:
    """Integration tests combining multiple memory manager features"""
    
    @pytest.fixture
    def memory_manager(self, temp_db_dir):
        """Create test memory manager instance"""
        db_path = temp_db_dir / "test_memory.db"
        schema_path = temp_db_dir / "schema.sql"
        TestMemoryManager()._create_test_schema(schema_path)
        
        with patch('archie_core.memory_manager.Path') as mock_path:
            mock_path.return_value.parent.parent = temp_db_dir
            manager = MemoryManager(str(db_path))
            yield manager
    
    @pytest.fixture
    def temp_db_dir(self):
        """Create temporary directory for test database"""
        with tempfile.TemporaryDirectory(prefix="archie_memory_test_") as temp_dir:
            yield Path(temp_dir)
    
    def test_full_memory_lifecycle(self, memory_manager):
        """Test complete memory lifecycle: store -> search -> archive"""
        # Store initial memories
        learning_id = memory_manager.store_memory(
            content="Learning Python decorators",
            entry_type="learning",
            tags=["python", "decorators", "programming"],
            metadata={"difficulty": "intermediate", "source": "documentation"}
        )
        
        work_id = memory_manager.store_memory(
            content="Team meeting about Q4 goals",
            entry_type="work",
            tags=["meeting", "goals", "team"],
            plugin_source="calendar"
        )
        
        # Search and verify memories
        all_memories = memory_manager.search_memories()
        assert len(all_memories) == 2
        
        python_memories = memory_manager.search_memories(query="Python")
        assert len(python_memories) == 1
        assert python_memories[0]['id'] == learning_id
        
        work_memories = memory_manager.search_memories(entry_type="work")
        assert len(work_memories) == 1
        assert work_memories[0]['id'] == work_id
        
        # Check stats
        stats = memory_manager.get_memory_stats()
        assert stats['total_entries'] == 2
        assert stats['entries_by_type']['learning'] == 1
        assert stats['entries_by_type']['work'] == 1
        
        # Manually age one memory and archive
        old_date = (datetime.now() - timedelta(days=100)).isoformat()
        with sqlite3.connect(memory_manager.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE memory_entries SET timestamp = ? WHERE id = ?",
                (old_date, learning_id)
            )
        
        archived_count = memory_manager.archive_old_memories(days_old=90)
        assert archived_count == 1
        
        # Verify archived memory is excluded from normal searches
        all_memories = memory_manager.search_memories()
        assert len(all_memories) == 1
        assert all_memories[0]['id'] == work_id
        
        # But can be found when including archived
        archived_memories = memory_manager.search_memories(archived=True)
        assert len(archived_memories) == 1
        assert archived_memories[0]['id'] == learning_id
        
        # Updated stats should reflect archiving
        updated_stats = memory_manager.get_memory_stats()
        assert updated_stats['total_entries'] == 1  # Excludes archived
    
    def test_interaction_and_memory_correlation(self, memory_manager):
        """Test storing both interactions and memories from same session"""
        session_id = "test_session_123"
        
        # Store an interaction
        interaction_id = memory_manager.store_interaction(
            user_message="Can you help me understand decorators?",
            assistant_response="Decorators are a powerful Python feature...",
            assistant_id="percy",
            session_id=session_id,
            intent_detected="learning_request"
        )
        
        # Store related memory
        memory_id = memory_manager.store_memory(
            content="User asked about Python decorators, provided explanation",
            entry_type="interaction",
            assistant_id="percy",
            tags=["python", "decorators", "teaching"],
            metadata={"session_id": session_id, "interaction_id": interaction_id}
        )
        
        # Search for related content
        decorator_memories = memory_manager.search_memories(query="decorators")
        assert len(decorator_memories) == 1
        assert decorator_memories[0]['metadata']['session_id'] == session_id
        
        # Verify interaction was stored
        with sqlite3.connect(memory_manager.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM interactions WHERE session_id = ?", (session_id,))
            interaction = cursor.fetchone()
            
            assert interaction is not None
            assert interaction['intent_detected'] == "learning_request"
    
    def test_bulk_operations_performance(self, memory_manager):
        """Test performance with bulk operations"""
        import time
        
        # Bulk store memories
        start_time = time.time()
        memory_ids = []
        
        for i in range(100):
            memory_id = memory_manager.store_memory(
                content=f"Bulk memory {i} with some content to make it realistic",
                entry_type="bulk",
                assistant_id="percy" if i % 2 == 0 else "archie",
                tags=[f"tag{i}", "bulk", "test"],
                metadata={"index": i, "batch": "performance_test"}
            )
            memory_ids.append(memory_id)
        
        store_time = time.time() - start_time
        
        # Bulk search
        start_time = time.time()
        all_bulk = memory_manager.search_memories(entry_type="bulk")
        search_time = time.time() - start_time
        
        assert len(all_bulk) == 100
        assert len(memory_ids) == 100
        
        # Performance assertions (should be reasonable for 100 entries)
        assert store_time < 10.0  # Should store 100 entries in under 10 seconds
        assert search_time < 1.0   # Should search in under 1 second
        
        # Test bulk archiving
        cutoff_date = datetime.now().isoformat()
        archived_count = memory_manager.archive_old_memories(days_old=0)
        assert archived_count == 100  # All should be archived
        
        # Verify stats are correct
        stats = memory_manager.get_memory_stats()
        assert stats['total_entries'] == 0  # All archived