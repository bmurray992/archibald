#!/usr/bin/env python3
"""
Migration 001: Unified Entities Schema
Transforms existing memory_entries to the new unified entities system
"""
import sqlite3
import json
import time
from datetime import datetime
from pathlib import Path
import logging
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from archie_core.models import EntityType

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1

def get_db_path():
    """Get database path from environment or default"""
    data_root = os.getenv("ARCHIE_DATA_ROOT", "./storage")
    return Path(data_root) / "db" / "long_memory.sqlite3"

def backup_database(db_path):
    """Create backup before migration"""
    backup_path = db_path.with_suffix('.sqlite3.backup_001')
    logger.info(f"Creating backup at {backup_path}")
    
    # Use SQLite backup API
    source = sqlite3.connect(db_path)
    backup = sqlite3.connect(backup_path)
    source.backup(backup)
    source.close()
    backup.close()
    
    return backup_path

def create_new_schema(conn):
    """Create the new unified entities schema"""
    logger.info("Creating new schema...")
    
    cur = conn.cursor()
    cur.executescript("""
    -- Core entities table
    CREATE TABLE IF NOT EXISTS entities (
        id TEXT PRIMARY KEY,
        type TEXT NOT NULL,
        payload TEXT NOT NULL,  -- JSON
        created INTEGER NOT NULL,
        updated INTEGER NOT NULL,
        tags TEXT,  -- JSON array
        assistant_id TEXT DEFAULT 'archie',
        sensitive BOOLEAN DEFAULT FALSE,
        archived BOOLEAN DEFAULT FALSE
    );
    
    -- Entity relationships
    CREATE TABLE IF NOT EXISTS links (
        src TEXT NOT NULL,
        dst TEXT NOT NULL,
        type TEXT NOT NULL,
        created INTEGER NOT NULL,
        metadata TEXT,  -- JSON
        PRIMARY KEY (src, dst, type)
    );
    
    -- Full-text search on entities
    CREATE VIRTUAL TABLE IF NOT EXISTS fts_entities USING fts5(
        id UNINDEXED,
        type UNINDEXED,
        text,
        content='',
        tokenize='porter'
    );
    
    -- Device registry
    CREATE TABLE IF NOT EXISTS devices (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        public_key TEXT NOT NULL,
        capabilities TEXT NOT NULL,  -- JSON array
        last_seen INTEGER,
        device_type TEXT,
        os_version TEXT,
        app_version TEXT,
        ip_address TEXT,
        council_member TEXT
    );
    
    -- Background jobs
    CREATE TABLE IF NOT EXISTS jobs (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        status TEXT NOT NULL,
        last_run INTEGER,
        next_run INTEGER,
        payload TEXT,  -- JSON
        retries INTEGER DEFAULT 0,
        rrule TEXT,
        max_retries INTEGER DEFAULT 3,
        timeout_seconds INTEGER DEFAULT 300,
        error_message TEXT,
        result TEXT  -- JSON
    );
    
    -- Settings (migrated from existing)
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    );
    
    -- Indexes for performance
    CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(type);
    CREATE INDEX IF NOT EXISTS idx_entities_created ON entities(created);
    CREATE INDEX IF NOT EXISTS idx_entities_assistant ON entities(assistant_id);
    CREATE INDEX IF NOT EXISTS idx_entities_archived ON entities(archived);
    CREATE INDEX IF NOT EXISTS idx_links_src ON links(src);
    CREATE INDEX IF NOT EXISTS idx_links_dst ON links(dst);
    CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
    CREATE INDEX IF NOT EXISTS idx_jobs_next_run ON jobs(next_run);
    """)
    
    conn.commit()
    logger.info("New schema created successfully")

