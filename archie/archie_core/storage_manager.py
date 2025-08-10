"""
ArchieOS Storage Manager - File system layer for intelligent storage management
"""
import os
import json
import shutil
import hashlib
import mimetypes
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import uuid
import logging

logger = logging.getLogger(__name__)


class ArchieStorageManager:
    """
    ArchieOS Storage Manager - The file system brain of our mini OS
    """
    
    # Plugin-aware folder structure
    PLUGIN_FOLDERS = {
        'calendar': 'Calendar events and scheduling data',
        'reminders': 'Task reminders and to-do items',
        'health': 'Health tracking and fitness data', 
        'finance': 'Financial records and budgets',
        'media': 'Images, videos, and multimedia content',
        'journal': 'Personal journal entries and reflections',
        'research': 'Research documents and notes',
        'tasks': 'Task management and project files'
    }
    
    # Storage tiers
    STORAGE_TIERS = {
        'hot': 'storage',      # Active, frequently accessed
        'warm': 'storage',     # Occasionally accessed
        'cold': 'storage/cold', # Archived, rarely accessed
        'vault': 'storage/vault' # Encrypted, sensitive data
    }
    
    def __init__(self, base_path: str = None):
        if base_path is None:
            # Use absolute path relative to this file
            base_dir = Path(__file__).parent.parent
            base_path = base_dir / "storage"
        
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self._init_storage_structure()
        
        logger.info("🗂️ Archie Storage Manager initialized - File system ready!")
    
    def _init_storage_structure(self):
        """Initialize the ArchieOS storage directory structure"""
        # Create main storage directories
        directories = [
            'plugins', 'media', 'vault', 'cold', 'temp', 'exports', 'backups'
        ]
        
        for directory in directories:
            (self.base_path / directory).mkdir(exist_ok=True)
        
        # Create plugin-specific directories
        for plugin_name in self.PLUGIN_FOLDERS:
            plugin_path = self.base_path / 'plugins' / plugin_name
            plugin_path.mkdir(exist_ok=True)
            
            # Create subdirectories for organized storage
            for subdir in ['data', 'exports', 'backups', 'temp']:
                (plugin_path / subdir).mkdir(exist_ok=True)
        
        logger.info(f"📁 Storage structure initialized at {self.base_path}")
    
    def store_file(
        self,
        file_content: bytes,
        filename: str,
        plugin: Optional[str] = None,
        category: str = 'data',
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        tier: str = 'hot'
    ) -> Dict[str, Any]:
        """
        Store a file in the ArchieOS with intelligent organization
        
        Returns file information including path, hash, and metadata
        """
        # Generate unique file ID
        file_id = str(uuid.uuid4())
        file_hash = hashlib.sha256(file_content).hexdigest()
        
        # Determine storage path
        if plugin and plugin in self.PLUGIN_FOLDERS:
            storage_path = self.base_path / 'plugins' / plugin / category
        else:
            storage_path = self.base_path / 'media'
        
        storage_path.mkdir(parents=True, exist_ok=True)
        
        # Generate safe filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_filename = self._sanitize_filename(filename)
        final_filename = f"{timestamp}_{file_id[:8]}_{safe_filename}"
        file_path = storage_path / final_filename
        
        # Write file
        with open(file_path, 'wb') as f:
            f.write(file_content)
        
        # Detect MIME type
        mime_type, _ = mimetypes.guess_type(filename)
        
        # Create metadata
        file_info = {
            'id': file_id,
            'original_filename': filename,
            'stored_filename': final_filename,
            'path': str(file_path.relative_to(self.base_path)),
            'absolute_path': str(file_path),
            'size_bytes': len(file_content),
            'hash': file_hash,
            'mime_type': mime_type,
            'plugin': plugin,
            'category': category,
            'tier': tier,
            'tags': tags or [],
            'metadata': metadata or {},
            'created_at': datetime.now().isoformat(),
            'accessed_at': datetime.now().isoformat(),
            'access_count': 0
        }
        
        # Store metadata file
        metadata_path = file_path.with_suffix(f"{file_path.suffix}.meta.json")
        with open(metadata_path, 'w') as f:
            json.dump(file_info, f, indent=2)
        
        # Log the storage with Archie's personality
        logger.info(f"📁 Archie: Filed {filename} in {plugin or 'media'} storage - {len(file_content)} bytes archived!")
        
        return file_info
    
    def retrieve_file(self, file_id: str) -> Optional[Tuple[bytes, Dict[str, Any]]]:
        """Retrieve a file by ID with metadata"""
        file_info = self.get_file_info(file_id)
        if not file_info:
            return None
        
        file_path = Path(file_info['absolute_path'])
        if not file_path.exists():
            logger.warning(f"🚨 File {file_id} metadata exists but file is missing!")
            return None
        
        # Update access statistics
        self._update_access_stats(file_info)
        
        # Read and return file content
        with open(file_path, 'rb') as f:
            content = f.read()
        
        logger.info(f"📤 Archie: Retrieved {file_info['original_filename']} - access count now {file_info['access_count'] + 1}")
        return content, file_info
    
    def search_files(
        self,
        query: Optional[str] = None,
        plugin: Optional[str] = None,
        tags: Optional[List[str]] = None,
        mime_type: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        tier: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Search files with multiple filter options"""
        results = []
        
        # Search through all metadata files
        for meta_file in self.base_path.rglob("*.meta.json"):
            try:
                with open(meta_file, 'r') as f:
                    file_info = json.load(f)
                
                # Apply filters
                if plugin and file_info.get('plugin') != plugin:
                    continue
                
                if mime_type and not (file_info.get('mime_type', '').startswith(mime_type)):
                    continue
                
                if tier and file_info.get('tier') != tier:
                    continue
                
                if tags:
                    file_tags = set(file_info.get('tags', []))
                    if not set(tags).intersection(file_tags):
                        continue
                
                if date_from or date_to:
                    created_at = datetime.fromisoformat(file_info['created_at'])
                    if date_from and created_at < date_from:
                        continue
                    if date_to and created_at > date_to:
                        continue
                
                if query:
                    # Search in filename, tags, and metadata
                    searchable_text = " ".join([
                        file_info['original_filename'],
                        " ".join(file_info.get('tags', [])),
                        json.dumps(file_info.get('metadata', {}))
                    ]).lower()
                    
                    if query.lower() not in searchable_text:
                        continue
                
                results.append(file_info)
                
                if len(results) >= limit:
                    break
                    
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"⚠️ Corrupted metadata file: {meta_file}")
                continue
        
        # Sort by most recently created
        results.sort(key=lambda x: x['created_at'], reverse=True)
        
        logger.info(f"🔍 Archie: Found {len(results)} files matching your search criteria")
        return results
    
    def get_file_info(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Get file metadata by ID"""
        for meta_file in self.base_path.rglob("*.meta.json"):
            try:
                with open(meta_file, 'r') as f:
                    file_info = json.load(f)
                
                if file_info.get('id') == file_id:
                    return file_info
                    
            except (json.JSONDecodeError, KeyError):
                continue
        
        return None
    
    def delete_file(self, file_id: str) -> bool:
        """Delete a file and its metadata"""
        file_info = self.get_file_info(file_id)
        if not file_info:
            return False
        
        file_path = Path(file_info['absolute_path'])
        metadata_path = file_path.with_suffix(f"{file_path.suffix}.meta.json")
        
        # Remove files
        try:
            if file_path.exists():
                file_path.unlink()
            if metadata_path.exists():
                metadata_path.unlink()
            
            logger.info(f"🗑️ Archie: Removed {file_info['original_filename']} from the archives")
            return True
            
        except OSError as e:
            logger.error(f"❌ Failed to delete file {file_id}: {e}")
            return False
    
    def move_to_tier(self, file_id: str, target_tier: str) -> bool:
        """Move file to different storage tier (hot/warm/cold/vault)"""
        if target_tier not in self.STORAGE_TIERS:
            return False
        
        file_info = self.get_file_info(file_id)
        if not file_info:
            return False
        
        current_path = Path(file_info['absolute_path'])
        target_base = self.base_path / self.STORAGE_TIERS[target_tier]
        
        # Maintain plugin structure in new tier
        if file_info.get('plugin'):
            target_dir = target_base / 'plugins' / file_info['plugin'] / file_info['category']
        else:
            target_dir = target_base / 'media'
        
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / current_path.name
        
        try:
            shutil.move(str(current_path), str(target_path))
            
            # Update metadata
            file_info['tier'] = target_tier
            file_info['absolute_path'] = str(target_path)
            file_info['path'] = str(target_path.relative_to(self.base_path))
            
            metadata_path = target_path.with_suffix(f"{target_path.suffix}.meta.json")
            with open(metadata_path, 'w') as f:
                json.dump(file_info, f, indent=2)
            
            # Remove old metadata
            old_metadata = current_path.with_suffix(f"{current_path.suffix}.meta.json")
            if old_metadata.exists():
                old_metadata.unlink()
            
            logger.info(f"📦 Archie: Moved {file_info['original_filename']} to {target_tier} storage")
            return True
            
        except OSError as e:
            logger.error(f"❌ Failed to move file to {target_tier}: {e}")
            return False
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """Get comprehensive storage statistics"""
        stats = {
            'total_files': 0,
            'total_size_bytes': 0,
            'files_by_plugin': {},
            'files_by_tier': {},
            'files_by_type': {},
            'storage_usage': {}
        }
        
        # Count files and calculate sizes
        for meta_file in self.base_path.rglob("*.meta.json"):
            try:
                with open(meta_file, 'r') as f:
                    file_info = json.load(f)
                
                stats['total_files'] += 1
                file_size = file_info.get('size_bytes', 0)
                stats['total_size_bytes'] += file_size
                
                # By plugin
                plugin = file_info.get('plugin', 'media')
                stats['files_by_plugin'][plugin] = stats['files_by_plugin'].get(plugin, 0) + 1
                
                # By tier
                tier = file_info.get('tier', 'hot')
                stats['files_by_tier'][tier] = stats['files_by_tier'].get(tier, 0) + 1
                
                # By MIME type
                mime_type = file_info.get('mime_type', 'unknown')
                mime_category = mime_type.split('/')[0] if '/' in mime_type else 'unknown'
                stats['files_by_type'][mime_category] = stats['files_by_type'].get(mime_category, 0) + 1
                
            except (json.JSONDecodeError, KeyError):
                continue
        
        # Calculate directory sizes
        for directory in ['plugins', 'media', 'vault', 'cold', 'exports', 'backups']:
            dir_path = self.base_path / directory
            if dir_path.exists():
                size = sum(f.stat().st_size for f in dir_path.rglob('*') if f.is_file())
                stats['storage_usage'][directory] = size
        
        stats['total_size_mb'] = round(stats['total_size_bytes'] / (1024 * 1024), 2)
        
        logger.info(f"📊 Storage stats: {stats['total_files']} files, {stats['total_size_mb']}MB")
        return stats
    
    def cleanup_temp_files(self, older_than_days: int = 1) -> int:
        """Clean up temporary files older than specified days"""
        cutoff_date = datetime.now() - timedelta(days=older_than_days)
        temp_dir = self.base_path / 'temp'
        
        cleaned_count = 0
        if temp_dir.exists():
            for file_path in temp_dir.rglob('*'):
                if file_path.is_file():
                    file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if file_time < cutoff_date:
                        try:
                            file_path.unlink()
                            cleaned_count += 1
                        except OSError:
                            pass
        
        logger.info(f"🧹 Archie: Cleaned up {cleaned_count} temporary files")
        return cleaned_count
    
    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for safe storage"""
        # Remove or replace problematic characters
        unsafe_chars = '<>:"/\\|?*'
        for char in unsafe_chars:
            filename = filename.replace(char, '_')
        
        # Limit length
        if len(filename) > 200:
            name, ext = os.path.splitext(filename)
            filename = name[:200-len(ext)] + ext
        
        return filename
    
    def _update_access_stats(self, file_info: Dict[str, Any]):
        """Update file access statistics"""
        file_info['accessed_at'] = datetime.now().isoformat()
        file_info['access_count'] = file_info.get('access_count', 0) + 1
        
        # Save updated metadata
        file_path = Path(file_info['absolute_path'])
        metadata_path = file_path.with_suffix(f"{file_path.suffix}.meta.json")
        
        try:
            with open(metadata_path, 'w') as f:
                json.dump(file_info, f, indent=2)
        except OSError:
            logger.warning("⚠️ Could not update access statistics")
    
    def close(self):
        """Clean shutdown"""
        logger.info("🏁 Archie Storage Manager shutting down gracefully")