"""
Indexer Job - Incremental FTS and vector index refresh
"""
import logging
from datetime import datetime, timedelta
from .scheduler import JobResult
from ..db import Database

logger = logging.getLogger(__name__)


async def indexer_handler(payload):
    """Rebuild or refresh search indexes"""
    try:
        mode = payload.get("mode", "incremental")
        
        db = Database()
        db.initialize()
        
        if mode == "full_rebuild":
            result = await _full_rebuild_indexes(db)
        else:
            result = await _incremental_index_update(db)
        
        db.close()
        return result
        
    except Exception as e:
        logger.error(f"Indexer job failed: {e}")
        return JobResult(
            success=False,
            message=f"Index update failed: {str(e)}"
        )


async def _incremental_index_update(db: Database) -> JobResult:
    """Update FTS index for recently modified entities"""
    try:
        # Find entities modified in last hour
        one_hour_ago = int((datetime.now() - timedelta(hours=1)).timestamp())
        
        # Get recently updated entities
        entities = db.search_entities(
            since=one_hour_ago,
            limit=1000,
            include_archived=True
        )
        
        if not entities:
            return JobResult(
                success=True,
                message="No entities to index",
                data={"indexed_count": 0}
            )
        
        indexed_count = 0
        
        with db.transaction() as conn:
            for entity in entities:
                try:
                    # Extract searchable text from entity payload
                    payload = entity['payload']
                    searchable_text = _extract_searchable_text(payload)
                    
                    # Update FTS index
                    conn.execute(
                        "INSERT OR REPLACE INTO fts_entities (id, type, text) VALUES (?, ?, ?)",
                        (entity['id'], entity['type'], searchable_text)
                    )
                    
                    indexed_count += 1
                    
                except Exception as e:
                    logger.warning(f"Failed to index entity {entity['id']}: {e}")
        
        logger.info(f"🔍 Incrementally indexed {indexed_count} entities")
        
        return JobResult(
            success=True,
            message=f"Incremental index update completed",
            data={
                "indexed_count": indexed_count,
                "mode": "incremental"
            }
        )
        
    except Exception as e:
        logger.error(f"Incremental indexing failed: {e}")
        return JobResult(
            success=False,
            message=f"Incremental indexing failed: {str(e)}"
        )


async def _full_rebuild_indexes(db: Database) -> JobResult:
    """Full rebuild of all search indexes"""
    try:
        logger.info("🔄 Starting full index rebuild...")
        
        with db.transaction() as conn:
            # Clear existing FTS data
            conn.execute("DELETE FROM fts_entities")
            
            # Get all entities
            all_entities = db.search_entities(
                limit=100000,  # Large limit to get all
                include_archived=True
            )
            
            indexed_count = 0
            
            for entity in all_entities:
                try:
                    # Extract searchable text
                    payload = entity['payload']
                    searchable_text = _extract_searchable_text(payload)
                    
                    # Insert into FTS
                    conn.execute(
                        "INSERT INTO fts_entities (id, type, text) VALUES (?, ?, ?)",
                        (entity['id'], entity['type'], searchable_text)
                    )
                    
                    indexed_count += 1
                    
                    if indexed_count % 1000 == 0:
                        logger.info(f"   Indexed {indexed_count} entities...")
                        
                except Exception as e:
                    logger.warning(f"Failed to index entity {entity['id']}: {e}")
            
            # Optimize FTS index
            conn.execute("INSERT INTO fts_entities(fts_entities) VALUES('optimize')")
        
        logger.info(f"✅ Full index rebuild completed: {indexed_count} entities")
        
        return JobResult(
            success=True,
            message="Full index rebuild completed",
            data={
                "indexed_count": indexed_count,
                "mode": "full_rebuild"
            }
        )
        
    except Exception as e:
        logger.error(f"Full index rebuild failed: {e}")
        return JobResult(
            success=False,
            message=f"Full index rebuild failed: {str(e)}"
        )


def _extract_searchable_text(payload: dict) -> str:
    """Extract searchable text from entity payload"""
    searchable_fields = []
    
    # Common fields across entity types
    for field in ['content', 'title', 'snippet', 'subject', 'description', 'memo']:
        if field in payload and payload[field]:
            searchable_fields.append(str(payload[field]))
    
    # Special handling for specific entity types
    if 'user_message' in payload:
        searchable_fields.append(str(payload['user_message']))
    if 'assistant_response' in payload:
        searchable_fields.append(str(payload['assistant_response']))
    
    if 'ingredients' in payload and isinstance(payload['ingredients'], list):
        searchable_fields.extend(payload['ingredients'])
    
    if 'instructions' in payload and isinstance(payload['instructions'], list):
        searchable_fields.extend(payload['instructions'])
    
    # Join all searchable text
    return ' '.join(searchable_fields)