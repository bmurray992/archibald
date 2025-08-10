"""
ArchieOS Typed Memory API - CRUD operations for unified entities
"""
import json
import logging
import time
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import ValidationError

from .db import Database
from .models import (
    EntityType, MemorySearchRequest, MemoryUpsertRequest,
    NoteSummary, Event, EmailThread, Task, Contact, Recipe, 
    Workout, HealthSummary, Transaction, MediaItem
)
from .events import emit_entity_event
from .auth import require_device_auth

logger = logging.getLogger(__name__)

# Entity type to model mapping
ENTITY_MODEL_MAP = {
    EntityType.NOTE: NoteSummary,
    EntityType.EVENT: Event,
    EntityType.EMAIL_THREAD: EmailThread,
    EntityType.TASK: Task,
    EntityType.CONTACT: Contact,
    EntityType.RECIPE: Recipe,
    EntityType.WORKOUT: Workout,
    EntityType.HEALTH_SUMMARY: HealthSummary,
    EntityType.TRANSACTION: Transaction,
    EntityType.MEDIA_ITEM: MediaItem
}

router = APIRouter(prefix="/api/memory", tags=["memory"])


class MemoryManager:
    """Manages typed entity operations"""
    
    def __init__(self):
        self.db = Database()
        self.db.initialize()
    
    async def upsert_entity(self, 
                           entity_type: EntityType, 
                           entity_data: Dict[str, Any],
                           tags: List[str] = None,
                           sensitive: bool = False,
                           device_id: Optional[str] = None) -> str:
        """Create or update a typed entity"""
        
        # Validate entity data against its model
        model_class = ENTITY_MODEL_MAP.get(entity_type)
        if not model_class:
            raise ValueError(f"Unsupported entity type: {entity_type}")
        
        try:
            # Validate the data
            validated_entity = model_class(**entity_data)
            entity_id = validated_entity.id
            
        except ValidationError as e:
            raise ValueError(f"Invalid {entity_type.value} data: {e}")
        
        # Check if entity exists
        existing_entity = self.db.get_entity(entity_id)
        action = "updated" if existing_entity else "created"
        
        # Prepare entity for storage
        entity = {
            'id': entity_id,
            'type': entity_type.value,
            'payload': validated_entity.dict(),
            'tags': tags or [],
            'assistant_id': device_id or 'unknown',
            'sensitive': sensitive,
            'archived': False
        }
        
        if existing_entity:
            # Update existing
            self.db.update_entity(entity_id, {
                'payload': validated_entity.dict(),
                'tags': tags or existing_entity.get('tags', [])
            })
        else:
            # Create new
            self.db.insert_entity(entity)
        
        # Emit event
        await emit_entity_event(action, entity_type.value, entity_id, {
            'sensitive': sensitive,
            'tags': tags or []
        })
        
        logger.info(f"📝 Entity {action}: {entity_type.value}/{entity_id}")
        return entity_id
    
    async def get_entity(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Get a single entity by ID"""
        entity = self.db.get_entity(entity_id)
        
        if entity:
            # Emit access event
            await emit_entity_event("accessed", entity['type'], entity_id, {})
            
        return entity
    
    async def search_entities(self, request: MemorySearchRequest) -> Dict[str, Any]:
        """Search entities with filters"""
        
        # Convert datetime to timestamps
        since_ts = int(request.since.timestamp()) if request.since else None
        until_ts = int(request.until.timestamp()) if request.until else None
        
        # Search database
        entities = self.db.search_entities(
            query=request.query,
            entity_type=request.type.value if request.type else None,
            tags=request.tags,
            since=since_ts,
            until=until_ts,
            limit=request.limit,
            offset=request.offset,
            include_archived=request.include_archived
        )
        
        # Get total count for pagination
        # TODO: Implement efficient count query
        total_count = len(entities) if len(entities) < request.limit else request.limit + 1
        
        # Emit search event
        await emit_entity_event("searched", "multiple", "", {
            'query': request.query,
            'type_filter': request.type.value if request.type else None,
            'results_count': len(entities)
        })
        
        return {
            'entities': entities,
            'total_count': total_count,
            'offset': request.offset,
            'limit': request.limit,
            'has_more': len(entities) == request.limit
        }
    
    async def delete_entity(self, entity_id: str) -> bool:
        """Delete an entity"""
        entity = self.db.get_entity(entity_id)
        if not entity:
            return False
        
        entity_type = entity['type']
        
        # Delete from database
        success = self.db.delete_entity(entity_id)
        
        if success:
            # Emit deletion event
            await emit_entity_event("deleted", entity_type, entity_id, {})
            logger.info(f"🗑️ Entity deleted: {entity_type}/{entity_id}")
        
        return success
    
    async def get_entity_stats(self) -> Dict[str, Any]:
        """Get entity statistics"""
        stats = self.db.get_stats()
        
        return {
            'total_entities': stats.get('total_entities', 0),
            'entities_by_type': stats.get('entities_by_type', {}),
            'total_links': stats.get('total_links', 0),
            'database_size_bytes': stats.get('database_size_bytes', 0),
            'supported_entity_types': [t.value for t in EntityType],
            'last_updated': datetime.now().isoformat()
        }
    
    def close(self):
        """Close database connection"""
        self.db.close()


# Global memory manager
_memory_manager: Optional[MemoryManager] = None


def get_memory_manager() -> MemoryManager:
    """Get or create memory manager instance"""
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = MemoryManager()
    return _memory_manager


# API Routes

@router.get("/search")
async def search_memories(
    query: Optional[str] = Query(None, description="Search query"),
    type: Optional[EntityType] = Query(None, description="Entity type filter"),
    tags: Optional[str] = Query(None, description="Comma-separated tags"),
    since: Optional[datetime] = Query(None, description="Start date filter"),
    until: Optional[datetime] = Query(None, description="End date filter"),
    limit: int = Query(50, ge=1, le=1000, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Result offset"),
    include_archived: bool = Query(False, description="Include archived entities"),
    device_info: Dict[str, Any] = Depends(require_device_auth("memory.read"))
):
    """Search through stored memories"""
    
    # Parse tags
    tags_list = []
    if tags:
        tags_list = [tag.strip() for tag in tags.split(',') if tag.strip()]
    
    # Create search request
    search_request = MemorySearchRequest(
        query=query,
        type=type,
        tags=tags_list,
        since=since,
        until=until,
        limit=limit,
        offset=offset,
        include_archived=include_archived
    )
    
    memory_manager = get_memory_manager()
    result = await memory_manager.search_entities(search_request)
    
    return {
        'success': True,
        'data': result,
        'message': f"Found {len(result['entities'])} entities"
    }


@router.post("/upsert")
async def upsert_entity(
    request: MemoryUpsertRequest,
    device_info: Dict[str, Any] = Depends(require_device_auth("memory.write"))
):
    """Create or update an entity"""
    
    try:
        memory_manager = get_memory_manager()
        
        entity_id = await memory_manager.upsert_entity(
            entity_type=request.type,
            entity_data=request.entity,
            tags=request.tags,
            sensitive=request.sensitive,
            device_id=device_info.get('device_id')
        )
        
        return {
            'success': True,
            'data': {'entity_id': entity_id},
            'message': f"Entity {request.type.value} saved successfully"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to upsert entity: {e}")
        raise HTTPException(status_code=500, detail="Failed to save entity")


@router.get("/{entity_type}/{entity_id}")
async def get_entity(
    entity_type: EntityType,
    entity_id: str,
    device_info: Dict[str, Any] = Depends(require_device_auth("memory.read"))
):
    """Get a specific entity"""
    
    memory_manager = get_memory_manager()
    entity = await memory_manager.get_entity(entity_id)
    
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    
    # Check entity type matches
    if entity['type'] != entity_type.value:
        raise HTTPException(status_code=400, detail="Entity type mismatch")
    
    return {
        'success': True,
        'data': entity,
        'message': "Entity retrieved successfully"
    }


@router.delete("/{entity_type}/{entity_id}")
async def delete_entity(
    entity_type: EntityType,
    entity_id: str,
    device_info: Dict[str, Any] = Depends(require_device_auth("memory.write"))
):
    """Delete an entity"""
    
    memory_manager = get_memory_manager()
    
    # Verify entity exists and type matches
    entity = await memory_manager.get_entity(entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    
    if entity['type'] != entity_type.value:
        raise HTTPException(status_code=400, detail="Entity type mismatch")
    
    # Delete entity
    success = await memory_manager.delete_entity(entity_id)
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete entity")
    
    return {
        'success': True,
        'message': f"Entity {entity_type.value}/{entity_id} deleted successfully"
    }


@router.get("/stats")
async def get_memory_stats(
    device_info: Dict[str, Any] = Depends(require_device_auth("memory.read"))
):
    """Get memory system statistics"""
    
    memory_manager = get_memory_manager()
    stats = await memory_manager.get_entity_stats()
    
    return {
        'success': True,
        'data': stats,
        'message': "Memory statistics retrieved"
    }


@router.post("/{entity_type}/{entity_id}/archive")
async def archive_entity(
    entity_type: EntityType,
    entity_id: str,
    device_info: Dict[str, Any] = Depends(require_device_auth("memory.write"))
):
    """Archive an entity"""
    
    memory_manager = get_memory_manager()
    
    # Get entity
    entity = await memory_manager.get_entity(entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    
    if entity['type'] != entity_type.value:
        raise HTTPException(status_code=400, detail="Entity type mismatch")
    
    # Update archived status
    success = memory_manager.db.update_entity(entity_id, {'archived': True})
    
    if success:
        await emit_entity_event("archived", entity_type.value, entity_id, {})
        return {
            'success': True,
            'message': f"Entity {entity_type.value}/{entity_id} archived"
        }
    else:
        raise HTTPException(status_code=500, detail="Failed to archive entity")


@router.post("/{entity_type}/{entity_id}/restore")
async def restore_entity(
    entity_type: EntityType,
    entity_id: str,
    device_info: Dict[str, Any] = Depends(require_device_auth("memory.write"))
):
    """Restore an archived entity"""
    
    memory_manager = get_memory_manager()
    
    # Get entity
    entity = await memory_manager.get_entity(entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    
    if entity['type'] != entity_type.value:
        raise HTTPException(status_code=400, detail="Entity type mismatch")
    
    # Update archived status
    success = memory_manager.db.update_entity(entity_id, {'archived': False})
    
    if success:
        await emit_entity_event("restored", entity_type.value, entity_id, {})
        return {
            'success': True,
            'message': f"Entity {entity_type.value}/{entity_id} restored"
        }
    else:
        raise HTTPException(status_code=500, detail="Failed to restore entity")


def register_memory_routes(app):
    """Register memory API routes with FastAPI app"""
    app.include_router(router)