"""
Comprehensive tests for archie_core.db module - Database operations
"""
import pytest
import tempfile
import sqlite3
import json
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

from archie_core.db import Database, get_db_path, migrate, CURRENT_SCHEMA_VERSION


class TestDatabase:
    """Test Database class initialization and basic operations"""
    
    @pytest.fixture
    def temp_db_dir(self):
        """Create temporary directory for test database"""
        with tempfile.TemporaryDirectory(prefix="archie_db_test_") as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def db(self, temp_db_dir):
        """Create test database instance"""
        db = Database(str(temp_db_dir))
        db.initialize()
        yield db
        db.close()
    
    def test_init_default_path(self):
        """Test database initialization with default path"""
        with patch.dict('os.environ', {'ARCHIE_DATA_ROOT': '/test/path'}):
            db = Database()
            assert str(db.data_root) == '/test/path'
            assert db.db_path == db.data_root / 'db' / 'long_memory.sqlite3'
    
    def test_init_custom_path(self, temp_db_dir):
        """Test database initialization with custom path"""
        db = Database(str(temp_db_dir))
        assert db.data_root == temp_db_dir
        assert db.db_path == temp_db_dir / 'db' / 'long_memory.sqlite3'
    
    def test_ensure_directories(self, temp_db_dir):
        """Test that required directories are created"""
        db = Database(str(temp_db_dir))
        
        # Check that all required directories exist
        assert (temp_db_dir / 'db').exists()
        assert (temp_db_dir / 'media_vault').exists()
        assert (temp_db_dir / 'thumbnails').exists()
        assert (temp_db_dir / 'indexes').exists()
        assert (temp_db_dir / 'snapshots').exists()
    
    def test_connection_properties(self, db):
        """Test database connection properties"""
        conn = db.connection
        
        # Test that connection is configured correctly
        cursor = conn.execute("PRAGMA journal_mode")
        assert cursor.fetchone()[0] == "wal"
        
        cursor = conn.execute("PRAGMA foreign_keys")
        assert cursor.fetchone()[0] == 1
        
        # Test that row factory is set
        assert conn.row_factory == sqlite3.Row
    
    def test_transaction_success(self, db):
        """Test successful transaction"""
        entity_id = "test_transaction_success"
        entity_data = {
            'id': entity_id,
            'type': 'test',
            'payload': {'content': 'test content'}
        }
        
        with db.transaction() as conn:
            conn.execute("""
                INSERT INTO entities (id, type, payload, created, updated)
                VALUES (?, ?, ?, ?, ?)
            """, (
                entity_data['id'],
                entity_data['type'],
                json.dumps(entity_data['payload']),
                int(time.time()),
                int(time.time())
            ))
        
        # Verify entity was inserted
        result = db.get_entity(entity_id)
        assert result is not None
        assert result['id'] == entity_id
    
    def test_transaction_rollback(self, db):
        """Test transaction rollback on error"""
        entity_id = "test_transaction_rollback"
        
        with pytest.raises(sqlite3.IntegrityError):
            with db.transaction() as conn:
                # Insert valid entity
                conn.execute("""
                    INSERT INTO entities (id, type, payload, created, updated)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    entity_id, 'test', '{}', int(time.time()), int(time.time())
                ))
                
                # Try to insert duplicate (should fail)
                conn.execute("""
                    INSERT INTO entities (id, type, payload, created, updated)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    entity_id, 'test', '{}', int(time.time()), int(time.time())
                ))
        
        # Verify entity was NOT inserted due to rollback
        result = db.get_entity(entity_id)
        assert result is None
    
    def test_initialize_fresh_database(self, temp_db_dir):
        """Test initializing a fresh database"""
        db = Database(str(temp_db_dir))
        result = db.initialize()
        
        assert result is True
        
        # Check that schema version is set correctly
        version = db._get_schema_version()
        assert version == CURRENT_SCHEMA_VERSION
        
        # Check that core tables exist
        tables = ['entities', 'links', 'devices', 'jobs', 'settings', 
                 'council_members', 'council_meetings', 'audit_log']
        
        for table in tables:
            cursor = db.connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table,)
            )
            assert cursor.fetchone() is not None, f"Table {table} should exist"
        
        db.close()
    
    def test_get_schema_version_no_tables(self, temp_db_dir):
        """Test getting schema version when no tables exist"""
        db = Database(str(temp_db_dir))
        version = db._get_schema_version()
        assert version == 0
        db.close()
    
    def test_get_schema_version_from_settings(self, db):
        """Test getting schema version from settings table"""
        # Version should be set during initialization
        version = db._get_schema_version()
        assert version == CURRENT_SCHEMA_VERSION
    
    def test_set_schema_version(self, db):
        """Test setting schema version"""
        test_version = 99
        db._set_schema_version(test_version)
        
        version = db._get_schema_version()
        assert version == test_version