def migrate_memory_entries(conn):
    """Migrate existing memory_entries to entities table"""
    logger.info("Migrating memory entries...")
    
    cur = conn.cursor()
    
    # Check if memory_entries exists
    cur.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='memory_entries'
    """)
    
    if not cur.fetchone():
        logger.info("No memory_entries table found, skipping migration")
        return 0
    
    # Get all memory entries
    cur.execute("""
        SELECT id, assistant_id, plugin_source, timestamp, entry_type, 
               content, metadata, tags, confidence, source_method, 
               archived, created_at, updated_at
        FROM memory_entries
    """)
    
    entries = cur.fetchall()
    migrated_count = 0
    
    for entry in entries:
        try:
            # Parse the old entry
            entry_id = entry[0] or f"memory_{int(time.time() * 1000)}_{migrated_count}"
            assistant_id = entry[1] or 'percy'
            plugin_source = entry[2]
            timestamp = entry[3]
            entry_type = entry[4] or 'memory_entry'
            content = entry[5]
            metadata = json.loads(entry[6]) if entry[6] else {}
            tags = entry[7].split(',') if entry[7] else []
            confidence = entry[8] or 1.0
            source_method = entry[9]
            archived = bool(entry[10])
            created_at = entry[11]
            updated_at = entry[12]
            
            # Convert timestamps
            created_ts = int(datetime.fromisoformat(created_at).timestamp()) if created_at else int(time.time())
            updated_ts = int(datetime.fromisoformat(updated_at).timestamp()) if updated_at else created_ts
            
            # Build payload based on entry type
            if entry_type == 'interaction':
                payload = {
                    'id': entry_id,
                    'content': content,
                    'metadata': metadata,
                    'confidence': confidence,
                    'source_method': source_method,
                    'plugin_source': plugin_source,
                    'timestamp': timestamp
                }
                entity_type = EntityType.INTERACTION
            else:
                # Generic memory entry
                payload = {
                    'id': entry_id,
                    'content': content,
                    'entry_type': entry_type,
                    'metadata': metadata,
                    'confidence': confidence,
                    'source_method': source_method,
                    'plugin_source': plugin_source,
                    'timestamp': timestamp
                }
                entity_type = EntityType.MEMORY_ENTRY
            
            # Insert into entities table
            cur.execute("""
                INSERT INTO entities (id, type, payload, created, updated, 
                                    tags, assistant_id, sensitive, archived)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry_id,
                entity_type.value,
                json.dumps(payload),
                created_ts,
                updated_ts,
                json.dumps(tags),
                assistant_id,
                False,  # sensitive
                archived
            ))
            
            # Add to FTS index
            searchable_text = f"{content} {' '.join(tags)}"
            cur.execute("""
                INSERT INTO fts_entities (id, type, text)
                VALUES (?, ?, ?)
            """, (entry_id, entity_type.value, searchable_text))
            
            migrated_count += 1
            
        except Exception as e:
            logger.error(f"Failed to migrate entry {entry[0]}: {e}")
    
    conn.commit()
    logger.info(f"Migrated {migrated_count} memory entries")
    return migrated_count

