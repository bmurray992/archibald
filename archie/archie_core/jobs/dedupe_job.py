"""
Dedupe Job - Content hash deduplication and cleanup
"""
import hashlib
import logging
import os
from pathlib import Path
from collections import defaultdict
from .scheduler import JobResult
from ..db import Database

logger = logging.getLogger(__name__)


async def dedupe_handler(payload):
    """Deduplicate files based on content hash"""
    try:
        min_file_size = payload.get("min_file_size", 1024)  # Skip files < 1KB by default
        dry_run = payload.get("dry_run", False)
        
        db = Database()
        db.initialize()
        
        result = await _deduplicate_files(db, min_file_size, dry_run)
        
        db.close()
        return result
        
    except Exception as e:
        logger.error(f"Dedupe job failed: {e}")
        return JobResult(
            success=False,
            message=f"Deduplication failed: {str(e)}"
        )


async def _deduplicate_files(db: Database, min_file_size: int, dry_run: bool) -> JobResult:
    """Find and merge duplicate files"""
    try:
        # Get all files from database
        cur = db.connection.execute(
            "SELECT id, hash, path, size FROM files WHERE size >= ? ORDER BY size DESC",
            (min_file_size,)
        )
        
        all_files = cur.fetchall()
        
        if not all_files:
            return JobResult(
                success=True,
                message="No files to process",
                data={"duplicates_found": 0, "bytes_saved": 0}
            )
        
        logger.info(f"🔍 Analyzing {len(all_files)} files for duplicates...")
        
        # Group files by hash
        hash_groups = defaultdict(list)
        for file_row in all_files:
            file_info = {
                'id': file_row['id'],
                'hash': file_row['hash'],
                'path': file_row['path'],
                'size': file_row['size']
            }
            hash_groups[file_row['hash']].append(file_info)
        
        # Find duplicate groups (hash appears more than once)
        duplicate_groups = {h: files for h, files in hash_groups.items() if len(files) > 1}
        
        if not duplicate_groups:
            return JobResult(
                success=True,
                message="No duplicates found",
                data={"duplicates_found": 0, "bytes_saved": 0}
            )
        
        logger.info(f"📋 Found {len(duplicate_groups)} duplicate groups")
        
        total_bytes_saved = 0
        total_files_removed = 0
        deduped_groups = 0
        
        data_root = Path(os.getenv("ARCHIE_DATA_ROOT", "./storage"))
        
        with db.transaction() as conn:
            for file_hash, duplicate_files in duplicate_groups.items():
                try:
                    # Sort by creation time - keep the oldest
                    duplicate_files.sort(key=lambda f: _get_file_creation_time(data_root / f['path']))
                    
                    keeper = duplicate_files[0]  # Keep the first (oldest) file
                    duplicates_to_remove = duplicate_files[1:]
                    
                    logger.info(f"🔗 Deduplicating hash {file_hash[:8]}... (keeping {keeper['id']})")
                    
                    for duplicate in duplicates_to_remove:
                        file_path = data_root / duplicate['path']
                        
                        if not dry_run:
                            # Remove physical file
                            if file_path.exists():
                                file_path.unlink()
                                total_bytes_saved += duplicate['size']
                            
                            # Update database references to point to keeper
                            _merge_file_references(conn, duplicate['id'], keeper['id'])
                            
                            # Remove file record
                            conn.execute("DELETE FROM files WHERE id = ?", (duplicate['id'],))
                        else:
                            # Dry run - just count savings
                            if file_path.exists():
                                total_bytes_saved += duplicate['size']
                        
                        total_files_removed += 1
                    
                    deduped_groups += 1
                    
                except Exception as e:
                    logger.warning(f"Failed to dedupe group {file_hash}: {e}")
        
        action = "Would remove" if dry_run else "Removed"
        logger.info(f"✅ Deduplication complete:")
        logger.info(f"   {action} {total_files_removed} duplicate files")
        logger.info(f"   {action} {total_bytes_saved:,} bytes ({total_bytes_saved/1024/1024:.1f} MB)")
        logger.info(f"   Processed {deduped_groups} duplicate groups")
        
        return JobResult(
            success=True,
            message=f"Deduplication completed ({action.lower()} {total_files_removed} files)",
            data={
                "duplicates_found": total_files_removed,
                "bytes_saved": total_bytes_saved,
                "groups_processed": deduped_groups,
                "dry_run": dry_run
            }
        )
        
    except Exception as e:
        logger.error(f"File deduplication failed: {e}")
        return JobResult(
            success=False,
            message=f"Deduplication failed: {str(e)}"
        )


def _get_file_creation_time(file_path: Path) -> float:
    """Get file creation timestamp"""
    try:
        if file_path.exists():
            return file_path.stat().st_ctime
        return 0.0
    except:
        return 0.0


def _merge_file_references(conn, duplicate_id: str, keeper_id: str):
    """Update any entity references to point to the keeper file"""
    try:
        # Update entities that reference the duplicate file
        conn.execute("""
            UPDATE entities 
            SET payload = json_set(payload, '$.source_paths', 
                json_array_replace(
                    json_extract(payload, '$.source_paths'), 
                    ?, ?
                )
            )
            WHERE json_extract(payload, '$.source_paths') LIKE ?
        """, (duplicate_id, keeper_id, f'%{duplicate_id}%'))
        
        # Update any other file references in metadata
        conn.execute("""
            UPDATE entities 
            SET payload = replace(payload, ?, ?)
            WHERE payload LIKE ?
        """, (duplicate_id, keeper_id, f'%{duplicate_id}%'))
        
    except Exception as e:
        logger.warning(f"Failed to merge file references: {e}")


async def calculate_duplicate_stats() -> dict:
    """Calculate potential space savings from deduplication"""
    try:
        db = Database()
        db.initialize()
        
        # Group files by hash and size
        cur = db.connection.execute("""
            SELECT hash, COUNT(*) as count, size, COUNT(*) * size as total_size
            FROM files 
            GROUP BY hash, size
            HAVING COUNT(*) > 1
            ORDER BY total_size DESC
        """)
        
        duplicate_stats = []
        total_potential_savings = 0
        total_duplicate_files = 0
        
        for row in cur:
            duplicate_count = row['count'] - 1  # Keep one copy
            bytes_saveable = duplicate_count * row['size']
            total_potential_savings += bytes_saveable
            total_duplicate_files += duplicate_count
            
            duplicate_stats.append({
                'hash': row['hash'],
                'duplicate_count': duplicate_count,
                'file_size': row['size'],
                'bytes_saveable': bytes_saveable
            })
        
        db.close()
        
        return {
            'potential_savings_bytes': total_potential_savings,
            'potential_savings_mb': round(total_potential_savings / 1024 / 1024, 1),
            'duplicate_files_count': total_duplicate_files,
            'duplicate_groups': len(duplicate_stats),
            'top_duplicates': duplicate_stats[:10]  # Top 10 by savings
        }
        
    except Exception as e:
        logger.error(f"Failed to calculate duplicate stats: {e}")
        return {
            'error': str(e)
        }