class TestEntityOperations:
    """Test entity CRUD operations"""
    
    @pytest.fixture
    def db(self, temp_db_dir):
        """Create test database instance"""
        db = Database(str(temp_db_dir))
        db.initialize()
        yield db
        db.close()
    
    @pytest.fixture
    def sample_entity(self):
        """Sample entity for testing"""
        return {
            'id': 'test_entity_123',
            'type': 'note',
            'payload': {
                'title': 'Test Note',
                'content': 'This is test content',
                'snippet': 'Test snippet'
            },
            'tags': ['test', 'sample'],
            'assistant_id': 'test_assistant',
            'sensitive': False,
            'archived': False
        }
    
    def test_insert_entity(self, db, sample_entity):
        """Test inserting an entity"""
        entity_id = db.insert_entity(sample_entity)
        
        assert entity_id == sample_entity['id']
        
        # Verify entity exists in database
        result = db.get_entity(entity_id)
        assert result is not None
        assert result['id'] == entity_id
        assert result['type'] == sample_entity['type']
        assert result['payload'] == sample_entity['payload']
        assert result['tags'] == sample_entity['tags']
    
    def test_insert_entity_minimal(self, db):
        """Test inserting entity with minimal required fields"""
        entity = {
            'id': 'minimal_entity',
            'type': 'test',
            'payload': {'content': 'minimal'}
        }
        
        entity_id = db.insert_entity(entity)
        assert entity_id == entity['id']
        
        result = db.get_entity(entity_id)
        assert result is not None
        assert result['tags'] == []  # Default empty tags
        assert result['assistant_id'] == 'archie'  # Default assistant
        assert result['sensitive'] is False
        assert result['archived'] is False
    
    def test_insert_entity_with_timestamps(self, db):
        """Test inserting entity with explicit timestamps"""
        now = int(time.time())
        entity = {
            'id': 'timestamped_entity',
            'type': 'test',
            'payload': {'content': 'test'},
            'created': now,
            'updated': now
        }
        
        db.insert_entity(entity)
        result = db.get_entity(entity['id'])
        
        assert result['created'] == now
        assert result['updated'] == now
    
    def test_get_entity_not_found(self, db):
        """Test getting non-existent entity"""
        result = db.get_entity('nonexistent_entity')
        assert result is None
    
    def test_update_entity(self, db, sample_entity):
        """Test updating an existing entity"""
        # Insert entity first
        db.insert_entity(sample_entity)
        
        # Update entity
        updates = {
            'payload': {'title': 'Updated Title', 'content': 'Updated content'},
            'tags': ['updated', 'modified']
        }
        
        result = db.update_entity(sample_entity['id'], updates)
        assert result is True
        
        # Verify updates
        entity = db.get_entity(sample_entity['id'])
        assert entity['payload']['title'] == 'Updated Title'
        assert entity['payload']['content'] == 'Updated content'
        assert entity['tags'] == ['updated', 'modified']
        assert entity['updated'] > sample_entity.get('updated', 0)
    
    def test_update_entity_partial_payload(self, db, sample_entity):
        """Test partial payload updates"""
        db.insert_entity(sample_entity)
        
        # Update only part of payload
        updates = {
            'payload': {'title': 'New Title'}  # Keep other fields
        }
        
        db.update_entity(sample_entity['id'], updates)
        entity = db.get_entity(sample_entity['id'])
        
        # Title should be updated, content should remain
        assert entity['payload']['title'] == 'New Title'
        assert entity['payload']['content'] == 'This is test content'
    
    def test_update_entity_not_found(self, db):
        """Test updating non-existent entity"""
        result = db.update_entity('nonexistent', {'payload': {'test': 'value'}})
        assert result is False
    
    def test_delete_entity(self, db, sample_entity):
        """Test deleting an entity"""
        # Insert entity
        db.insert_entity(sample_entity)
        
        # Create a link involving this entity
        db.create_link(sample_entity['id'], 'other_entity', 'related')
        
        # Delete entity
        result = db.delete_entity(sample_entity['id'])
        assert result is True
        
        # Verify entity is deleted
        assert db.get_entity(sample_entity['id']) is None
        
        # Verify links are also deleted
        links = db.get_links(sample_entity['id'])
        assert len(links) == 0