def migrate_interactions(conn):
    """Migrate existing interactions to entities table"""
    logger.info("Migrating interactions...")
    
    cur = conn.cursor()
    
    # Check if interactions exists
    cur.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='interactions'
    """)
    
    if not cur.fetchone():
        logger.info("No interactions table found, skipping migration")
        return 0
    
    # Get all interactions
    cur.execute("""
        SELECT id, assistant_id, user_message, assistant_response, 
               context, timestamp, session_id, plugin_used, 
               intent_detected, created_at
        FROM interactions
    """)
    
    interactions = cur.fetchall()
    migrated_count = 0
    
    for interaction in interactions:
        try:
            # Parse the interaction
            interaction_id = f"interaction_{interaction[0]}"
            assistant_id = interaction[1] or 'percy'
            user_message = interaction[2]
            assistant_response = interaction[3]
            context = interaction[4]
            timestamp = interaction[5]
            session_id = interaction[6]
            plugin_used = interaction[7]
            intent_detected = interaction[8]
            created_at = interaction[9]
            
            # Convert timestamp
            created_ts = int(datetime.fromisoformat(created_at).timestamp()) if created_at else int(time.time())
            
            # Build payload
            payload = {
                'id': interaction_id,
                'user_message': user_message,
                'assistant_response': assistant_response,
                'context': context,
                'timestamp': timestamp,
                'session_id': session_id,
                'plugin_used': plugin_used,
                'intent_detected': intent_detected
            }
            
            # Insert into entities table
            cur.execute("""
                INSERT INTO entities (id, type, payload, created, updated, 
                                    tags, assistant_id, sensitive, archived)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                interaction_id,
                EntityType.INTERACTION.value,
                json.dumps(payload),
                created_ts,
                created_ts,
                '[]',
                assistant_id,
                False,
                False
            ))
            
            # Add to FTS index
            searchable_text = f"{user_message} {assistant_response}"
            cur.execute("""
                INSERT INTO fts_entities (id, type, text)
                VALUES (?, ?, ?)
            """, (interaction_id, EntityType.INTERACTION.value, searchable_text))
            
            migrated_count += 1
            
        except Exception as e:
            logger.error(f"Failed to migrate interaction {interaction[0]}: {e}")
    
    conn.commit()
    logger.info(f"Migrated {migrated_count} interactions")
    return migrated_count

def update_schema_version(conn):
    """Update schema version in meta/settings"""
    cur = conn.cursor()
    
    # Check if meta table exists
    cur.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='meta'
    """)
    
    if cur.fetchone():
        cur.execute("INSERT OR REPLACE INTO meta(key, value) VALUES('schema_version', ?)", (SCHEMA_VERSION,))
    
    # Also update in settings
    cur.execute("INSERT OR REPLACE INTO settings(key, value) VALUES('schema_version', ?)", (str(SCHEMA_VERSION),))
    
    conn.commit()
    logger.info(f"Updated schema version to {SCHEMA_VERSION}")

def verify_migration(conn):
    """Verify the migration was successful"""
    cur = conn.cursor()
    
    # Count entities
    cur.execute("SELECT COUNT(*) FROM entities")
    entity_count = cur.fetchone()[0]
    
    # Count by type
    cur.execute("SELECT type, COUNT(*) FROM entities GROUP BY type")
    type_counts = cur.fetchall()
    
    # Check FTS
    cur.execute("SELECT COUNT(*) FROM fts_entities")
    fts_count = cur.fetchone()[0]
    
    logger.info("Migration verification:")
    logger.info(f"  Total entities: {entity_count}")
    logger.info(f"  FTS entries: {fts_count}")
    logger.info("  Entities by type:")
    for entity_type, count in type_counts:
        logger.info(f"    {entity_type}: {count}")
    
    return entity_count > 0

def main():
    """Run the migration"""
    logger.info("Starting migration 001: Unified Entities Schema")
    
    # Get database path
    db_path = get_db_path()
    if not db_path.exists():
        logger.error(f"Database not found at {db_path}")
        return 1
    
    # Create backup
    backup_path = backup_database(db_path)
    logger.info(f"Backup created at {backup_path}")
    
    try:
        # Connect to database
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        
        # Create new schema
        create_new_schema(conn)
        
        # Migrate data
        memory_count = migrate_memory_entries(conn)
        interaction_count = migrate_interactions(conn)
        
        # Update schema version
        update_schema_version(conn)
        
        # Verify migration
        if verify_migration(conn):
            logger.info("Migration completed successfully!")
            logger.info(f"Migrated {memory_count} memory entries and {interaction_count} interactions")
        else:
            logger.error("Migration verification failed!")
            return 1
        
        conn.close()
        return 0
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        logger.info(f"Database backup available at {backup_path}")
        return 1

if __name__ == "__main__":
    sys.exit(main())