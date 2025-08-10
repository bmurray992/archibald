"""
Archie's Memory Manager - Core memory storage and retrieval functionality
"""
import sqlite3
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class MemoryManager:
    """
    Archie's memory management system - the heart of long-term storage
    """
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            # Use absolute path relative to this file
            base_dir = Path(__file__).parent.parent
            db_path = base_dir / "database" / "memory.db"
        
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
    
    def _init_database(self):
        """Initialize the database with schema"""
        schema_path = Path(__file__).parent.parent / "database" / "schema.sql"
        
        with sqlite3.connect(self.db_path) as conn:
            # Enable foreign keys and JSON support
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode = WAL")
            
            if schema_path.exists():
                with open(schema_path, 'r') as f:
                    conn.executescript(f.read())
            
            logger.info("🗃️ Archie: Database initialized and ready for archiving!")
    
    def store_memory(
        self,
        content: str,
        entry_type: str,
        assistant_id: str = "percy",
        plugin_source: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        confidence: float = 1.0,
        source_method: str = "ui"
    ) -> int:
        """
        Store a new memory entry - Archie's bread and butter!
        
        Returns the ID of the stored memory entry
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            tags_str = ",".join(tags) if tags else ""
            metadata_json = json.dumps(metadata) if metadata else None
            
            cursor.execute("""
                INSERT INTO memory_entries 
                (assistant_id, plugin_source, entry_type, content, metadata, tags, confidence, source_method)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                assistant_id, plugin_source, entry_type, content,
                metadata_json, tags_str, confidence, source_method
            ))
            
            memory_id = cursor.lastrowid
            
            # Log the storage using the same connection
            self._log_audit("write", "memory_entries", assistant_id, "success", 
                           f"Stored memory entry ID {memory_id}", conn)
            
            logger.info(f"📚 Archie: Filed away memory #{memory_id} - {entry_type}")
            return memory_id
    
    def search_memories(
        self,
        query: Optional[str] = None,
        entry_type: Optional[str] = None,
        assistant_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        limit: int = 50,
        archived: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Search through memories - Archie's specialty!
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Build dynamic query
            conditions = ["archived = ?"]
            params = [archived]
            
            if query:
                # Use FTS for text search
                cursor.execute("""
                    SELECT rowid FROM memory_fts WHERE memory_fts MATCH ?
                """, (query,))
                fts_results = [row[0] for row in cursor.fetchall()]
                
                if fts_results:
                    placeholders = ",".join("?" * len(fts_results))
                    conditions.append(f"id IN ({placeholders})")
                    params.extend(fts_results)
                else:
                    # No FTS matches, return empty
                    return []
            
            if entry_type:
                conditions.append("entry_type = ?")
                params.append(entry_type)
            
            if assistant_id:
                conditions.append("assistant_id = ?")
                params.append(assistant_id)
            
            if tags:
                for tag in tags:
                    conditions.append("tags LIKE ?")
                    params.append(f"%{tag}%")
            
            if date_from:
                conditions.append("timestamp >= ?")
                params.append(date_from.isoformat())
            
            if date_to:
                conditions.append("timestamp <= ?")
                params.append(date_to.isoformat())
            
            where_clause = " AND ".join(conditions)
            
            cursor.execute(f"""
                SELECT * FROM memory_entries 
                WHERE {where_clause}
                ORDER BY timestamp DESC
                LIMIT ?
            """, params + [limit])
            
            results = []
            for row in cursor.fetchall():
                memory = dict(row)
                if memory['metadata']:
                    memory['metadata'] = json.loads(memory['metadata'])
                if memory['tags']:
                    memory['tags'] = memory['tags'].split(',')
                results.append(memory)
            
            # Log the search using the same connection
            self._log_audit("read", "memory_entries", assistant_id or "unknown", 
                           "success", f"Retrieved {len(results)} memories", conn)
            
            logger.info(f"🔍 Archie: Found {len(results)} memories matching your query")
            return results
    
    def store_interaction(
        self,
        user_message: str,
        assistant_response: str,
        assistant_id: str = "percy",
        context: Optional[str] = None,
        session_id: Optional[str] = None,
        plugin_used: Optional[str] = None,
        intent_detected: Optional[str] = None
    ) -> int:
        """Store a conversation interaction"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO interactions 
                (assistant_id, user_message, assistant_response, context, session_id, plugin_used, intent_detected)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (assistant_id, user_message, assistant_response, context, session_id, plugin_used, intent_detected))
            
            interaction_id = cursor.lastrowid
            logger.info(f"💬 Archie: Logged interaction #{interaction_id}")
            return interaction_id
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Get statistics about stored memories"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Total entries
            cursor.execute("SELECT COUNT(*) FROM memory_entries WHERE archived = FALSE")
            total_entries = cursor.fetchone()[0]
            
            # Entries by type
            cursor.execute("""
                SELECT entry_type, COUNT(*) 
                FROM memory_entries 
                WHERE archived = FALSE 
                GROUP BY entry_type
            """)
            by_type = dict(cursor.fetchall())
            
            # Recent activity (last 7 days)
            week_ago = (datetime.now() - timedelta(days=7)).isoformat()
            cursor.execute("""
                SELECT COUNT(*) FROM memory_entries 
                WHERE timestamp >= ? AND archived = FALSE
            """, (week_ago,))
            recent_activity = cursor.fetchone()[0]
            
            # Database size
            cursor.execute("PRAGMA page_count")
            page_count = cursor.fetchone()[0]
            cursor.execute("PRAGMA page_size")
            page_size = cursor.fetchone()[0]
            db_size_mb = (page_count * page_size) / (1024 * 1024)
            
            stats = {
                "total_entries": total_entries,
                "entries_by_type": by_type,
                "recent_activity_7d": recent_activity,
                "database_size_mb": round(db_size_mb, 2),
                "last_updated": datetime.now().isoformat()
            }
            
            logger.info(f"📊 Archie: Current stats - {total_entries} entries, {db_size_mb:.1f}MB")
            return stats
    
    def archive_old_memories(self, days_old: int = 90) -> int:
        """Archive memories older than specified days"""
        cutoff_date = (datetime.now() - timedelta(days=days_old)).isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE memory_entries 
                SET archived = TRUE 
                WHERE timestamp < ? AND archived = FALSE
            """, (cutoff_date,))
            
            archived_count = cursor.rowcount
            
            # Log pruning activity
            cursor.execute("""
                INSERT INTO pruning_history (rule_type, entries_affected, details)
                VALUES (?, ?, ?)
            """, ("age", archived_count, f"Archived memories older than {days_old} days"))
            
            logger.info(f"🧹 Archie: Archived {archived_count} old memories. Tidy!")
            return archived_count
    
    def _log_audit(self, action: str, resource: str, assistant_id: str, 
                   status: str, details: str = "", conn=None):
        """Log audit trail"""
        if conn is None:
            # Use a separate connection if not provided
            with sqlite3.connect(self.db_path) as audit_conn:
                cursor = audit_conn.cursor()
                cursor.execute("""
                    INSERT INTO audit_log (assistant_id, action, resource, status, details)
                    VALUES (?, ?, ?, ?, ?)
                """, (assistant_id, action, resource, status, details))
        else:
            # Use provided connection (within existing transaction)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO audit_log (assistant_id, action, resource, status, details)
                VALUES (?, ?, ?, ?, ?)
            """, (assistant_id, action, resource, status, details))
    
    def close(self):
        """Clean shutdown"""
        logger.info("🏁 Archie: Memory manager shutting down gracefully")