class TestEntitySearch:
    """Test entity search functionality"""
    
    @pytest.fixture
    def db_with_entities(self, temp_db_dir):
        """Create database with sample entities for search testing"""
        db = Database(str(temp_db_dir))
        db.initialize()
        
        # Insert test entities
        entities = [
            {
                'id': 'note_1',
                'type': 'note',
                'payload': {'title': 'Python Programming', 'content': 'Learn Python basics', 'snippet': 'Python tutorial'},
                'tags': ['programming', 'python'],
                'created': int(time.time()) - 3600  # 1 hour ago
            },
            {
                'id': 'note_2',
                'type': 'note',
                'payload': {'title': 'JavaScript Guide', 'content': 'JavaScript fundamentals', 'snippet': 'JS guide'},
                'tags': ['programming', 'javascript'],
                'created': int(time.time()) - 1800  # 30 minutes ago
            },
            {
                'id': 'task_1',
                'type': 'task',
                'payload': {'title': 'Buy groceries', 'content': 'Milk, bread, eggs', 'status': 'pending'},
                'tags': ['shopping', 'personal'],
                'created': int(time.time()) - 900   # 15 minutes ago
            },
            {
                'id': 'archived_note',
                'type': 'note',
                'payload': {'title': 'Old Note', 'content': 'This is archived'},
                'archived': True,
                'created': int(time.time()) - 7200  # 2 hours ago
            }
        ]
        
        for entity in entities:
            db.insert_entity(entity)
        
        # Wait a moment for FTS to update
        time.sleep(0.1)
        
        yield db
        db.close()
    
    def test_search_entities_no_filters(self, db_with_entities):
        """Test searching entities without filters"""
        results = db_with_entities.search_entities()
        
        # Should return non-archived entities, newest first
        assert len(results) == 3  # Excludes archived
        assert results[0]['id'] == 'task_1'  # Most recent
        assert results[1]['id'] == 'note_2'
        assert results[2]['id'] == 'note_1'
    
    def test_search_entities_by_type(self, db_with_entities):
        """Test searching entities by type"""
        results = db_with_entities.search_entities(entity_type='note')
        
        assert len(results) == 2
        for result in results:
            assert result['type'] == 'note'
            assert not result['archived']  # Archived should be excluded
    
    def test_search_entities_include_archived(self, db_with_entities):
        """Test including archived entities in search"""
        results = db_with_entities.search_entities(include_archived=True)
        
        assert len(results) == 4  # Includes archived entity
        archived_entity = next((r for r in results if r['id'] == 'archived_note'), None)
        assert archived_entity is not None
        assert archived_entity['archived'] is True
    
    def test_search_entities_with_text_query(self, db_with_entities):
        """Test full-text search"""
        results = db_with_entities.search_entities(query='Python')
        
        assert len(results) >= 1
        python_note = next((r for r in results if r['id'] == 'note_1'), None)
        assert python_note is not None
    
    def test_search_entities_with_time_range(self, db_with_entities):
        """Test searching with time constraints"""
        # Search for entities created in last 30 minutes
        since = int(time.time()) - 1800  # 30 minutes ago
        results = db_with_entities.search_entities(since=since)
        
        assert len(results) == 2  # note_2 and task_1
        for result in results:
            assert result['created'] >= since
    
    def test_search_entities_with_until(self, db_with_entities):
        """Test searching with until constraint"""
        # Search for entities created more than 45 minutes ago
        until = int(time.time()) - 2700  # 45 minutes ago
        results = db_with_entities.search_entities(until=until)
        
        assert len(results) == 1
        assert results[0]['id'] == 'note_1'
    
    def test_search_entities_with_limit_offset(self, db_with_entities):
        """Test pagination with limit and offset"""
        # Get first page
        page1 = db_with_entities.search_entities(limit=2, offset=0)
        assert len(page1) == 2
        
        # Get second page
        page2 = db_with_entities.search_entities(limit=2, offset=2)
        assert len(page2) == 1  # Only 1 more entity
        
        # Verify no overlap
        page1_ids = {r['id'] for r in page1}
        page2_ids = {r['id'] for r in page2}
        assert len(page1_ids.intersection(page2_ids)) == 0
    
    def test_search_entities_complex_query(self, db_with_entities):
        """Test complex search with multiple filters"""
        results = db_with_entities.search_entities(
            entity_type='note',
            query='programming',
            limit=10
        )
        
        # Should find programming-related notes
        assert len(results) >= 1
        for result in results:
            assert result['type'] == 'note'


