"""
ArchieOS File Manager
Handles file operations, metadata tracking, and storage management
"""
import os
import hashlib
import mimetypes
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, BinaryIO
import json
import shutil

from .storage_config import get_storage_config


class FileMetadata:
    """File metadata container"""
    def __init__(self, **kwargs):
        self.filename = kwargs.get('filename', '')
        self.original_name = kwargs.get('original_name', '')
        self.file_path = kwargs.get('file_path', '')
        self.file_size = kwargs.get('file_size', 0)
        self.mime_type = kwargs.get('mime_type', '')
        self.file_hash = kwargs.get('file_hash', '')
        self.created_at = kwargs.get('created_at', datetime.now())
        self.modified_at = kwargs.get('modified_at', datetime.now())
        self.tags = kwargs.get('tags', [])
        self.plugin_source = kwargs.get('plugin_source', '')
        self.storage_tier = kwargs.get('storage_tier', 'uploads')
        self.archived = kwargs.get('archived', False)
        self.description = kwargs.get('description', '')
        self.metadata = kwargs.get('metadata', {})


class ArchieFileManager:
    """Advanced file management system for ArchieOS"""
    
    def __init__(self):
        self.storage_config = get_storage_config()
        self.db_path = self.storage_config.get_path("indexes", "files.db")
        self.init_database()
    
    def init_database(self):
        """Initialize the file metadata database"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT NOT NULL,
                    original_name TEXT NOT NULL,
                    file_path TEXT NOT NULL UNIQUE,
                    file_size INTEGER NOT NULL,
                    mime_type TEXT,
                    file_hash TEXT UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    modified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    plugin_source TEXT,
                    storage_tier TEXT DEFAULT 'uploads',
                    archived BOOLEAN DEFAULT FALSE,
                    description TEXT,
                    metadata TEXT  -- JSON string
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS file_tags (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_id INTEGER,
                    tag TEXT,
                    FOREIGN KEY (file_id) REFERENCES files (id),
                    UNIQUE(file_id, tag)
                )
            """)
            
            # Create indexes for better performance
            conn.execute("CREATE INDEX IF NOT EXISTS idx_files_hash ON files(file_hash)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_files_created_at ON files(created_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_files_plugin ON files(plugin_source)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tags_tag ON file_tags(tag)")
            
            conn.commit()
    
    def calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA-256 hash of file"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    
    def store_file(self, 
                   file_content: BinaryIO, 
                   original_filename: str,
                   storage_tier: str = "uploads",
                   plugin_source: str = "",
                   tags: List[str] = None,
                   description: str = "",
                   metadata: Dict = None) -> Tuple[str, FileMetadata]:
        """Store a file with metadata tracking"""
        if tags is None:
            tags = []
        if metadata is None:
            metadata = {}
        
        # Generate unique filename to avoid conflicts
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        name, ext = os.path.splitext(original_filename)
        safe_name = "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        unique_filename = f"{safe_name}_{timestamp}{ext}"
        
        # Determine storage path
        storage_path = self.storage_config.get_path(storage_tier, unique_filename)
        storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write file to storage
        with open(storage_path, 'wb') as f:
            shutil.copyfileobj(file_content, f)
        
        # Calculate file metadata
        file_size = storage_path.stat().st_size
        mime_type, _ = mimetypes.guess_type(original_filename)
        file_hash = self.calculate_file_hash(storage_path)
        
        # Check for duplicates
        existing_file = self.get_file_by_hash(file_hash)
        if existing_file:
            # Remove the duplicate file we just created
            storage_path.unlink()
            return existing_file.filename, existing_file
        
        # Create metadata object
        file_metadata = FileMetadata(
            filename=unique_filename,
            original_name=original_filename,
            file_path=str(storage_path),
            file_size=file_size,
            mime_type=mime_type or 'application/octet-stream',
            file_hash=file_hash,
            plugin_source=plugin_source,
            storage_tier=storage_tier,
            tags=tags,
            description=description,
            metadata=metadata
        )
        
        # Store in database
        self.save_file_metadata(file_metadata)
        
        return unique_filename, file_metadata
    
    def save_file_metadata(self, file_metadata: FileMetadata) -> int:
        """Save file metadata to database"""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute("""
                INSERT INTO files (
                    filename, original_name, file_path, file_size, mime_type, 
                    file_hash, plugin_source, storage_tier, archived, 
                    description, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                file_metadata.filename,
                file_metadata.original_name,
                file_metadata.file_path,
                file_metadata.file_size,
                file_metadata.mime_type,
                file_metadata.file_hash,
                file_metadata.plugin_source,
                file_metadata.storage_tier,
                file_metadata.archived,
                file_metadata.description,
                json.dumps(file_metadata.metadata)
            ))
            
            file_id = cursor.lastrowid
            
            # Save tags
            for tag in file_metadata.tags:
                conn.execute(
                    "INSERT OR IGNORE INTO file_tags (file_id, tag) VALUES (?, ?)",
                    (file_id, tag.lower().strip())
                )
            
            conn.commit()
            return file_id
    
    def get_file_by_hash(self, file_hash: str) -> Optional[FileMetadata]:
        """Get file metadata by hash"""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute(
                "SELECT * FROM files WHERE file_hash = ?", (file_hash,)
            )
            row = cursor.fetchone()
            
            if row:
                return self._row_to_metadata(conn, row)
            return None
    
    def get_file_by_filename(self, filename: str) -> Optional[FileMetadata]:
        """Get file metadata by filename"""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute(
                "SELECT * FROM files WHERE filename = ?", (filename,)
            )
            row = cursor.fetchone()
            
            if row:
                return self._row_to_metadata(conn, row)
            return None
    
    def search_files(self, 
                     query: str = "",
                     tags: List[str] = None,
                     plugin_source: str = "",
                     storage_tier: str = "",
                     limit: int = 50) -> List[FileMetadata]:
        """Search files by various criteria"""
        if tags is None:
            tags = []
        
        with sqlite3.connect(str(self.db_path)) as conn:
            sql = "SELECT DISTINCT f.* FROM files f"
            params = []
            conditions = []
            
            if tags:
                sql += " JOIN file_tags ft ON f.id = ft.file_id"
                tag_conditions = " OR ".join(["ft.tag = ?"] * len(tags))
                conditions.append(f"({tag_conditions})")
                params.extend(tags)
            
            if query:
                conditions.append("(f.filename LIKE ? OR f.original_name LIKE ? OR f.description LIKE ?)")
                query_param = f"%{query}%"
                params.extend([query_param, query_param, query_param])
            
            if plugin_source:
                conditions.append("f.plugin_source = ?")
                params.append(plugin_source)
            
            if storage_tier:
                conditions.append("f.storage_tier = ?")
                params.append(storage_tier)
            
            if conditions:
                sql += " WHERE " + " AND ".join(conditions)
            
            sql += " ORDER BY f.created_at DESC LIMIT ?"
            params.append(limit)
            
            cursor = conn.execute(sql, params)
            rows = cursor.fetchall()
            
            return [self._row_to_metadata(conn, row) for row in rows]
    
    def get_recent_files(self, limit: int = 20) -> List[FileMetadata]:
        """Get recently uploaded files"""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute(
                "SELECT * FROM files ORDER BY created_at DESC LIMIT ?", (limit,)
            )
            rows = cursor.fetchall()
            return [self._row_to_metadata(conn, row) for row in rows]
    
    def get_files_by_plugin(self, plugin_name: str, limit: int = 50) -> List[FileMetadata]:
        """Get files associated with a specific plugin"""
        return self.search_files(plugin_source=plugin_name, limit=limit)
    
    def move_to_cold_storage(self, file_id: int) -> bool:
        """Move file to cold storage"""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute("SELECT * FROM files WHERE id = ?", (file_id,))
            row = cursor.fetchone()
            
            if not row:
                return False
            
            file_metadata = self._row_to_metadata(conn, row)
            old_path = Path(file_metadata.file_path)
            
            if not old_path.exists():
                return False
            
            # Move to cold storage
            cold_path = self.storage_config.get_path("cold", file_metadata.filename)
            cold_path.parent.mkdir(parents=True, exist_ok=True)
            
            shutil.move(str(old_path), str(cold_path))
            
            # Update database
            conn.execute(
                "UPDATE files SET file_path = ?, storage_tier = ?, archived = ? WHERE id = ?",
                (str(cold_path), "cold", True, file_id)
            )
            conn.commit()
            
            return True
    
    def delete_file(self, filename: str) -> bool:
        """Delete a file and its metadata"""
        file_metadata = self.get_file_by_filename(filename)
        if not file_metadata:
            return False
        
        # Delete physical file
        file_path = Path(file_metadata.file_path)
        if file_path.exists():
            file_path.unlink()
        
        # Delete from database
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("DELETE FROM file_tags WHERE file_id IN (SELECT id FROM files WHERE filename = ?)", (filename,))
            conn.execute("DELETE FROM files WHERE filename = ?", (filename,))
            conn.commit()
        
        return True
    
    def get_storage_stats(self) -> Dict[str, any]:
        """Get comprehensive storage statistics"""
        stats = self.storage_config.get_storage_stats()
        
        with sqlite3.connect(str(self.db_path)) as conn:
            # Get file counts by storage tier
            cursor = conn.execute("""
                SELECT storage_tier, COUNT(*), SUM(file_size) 
                FROM files 
                GROUP BY storage_tier
            """)
            
            tier_stats = {}
            for row in cursor.fetchall():
                tier, count, total_size = row
                tier_stats[tier] = {
                    "file_count": count,
                    "total_size": total_size or 0
                }
            
            # Get total counts
            cursor = conn.execute("SELECT COUNT(*), SUM(file_size) FROM files")
            total_files, total_size = cursor.fetchone()
            
            stats["database"] = {
                "total_files": total_files or 0,
                "total_size": total_size or 0,
                "by_tier": tier_stats
            }
        
        return stats
    
    def _row_to_metadata(self, conn: sqlite3.Connection, row: tuple) -> FileMetadata:
        """Convert database row to FileMetadata object"""
        columns = [
            'id', 'filename', 'original_name', 'file_path', 'file_size', 
            'mime_type', 'file_hash', 'created_at', 'modified_at', 
            'plugin_source', 'storage_tier', 'archived', 'description', 'metadata'
        ]
        
        file_data = dict(zip(columns, row))
        
        # Parse metadata JSON
        if file_data['metadata']:
            try:
                file_data['metadata'] = json.loads(file_data['metadata'])
            except json.JSONDecodeError:
                file_data['metadata'] = {}
        else:
            file_data['metadata'] = {}
        
        # Get tags
        cursor = conn.execute("SELECT tag FROM file_tags WHERE file_id = ?", (file_data['id'],))
        file_data['tags'] = [row[0] for row in cursor.fetchall()]
        
        return FileMetadata(**file_data)