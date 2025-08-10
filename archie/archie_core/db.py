"""
ArchieOS Database Module - SQLite with unified entities schema
"""
import sqlite3
import os
import time
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from contextlib import contextmanager
from datetime import datetime

logger = logging.getLogger(__name__)

CURRENT_SCHEMA_VERSION = 1

class Database:
    """Database connection and operations manager"""
    
    def __init__(self, data_root: Optional[str] = None):
        if data_root is None:
            data_root = os.getenv("ARCHIE_DATA_ROOT", "./storage")
        
        self.data_root = Path(data_root)
        self.db_path = self.get_db_path()
        self._ensure_directories()
        self._connection = None
        
    def get_db_path(self) -> Path:
        """Get the database file path"""
        return self.data_root / "db" / "long_memory.sqlite3"
    
    def _ensure_directories(self):
        """Ensure required directories exist"""
        db_dir = self.db_path.parent
        db_dir.mkdir(parents=True, exist_ok=True)
        
        # Create other required directories
        for subdir in ["media_vault", "thumbnails", "indexes", "snapshots"]:
            (self.data_root / subdir).mkdir(parents=True, exist_ok=True)
    
    @property
    def connection(self) -> sqlite3.Connection:
        """Get or create database connection"""
        if self._connection is None:
            self._connection = sqlite3.connect(
                str(self.db_path),
                isolation_level=None  # Autocommit mode
            )
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA journal_mode=WAL")
            self._connection.execute("PRAGMA foreign_keys=ON")
            
        return self._connection
    
    @contextmanager
    def transaction(self):
        """Context manager for database transactions"""
        conn = self.connection
        try:
            conn.execute("BEGIN")
            yield conn
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
    
    def initialize(self) -> bool:
        """Initialize database with schema"""
        try:
            current_version = self._get_schema_version()
            
            if current_version < CURRENT_SCHEMA_VERSION:
                logger.info(f"Database schema version {current_version}, migrating to {CURRENT_SCHEMA_VERSION}")
                self._migrate_schema(current_version)
            else:
                logger.info(f"Database schema up to date (version {current_version})")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            return False
    
    def _get_schema_version(self) -> int:
        """Get current schema version"""
        try:
            # Try settings table first
            cur = self.connection.execute(
                "SELECT value FROM settings WHERE key = 'schema_version'"
            )
            row = cur.fetchone()
            if row:
                return int(row['value'])
            
            # Try meta table (legacy)
            cur = self.connection.execute(
                "SELECT value FROM meta WHERE key = 'schema_version'"
            )
            row = cur.fetchone()
            if row:
                return int(row['value'])
                
        except sqlite3.OperationalError:
            # Tables don't exist yet
            pass
        
        return 0
    
    def _migrate_schema(self, from_version: int):
        """Run migrations to bring schema up to date"""
        if from_version == 0:
            # Fresh install - create schema directly
            self._create_schema()
            self._set_schema_version(CURRENT_SCHEMA_VERSION)
        else:
            # Run migrations
            migrations_dir = Path(__file__).parent.parent / "migrations"
            
            for version in range(from_version + 1, CURRENT_SCHEMA_VERSION + 1):
                migration_file = migrations_dir / f"{version:03d}_*.py"
                # Import and run migration
                # This is simplified - in production you'd want more robust migration handling
                logger.info(f"Running migration {version}")
                self._set_schema_version(version)
    
    def _create_schema(self):
        """Create the database schema from scratch"""
        self.connection.executescript("""
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
        
        -- Files table (existing, enhanced)
        CREATE TABLE IF NOT EXISTS files (
            id TEXT PRIMARY KEY,
            hash TEXT NOT NULL,
            path TEXT NOT NULL,
            size INTEGER NOT NULL,
            created INTEGER NOT NULL,
            tags TEXT,  -- JSON array
            meta TEXT  -- JSON metadata
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
        
        -- Settings
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        
        -- Council members
        CREATE TABLE IF NOT EXISTS council_members (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            role TEXT NOT NULL,
            capabilities TEXT NOT NULL,  -- JSON array
            endpoint_url TEXT,
            public_key TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            joined_at INTEGER NOT NULL
        );
        
        -- Council meetings
        CREATE TABLE IF NOT EXISTS council_meetings (
            id TEXT PRIMARY KEY,
            summoner TEXT NOT NULL,
            topic TEXT NOT NULL,
            participants TEXT NOT NULL,  -- JSON array
            status TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            completed_at INTEGER,
            context TEXT,  -- JSON
            deliberations TEXT,  -- JSON array
            draft_response TEXT,
            final_response TEXT
        );
        
        -- Audit log (existing, for compatibility)
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
        
        -- Create indexes
        CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(type);
        CREATE INDEX IF NOT EXISTS idx_entities_created ON entities(created);
        CREATE INDEX IF NOT EXISTS idx_entities_assistant ON entities(assistant_id);
        CREATE INDEX IF NOT EXISTS idx_entities_archived ON entities(archived);
        CREATE INDEX IF NOT EXISTS idx_links_src ON links(src);
        CREATE INDEX IF NOT EXISTS idx_links_dst ON links(dst);
        CREATE INDEX IF NOT EXISTS idx_files_hash ON files(hash);
        CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
        CREATE INDEX IF NOT EXISTS idx_jobs_next_run ON jobs(next_run);
        CREATE INDEX IF NOT EXISTS idx_devices_council ON devices(council_member);
        
        -- Create triggers to sync FTS
        CREATE TRIGGER IF NOT EXISTS entities_ai AFTER INSERT ON entities
        BEGIN
            INSERT INTO fts_entities (id, type, text)
            SELECT NEW.id, NEW.type, json_extract(NEW.payload, '$.content') || ' ' || 
                   COALESCE(json_extract(NEW.payload, '$.title'), '') || ' ' ||
                   COALESCE(json_extract(NEW.payload, '$.snippet'), '') || ' ' ||
                   COALESCE(json_extract(NEW.payload, '$.subject'), '');
        END;
        
        CREATE TRIGGER IF NOT EXISTS entities_ad AFTER DELETE ON entities
        BEGIN
            DELETE FROM fts_entities WHERE id = OLD.id;
        END;
        
        CREATE TRIGGER IF NOT EXISTS entities_au AFTER UPDATE ON entities
        BEGIN
            DELETE FROM fts_entities WHERE id = OLD.id;
            INSERT INTO fts_entities (id, type, text)
            SELECT NEW.id, NEW.type, json_extract(NEW.payload, '$.content') || ' ' || 
                   COALESCE(json_extract(NEW.payload, '$.title'), '') || ' ' ||
                   COALESCE(json_extract(NEW.payload, '$.snippet'), '') || ' ' ||
                   COALESCE(json_extract(NEW.payload, '$.subject'), '');
        END;
        """)
        
        logger.info("Database schema created successfully")
    
    def _set_schema_version(self, version: int):
        """Update schema version"""
        self.connection.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES ('schema_version', ?)",
            (str(version),)
        )
    
    # Entity operations
    
    def insert_entity(self, entity: Dict[str, Any]) -> str:
        """Insert a new entity"""
        with self.transaction() as conn:
            conn.execute("""
                INSERT INTO entities (id, type, payload, created, updated, 
                                    tags, assistant_id, sensitive, archived)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entity['id'],
                entity['type'],
                json.dumps(entity['payload']),
                entity.get('created', int(time.time())),
                entity.get('updated', int(time.time())),
                json.dumps(entity.get('tags', [])),
                entity.get('assistant_id', 'archie'),
                entity.get('sensitive', False),
                entity.get('archived', False)
            ))
        
        return entity['id']
    
    def update_entity(self, entity_id: str, updates: Dict[str, Any]) -> bool:
        """Update an existing entity"""
        with self.transaction() as conn:
            # Get current entity
            cur = conn.execute(
                "SELECT payload FROM entities WHERE id = ?",
                (entity_id,)
            )
            row = cur.fetchone()
            if not row:
                return False
            
            # Update payload
            payload = json.loads(row['payload'])
            payload.update(updates.get('payload', {}))
            
            # Update entity
            conn.execute("""
                UPDATE entities 
                SET payload = ?, updated = ?, tags = ?
                WHERE id = ?
            """, (
                json.dumps(payload),
                int(time.time()),
                json.dumps(updates.get('tags', [])),
                entity_id
            ))
        
        return True
    
    def get_entity(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Get a single entity by ID"""
        cur = self.connection.execute(
            "SELECT * FROM entities WHERE id = ?",
            (entity_id,)
        )
        row = cur.fetchone()
        
        if row:
            return {
                'id': row['id'],
                'type': row['type'],
                'payload': json.loads(row['payload']),
                'created': row['created'],
                'updated': row['updated'],
                'tags': json.loads(row['tags']) if row['tags'] else [],
                'assistant_id': row['assistant_id'],
                'sensitive': bool(row['sensitive']),
                'archived': bool(row['archived'])
            }
        
        return None
    
    def search_entities(self, 
                       query: Optional[str] = None,
                       entity_type: Optional[str] = None,
                       tags: Optional[List[str]] = None,
                       since: Optional[int] = None,
                       until: Optional[int] = None,
                       limit: int = 50,
                       offset: int = 0,
                       include_archived: bool = False) -> List[Dict[str, Any]]:
        """Search entities with various filters"""
        
        # Build query
        where_clauses = []
        params = []
        
        if entity_type:
            where_clauses.append("e.type = ?")
            params.append(entity_type)
        
        if not include_archived:
            where_clauses.append("e.archived = 0")
        
        if since:
            where_clauses.append("e.created >= ?")
            params.append(since)
        
        if until:
            where_clauses.append("e.created <= ?")
            params.append(until)
        
        # Handle text search
        if query:
            # Use FTS
            fts_query = f"""
                SELECT e.* FROM entities e
                JOIN fts_entities f ON e.id = f.id
                WHERE f.text MATCH ?
                {' AND ' + ' AND '.join(where_clauses) if where_clauses else ''}
                ORDER BY rank
                LIMIT ? OFFSET ?
            """
            params.insert(0, query)
        else:
            # Regular query
            fts_query = f"""
                SELECT * FROM entities e
                {' WHERE ' + ' AND '.join(where_clauses) if where_clauses else ''}
                ORDER BY created DESC
                LIMIT ? OFFSET ?
            """
        
        params.extend([limit, offset])
        
        cur = self.connection.execute(fts_query, params)
        
        results = []
        for row in cur:
            results.append({
                'id': row['id'],
                'type': row['type'],
                'payload': json.loads(row['payload']),
                'created': row['created'],
                'updated': row['updated'],
                'tags': json.loads(row['tags']) if row['tags'] else [],
                'assistant_id': row['assistant_id'],
                'sensitive': bool(row['sensitive']),
                'archived': bool(row['archived'])
            })
        
        return results
    
    def delete_entity(self, entity_id: str) -> bool:
        """Delete an entity"""
        with self.transaction() as conn:
            conn.execute("DELETE FROM entities WHERE id = ?", (entity_id,))
            conn.execute("DELETE FROM links WHERE src = ? OR dst = ?", (entity_id, entity_id))
        
        return True
    
    # Link operations
    
    def create_link(self, src: str, dst: str, link_type: str, metadata: Optional[Dict] = None):
        """Create a link between entities"""
        with self.transaction() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO links (src, dst, type, created, metadata)
                VALUES (?, ?, ?, ?, ?)
            """, (
                src, dst, link_type,
                int(time.time()),
                json.dumps(metadata or {})
            ))
    
    def get_links(self, entity_id: str, direction: str = "both") -> List[Dict[str, Any]]:
        """Get all links for an entity"""
        links = []
        
        if direction in ("both", "outgoing"):
            cur = self.connection.execute(
                "SELECT * FROM links WHERE src = ?",
                (entity_id,)
            )
            for row in cur:
                links.append({
                    'src': row['src'],
                    'dst': row['dst'],
                    'type': row['type'],
                    'created': row['created'],
                    'metadata': json.loads(row['metadata']) if row['metadata'] else {},
                    'direction': 'outgoing'
                })
        
        if direction in ("both", "incoming"):
            cur = self.connection.execute(
                "SELECT * FROM links WHERE dst = ?",
                (entity_id,)
            )
            for row in cur:
                links.append({
                    'src': row['src'],
                    'dst': row['dst'],
                    'type': row['type'],
                    'created': row['created'],
                    'metadata': json.loads(row['metadata']) if row['metadata'] else {},
                    'direction': 'incoming'
                })
        
        return links
    
    # Device operations
    
    def register_device(self, device: Dict[str, Any]) -> str:
        """Register a new device"""
        with self.transaction() as conn:
            conn.execute("""
                INSERT INTO devices (id, name, public_key, capabilities, 
                                   last_seen, device_type, os_version, 
                                   app_version, ip_address, council_member)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                device['id'],
                device['name'],
                device['public_key'],
                json.dumps(device['capabilities']),
                int(time.time()),
                device.get('device_type'),
                device.get('os_version'),
                device.get('app_version'),
                device.get('ip_address'),
                device.get('council_member')
            ))
        
        return device['id']
    
    def get_device(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Get device by ID"""
        cur = self.connection.execute(
            "SELECT * FROM devices WHERE id = ?",
            (device_id,)
        )
        row = cur.fetchone()
        
        if row:
            return {
                'id': row['id'],
                'name': row['name'],
                'public_key': row['public_key'],
                'capabilities': json.loads(row['capabilities']),
                'last_seen': row['last_seen'],
                'device_type': row['device_type'],
                'os_version': row['os_version'],
                'app_version': row['app_version'],
                'ip_address': row['ip_address'],
                'council_member': row['council_member']
            }
        
        return None
    
    def update_device_seen(self, device_id: str, ip_address: Optional[str] = None):
        """Update device last seen timestamp"""
        with self.transaction() as conn:
            if ip_address:
                conn.execute(
                    "UPDATE devices SET last_seen = ?, ip_address = ? WHERE id = ?",
                    (int(time.time()), ip_address, device_id)
                )
            else:
                conn.execute(
                    "UPDATE devices SET last_seen = ? WHERE id = ?",
                    (int(time.time()), device_id)
                )
    
    # Job operations
    
    def create_job(self, job: Dict[str, Any]) -> str:
        """Create a new job"""
        with self.transaction() as conn:
            conn.execute("""
                INSERT INTO jobs (id, name, status, last_run, next_run, 
                                payload, retries, rrule, max_retries, 
                                timeout_seconds, error_message, result)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job['id'],
                job['name'],
                job['status'],
                job.get('last_run'),
                job.get('next_run'),
                json.dumps(job.get('payload', {})),
                job.get('retries', 0),
                job.get('rrule'),
                job.get('max_retries', 3),
                job.get('timeout_seconds', 300),
                job.get('error_message'),
                json.dumps(job.get('result')) if job.get('result') else None
            ))
        
        return job['id']
    
    def update_job(self, job_id: str, updates: Dict[str, Any]):
        """Update job status and details"""
        set_clauses = []
        params = []
        
        for key, value in updates.items():
            if key in ('payload', 'result'):
                set_clauses.append(f"{key} = ?")
                params.append(json.dumps(value))
            else:
                set_clauses.append(f"{key} = ?")
                params.append(value)
        
        params.append(job_id)
        
        with self.transaction() as conn:
            conn.execute(
                f"UPDATE jobs SET {', '.join(set_clauses)} WHERE id = ?",
                params
            )
    
    def get_pending_jobs(self) -> List[Dict[str, Any]]:
        """Get jobs ready to run"""
        cur = self.connection.execute("""
            SELECT * FROM jobs 
            WHERE status IN ('pending', 'failed') 
            AND (next_run IS NULL OR next_run <= ?)
            AND retries < max_retries
            ORDER BY next_run
        """, (int(time.time()),))
        
        jobs = []
        for row in cur:
            jobs.append({
                'id': row['id'],
                'name': row['name'],
                'status': row['status'],
                'last_run': row['last_run'],
                'next_run': row['next_run'],
                'payload': json.loads(row['payload']) if row['payload'] else {},
                'retries': row['retries'],
                'rrule': row['rrule'],
                'max_retries': row['max_retries'],
                'timeout_seconds': row['timeout_seconds'],
                'error_message': row['error_message'],
                'result': json.loads(row['result']) if row['result'] else None
            })
        
        return jobs
    
    # Utility methods
    
    def vacuum(self):
        """Optimize database"""
        self.connection.execute("VACUUM")
    
    def checkpoint(self):
        """Checkpoint WAL"""
        self.connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        stats = {}
        
        # Entity counts
        cur = self.connection.execute(
            "SELECT type, COUNT(*) as count FROM entities GROUP BY type"
        )
        stats['entities_by_type'] = {row['type']: row['count'] for row in cur}
        
        # Total entities
        cur = self.connection.execute("SELECT COUNT(*) as count FROM entities")
        stats['total_entities'] = cur.fetchone()['count']
        
        # Link count
        cur = self.connection.execute("SELECT COUNT(*) as count FROM links")
        stats['total_links'] = cur.fetchone()['count']
        
        # Device count
        cur = self.connection.execute("SELECT COUNT(*) as count FROM devices")
        stats['total_devices'] = cur.fetchone()['count']
        
        # Job stats
        cur = self.connection.execute(
            "SELECT status, COUNT(*) as count FROM jobs GROUP BY status"
        )
        stats['jobs_by_status'] = {row['status']: row['count'] for row in cur}
        
        # Database size
        cur = self.connection.execute("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
        stats['database_size_bytes'] = cur.fetchone()['size']
        
        return stats
    
    def close(self):
        """Close database connection"""
        if self._connection:
            self._connection.close()
            self._connection = None


# Module-level functions for backward compatibility and convenience

def get_db_path(root: Optional[str] = None) -> Path:
    """Get database path"""
    if root is None:
        root = os.getenv("ARCHIE_DATA_ROOT", "./storage")
    return Path(root) / "db" / "long_memory.sqlite3"


def migrate(db_path: Optional[str] = None):
    """Run database migrations"""
    if db_path is None:
        db_path = str(get_db_path())
    
    db = Database()
    db.initialize()
    db.close()
    
    logger.info(f"Database migrated at {db_path}")


if __name__ == "__main__":
    # Run migration when called directly
    migrate()
    print("Database initialized successfully")