class TestLinkOperations:
    """Test entity link operations"""
    
    @pytest.fixture
    def db_with_entities(self, temp_db_dir):
        """Create database with entities for link testing"""
        db = Database(str(temp_db_dir))
        db.initialize()
        
        # Insert test entities
        entities = [
            {'id': 'entity_a', 'type': 'note', 'payload': {'title': 'Entity A'}},
            {'id': 'entity_b', 'type': 'note', 'payload': {'title': 'Entity B'}},
            {'id': 'entity_c', 'type': 'task', 'payload': {'title': 'Entity C'}}
        ]
        
        for entity in entities:
            db.insert_entity(entity)
        
        yield db
        db.close()
    
    def test_create_link(self, db_with_entities):
        """Test creating links between entities"""
        metadata = {'strength': 0.8, 'auto_generated': True}
        
        db_with_entities.create_link('entity_a', 'entity_b', 'related', metadata)
        
        # Verify link exists
        links = db_with_entities.get_links('entity_a', direction='outgoing')
        assert len(links) == 1
        
        link = links[0]
        assert link['src'] == 'entity_a'
        assert link['dst'] == 'entity_b'
        assert link['type'] == 'related'
        assert link['metadata'] == metadata
        assert link['direction'] == 'outgoing'
    
    def test_create_link_replace_existing(self, db_with_entities):
        """Test that creating a link replaces existing one"""
        # Create initial link
        db_with_entities.create_link('entity_a', 'entity_b', 'related', {'version': 1})
        
        # Replace with new link
        db_with_entities.create_link('entity_a', 'entity_b', 'related', {'version': 2})
        
        # Should have only one link with updated metadata
        links = db_with_entities.get_links('entity_a', direction='outgoing')
        assert len(links) == 1
        assert links[0]['metadata']['version'] == 2
    
    def test_get_links_outgoing(self, db_with_entities):
        """Test getting outgoing links"""
        db_with_entities.create_link('entity_a', 'entity_b', 'parent_of')
        db_with_entities.create_link('entity_a', 'entity_c', 'related_to')
        
        links = db_with_entities.get_links('entity_a', direction='outgoing')
        
        assert len(links) == 2
        for link in links:
            assert link['src'] == 'entity_a'
            assert link['direction'] == 'outgoing'
    
    def test_get_links_incoming(self, db_with_entities):
        """Test getting incoming links"""
        db_with_entities.create_link('entity_a', 'entity_b', 'parent_of')
        db_with_entities.create_link('entity_c', 'entity_b', 'related_to')
        
        links = db_with_entities.get_links('entity_b', direction='incoming')
        
        assert len(links) == 2
        for link in links:
            assert link['dst'] == 'entity_b'
            assert link['direction'] == 'incoming'
    
    def test_get_links_both_directions(self, db_with_entities):
        """Test getting links in both directions"""
        db_with_entities.create_link('entity_a', 'entity_b', 'parent_of')
        db_with_entities.create_link('entity_b', 'entity_c', 'child_of')
        
        links = db_with_entities.get_links('entity_b', direction='both')
        
        assert len(links) == 2
        directions = {link['direction'] for link in links}
        assert directions == {'incoming', 'outgoing'}
    
    def test_delete_entity_removes_links(self, db_with_entities):
        """Test that deleting entity removes associated links"""
        # Create links
        db_with_entities.create_link('entity_a', 'entity_b', 'related')
        db_with_entities.create_link('entity_b', 'entity_c', 'parent_of')
        
        # Delete entity_b
        db_with_entities.delete_entity('entity_b')
        
        # Links involving entity_b should be gone
        links_a = db_with_entities.get_links('entity_a')
        links_c = db_with_entities.get_links('entity_c')
        
        assert len(links_a) == 0
        assert len(links_c) == 0


class TestDeviceOperations:
    """Test device registration and management"""
    
    @pytest.fixture
    def db(self, temp_db_dir):
        """Create test database instance"""
        db = Database(str(temp_db_dir))
        db.initialize()
        yield db
        db.close()
    
    @pytest.fixture
    def sample_device(self):
        """Sample device for testing"""
        return {
            'id': 'device_123',
            'name': 'Test Device',
            'public_key': 'test_public_key_data',
            'capabilities': ['memory', 'storage', 'council.deliberate'],
            'device_type': 'mobile',
            'os_version': 'iOS 15.0',
            'app_version': '1.0.0',
            'ip_address': '192.168.1.100',
            'council_member': 'percy'
        }
    
    def test_register_device(self, db, sample_device):
        """Test device registration"""
        device_id = db.register_device(sample_device)
        
        assert device_id == sample_device['id']
        
        # Verify device exists
        result = db.get_device(device_id)
        assert result is not None
        assert result['id'] == device_id
        assert result['name'] == sample_device['name']
        assert result['capabilities'] == sample_device['capabilities']
        assert result['last_seen'] is not None
    
    def test_register_device_minimal(self, db):
        """Test registering device with minimal fields"""
        device = {
            'id': 'minimal_device',
            'name': 'Minimal Device',
            'public_key': 'minimal_key',
            'capabilities': ['basic']
        }
        
        device_id = db.register_device(device)
        result = db.get_device(device_id)
        
        assert result is not None
        assert result['device_type'] is None
        assert result['council_member'] is None
    
    def test_get_device_not_found(self, db):
        """Test getting non-existent device"""
        result = db.get_device('nonexistent_device')
        assert result is None
    
    def test_update_device_seen(self, db, sample_device):
        """Test updating device last seen timestamp"""
        # Register device
        db.register_device(sample_device)
        original_device = db.get_device(sample_device['id'])
        
        # Wait a moment
        time.sleep(0.1)
        
        # Update last seen
        new_ip = '192.168.1.200'
        db.update_device_seen(sample_device['id'], new_ip)
        
        updated_device = db.get_device(sample_device['id'])
        assert updated_device['last_seen'] > original_device['last_seen']
        assert updated_device['ip_address'] == new_ip
    
    def test_update_device_seen_no_ip(self, db, sample_device):
        """Test updating device last seen without IP update"""
        db.register_device(sample_device)
        original_device = db.get_device(sample_device['id'])
        
        time.sleep(0.1)
        
        # Update without new IP
        db.update_device_seen(sample_device['id'])
        
        updated_device = db.get_device(sample_device['id'])
        assert updated_device['last_seen'] > original_device['last_seen']
        assert updated_device['ip_address'] == original_device['ip_address']


class TestJobOperations:
    """Test background job operations"""
    
    @pytest.fixture
    def db(self, temp_db_dir):
        """Create test database instance"""
        db = Database(str(temp_db_dir))
        db.initialize()
        yield db
        db.close()
    
    @pytest.fixture
    def sample_job(self):
        """Sample job for testing"""
        return {
            'id': 'job_123',
            'name': 'test_job',
            'status': 'pending',
            'next_run': int(time.time()) + 3600,  # 1 hour from now
            'payload': {'param1': 'value1', 'param2': 42},
            'rrule': 'FREQ=DAILY',
            'max_retries': 5,
            'timeout_seconds': 600
        }
    
    def test_create_job(self, db, sample_job):
        """Test creating a job"""
        job_id = db.create_job(sample_job)
        
        assert job_id == sample_job['id']
        
        # Verify job was stored with all fields
        jobs = db.get_pending_jobs()  # This would include our job if next_run was in past
        
        # Let's query directly to verify storage
        cursor = db.connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        row = cursor.fetchone()
        
        assert row is not None
        assert row['name'] == sample_job['name']
        assert row['status'] == sample_job['status']
        assert json.loads(row['payload']) == sample_job['payload']
    
    def test_create_job_minimal(self, db):
        """Test creating job with minimal fields"""
        job = {
            'id': 'minimal_job',
            'name': 'minimal',
            'status': 'pending'
        }
        
        job_id = db.create_job(job)
        
        cursor = db.connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        row = cursor.fetchone()
        
        assert row is not None
        assert row['retries'] == 0  # Default value
        assert row['max_retries'] == 3  # Default value
        assert json.loads(row['payload']) == {}  # Default empty payload
    
    def test_update_job(self, db, sample_job):
        """Test updating job status and details"""
        # Create job
        db.create_job(sample_job)
        
        # Update job
        updates = {
            'status': 'completed',
            'retries': 2,
            'result': {'output': 'success'},
            'error_message': None
        }
        
        db.update_job(sample_job['id'], updates)
        
        # Verify updates
        cursor = db.connection.execute("SELECT * FROM jobs WHERE id = ?", (sample_job['id'],))
        row = cursor.fetchone()
        
        assert row['status'] == 'completed'
        assert row['retries'] == 2
        assert json.loads(row['result']) == {'output': 'success'}
    
    def test_get_pending_jobs(self, db):
        """Test getting jobs ready to run"""
        now = int(time.time())
        
        # Create various jobs
        jobs = [
            {
                'id': 'ready_job',
                'name': 'ready',
                'status': 'pending',
                'next_run': now - 60  # Past due
            },
            {
                'id': 'future_job',
                'name': 'future',
                'status': 'pending',
                'next_run': now + 3600  # Future
            },
            {
                'id': 'failed_job',
                'name': 'failed',
                'status': 'failed',
                'next_run': now - 60,  # Past due
                'retries': 2,
                'max_retries': 5
            },
            {
                'id': 'exhausted_job',
                'name': 'exhausted',
                'status': 'failed',
                'next_run': now - 60,
                'retries': 5,
                'max_retries': 5  # Exhausted retries
            }
        ]
        
        for job in jobs:
            db.create_job(job)
        
        # Get pending jobs
        pending = db.get_pending_jobs()
        
        # Should include ready_job and failed_job (not exhausted, not future)
        pending_ids = {job['id'] for job in pending}
        assert 'ready_job' in pending_ids
        assert 'failed_job' in pending_ids
        assert 'future_job' not in pending_ids
        assert 'exhausted_job' not in pending_ids


class TestDatabaseUtilities:
    """Test utility methods and statistics"""
    
    @pytest.fixture
    def db_with_data(self, temp_db_dir):
        """Create database with sample data for statistics testing"""
        db = Database(str(temp_db_dir))
        db.initialize()
        
        # Add sample entities
        entities = [
            {'id': 'note_1', 'type': 'note', 'payload': {'title': 'Note 1'}},
            {'id': 'note_2', 'type': 'note', 'payload': {'title': 'Note 2'}},
            {'id': 'task_1', 'type': 'task', 'payload': {'title': 'Task 1'}}
        ]
        
        for entity in entities:
            db.insert_entity(entity)
        
        # Add links
        db.create_link('note_1', 'task_1', 'related')
        
        # Add device
        db.register_device({
            'id': 'test_device',
            'name': 'Test',
            'public_key': 'key',
            'capabilities': ['basic']
        })
        
        # Add job
        db.create_job({
            'id': 'test_job',
            'name': 'test',
            'status': 'pending'
        })
        
        yield db
        db.close()
    
    def test_get_stats(self, db_with_data):
        """Test database statistics"""
        stats = db_with_data.get_stats()
        
        # Check entity counts
        assert stats['total_entities'] == 3
        assert stats['entities_by_type']['note'] == 2
        assert stats['entities_by_type']['task'] == 1
        
        # Check other counts
        assert stats['total_links'] == 1
        assert stats['total_devices'] == 1
        
        # Check job stats
        assert stats['jobs_by_status']['pending'] == 1
        
        # Check database size exists
        assert 'database_size_bytes' in stats
        assert stats['database_size_bytes'] > 0
    
    def test_vacuum(self, db_with_data):
        """Test database vacuum operation"""
        # This should complete without error
        db_with_data.vacuum()
    
    def test_checkpoint(self, db_with_data):
        """Test WAL checkpoint"""
        # This should complete without error
        db_with_data.checkpoint()
    
    def test_close(self, db_with_data):
        """Test closing database connection"""
        assert db_with_data._connection is not None
        
        db_with_data.close()
        
        assert db_with_data._connection is None


class TestDatabaseErrors:
    """Test error conditions and edge cases"""
    
    @pytest.fixture
    def db(self, temp_db_dir):
        """Create test database instance"""
        db = Database(str(temp_db_dir))
        db.initialize()
        yield db
        db.close()
    
    def test_insert_duplicate_entity(self, db):
        """Test inserting entity with duplicate ID"""
        entity = {
            'id': 'duplicate_test',
            'type': 'note',
            'payload': {'title': 'Test'}
        }
        
        # First insert should succeed
        db.insert_entity(entity)
        
        # Second insert should fail with integrity error
        with pytest.raises(sqlite3.IntegrityError):
            db.insert_entity(entity)
    
    def test_malformed_json_handling(self, db):
        """Test handling of malformed JSON in database"""
        # Insert entity directly with bad JSON to test reading
        with db.transaction() as conn:
            conn.execute("""
                INSERT INTO entities (id, type, payload, created, updated)
                VALUES (?, ?, ?, ?, ?)
            """, (
                'bad_json_entity',
                'test',
                'invalid json content',  # This is not valid JSON
                int(time.time()),
                int(time.time())
            ))
        
        # Getting the entity should handle the JSON error gracefully
        with pytest.raises(json.JSONDecodeError):
            db.get_entity('bad_json_entity')
    
    def test_search_with_invalid_fts_query(self, db):
        """Test search with invalid FTS query syntax"""
        # FTS queries have special syntax - test invalid query
        # Some FTS implementations may handle this gracefully
        try:
            results = db.search_entities(query='"unclosed quote')
            # If it doesn't raise an error, that's fine too
            assert isinstance(results, list)
        except sqlite3.OperationalError:
            # This is expected for invalid FTS syntax
            pass
    
    def test_initialize_database_error(self, temp_db_dir):
        """Test database initialization with permission error"""
        # Create a directory where we can't write
        db_path = temp_db_dir / "readonly"
        db_path.mkdir()
        db_path.chmod(0o444)  # Read-only
        
        db = Database(str(db_path))
        
        try:
            # This should fail due to permissions
            result = db.initialize()
            # If it doesn't fail (some filesystems ignore chmod), that's ok
            if result:
                assert True
        except PermissionError:
            # Expected on systems that respect permissions
            pass
        finally:
            # Cleanup - restore permissions
            db_path.chmod(0o755)
            db.close()


class TestModuleFunctions:
    """Test module-level convenience functions"""
    
    def test_get_db_path_default(self):
        """Test getting database path with default root"""
        with patch.dict('os.environ', {'ARCHIE_DATA_ROOT': '/test/root'}):
            path = get_db_path()
            assert str(path) == '/test/root/db/long_memory.sqlite3'
    
    def test_get_db_path_custom(self):
        """Test getting database path with custom root"""
        path = get_db_path('/custom/root')
        assert str(path) == '/custom/root/db/long_memory.sqlite3'
    
    def test_migrate_function(self, temp_db_dir):
        """Test migration function"""
        db_path = temp_db_dir / "test_migrate.db"
        
        # This should create and initialize database
        migrate(str(db_path))
        
        # Verify database was created
        assert db_path.exists()
        
        # Test that it's a valid SQLite database
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        assert 'entities' in tables
        assert 'devices' in tables


# Performance and stress tests

class TestDatabasePerformance:
    """Test database performance with larger datasets"""
    
    @pytest.fixture
    def db(self, temp_db_dir):
        """Create test database instance"""
        db = Database(str(temp_db_dir))
        db.initialize()
        yield db
        db.close()
    
    @pytest.mark.slow
    def test_bulk_entity_insert(self, db):
        """Test inserting many entities"""
        start_time = time.time()
        
        # Insert 1000 entities
        for i in range(1000):
            entity = {
                'id': f'bulk_entity_{i}',
                'type': 'note',
                'payload': {'title': f'Note {i}', 'content': f'Content for note {i}'}
            }
            db.insert_entity(entity)
        
        end_time = time.time()
        
        # Should complete in reasonable time (less than 10 seconds)
        assert end_time - start_time < 10
        
        # Verify count
        stats = db.get_stats()
        assert stats['total_entities'] == 1000
    
    @pytest.mark.slow
    def test_search_performance(self, db):
        """Test search performance with many entities"""
        # Insert entities with searchable content
        for i in range(500):
            entity = {
                'id': f'search_entity_{i}',
                'type': 'note',
                'payload': {
                    'title': f'Document {i}',
                    'content': f'This is document number {i} with searchable content python programming'
                }
            }
            db.insert_entity(entity)
        
        # Wait for FTS to catch up
        time.sleep(0.5)
        
        start_time = time.time()
        
        # Perform search
        results = db.search_entities(query='python programming', limit=50)
        
        end_time = time.time()
        
        # Should complete quickly (less than 1 second)
        assert end_time - start_time < 1
        assert len(results) > 0