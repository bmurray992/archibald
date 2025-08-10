"""
ArchieOS Graph API - Entity relationship management and graph traversal
"""
import logging
import time
from datetime import datetime
from typing import Dict, Any, List, Optional, Set
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel

from .db import Database
from .memory_api import get_memory_manager
from .models import EntityLink
from .events import emit_entity_event
from .auth import require_device_auth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/graph", tags=["graph"])


class CreateLinkRequest(BaseModel):
    """Request to create a link between entities"""
    src: str
    dst: str
    type: str
    metadata: Optional[Dict[str, Any]] = None


class GraphTraversalRequest(BaseModel):
    """Request for graph traversal"""
    center: str  # Starting entity ID
    radius: int = 2  # How many hops to traverse
    link_types: Optional[List[str]] = None  # Filter by link types
    entity_types: Optional[List[str]] = None  # Filter by entity types
    max_results: int = 100


class GraphNeighborhood(BaseModel):
    """Response containing graph neighborhood"""
    center: str
    entities: List[Dict[str, Any]]
    links: List[Dict[str, Any]]
    total_entities: int
    total_links: int


class GraphManager:
    """Manages entity relationships and graph operations"""
    
    def __init__(self):
        self.db = Database()
        self.db.initialize()
        self.memory_manager = get_memory_manager()
    
    async def create_link(self, 
                         src: str, 
                         dst: str, 
                         link_type: str,
                         metadata: Optional[Dict[str, Any]] = None,
                         device_id: Optional[str] = None) -> bool:
        """Create a link between two entities"""
        
        # Verify both entities exist
        src_entity = await self.memory_manager.get_entity(src)
        dst_entity = await self.memory_manager.get_entity(dst)
        
        if not src_entity:
            raise ValueError(f"Source entity not found: {src}")
        if not dst_entity:
            raise ValueError(f"Destination entity not found: {dst}")
        
        # Create the link
        self.db.create_link(src, dst, link_type, metadata)
        
        # Emit event
        await emit_entity_event("linked", "relationship", f"{src}->{dst}", {
            'link_type': link_type,
            'src_type': src_entity['type'],
            'dst_type': dst_entity['type'],
            'device_id': device_id
        })
        
        logger.info(f"🔗 Created link: {src} --{link_type}--> {dst}")
        return True
    
    async def get_entity_links(self, 
                              entity_id: str, 
                              direction: str = "both",
                              link_types: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Get all links for an entity"""
        
        # Get links from database
        links = self.db.get_links(entity_id, direction)
        
        # Filter by link type if specified
        if link_types:
            links = [link for link in links if link['type'] in link_types]
        
        # Enrich links with entity information
        enriched_links = []
        for link in links:
            # Get the connected entity
            connected_id = link['dst'] if link['direction'] == 'outgoing' else link['src']
            connected_entity = await self.memory_manager.get_entity(connected_id)
            
            if connected_entity:
                enriched_link = {
                    **link,
                    'connected_entity': {
                        'id': connected_entity['id'],
                        'type': connected_entity['type'],
                        'summary': self._get_entity_summary(connected_entity)
                    }
                }
                enriched_links.append(enriched_link)
        
        return enriched_links
    
    async def traverse_graph(self, 
                            center: str, 
                            radius: int = 2,
                            link_types: Optional[List[str]] = None,
                            entity_types: Optional[List[str]] = None,
                            max_results: int = 100) -> GraphNeighborhood:
        """Traverse the graph from a center entity"""
        
        # Verify center entity exists
        center_entity = await self.memory_manager.get_entity(center)
        if not center_entity:
            raise ValueError(f"Center entity not found: {center}")
        
        visited_entities = set()
        visited_links = set()
        entities_data = {}
        links_data = []
        
        # Start with center entity
        entities_to_visit = [(center, 0)]  # (entity_id, depth)
        visited_entities.add(center)
        entities_data[center] = center_entity
        
        while entities_to_visit and len(entities_data) < max_results:
            entity_id, depth = entities_to_visit.pop(0)
            
            if depth >= radius:
                continue
            
            # Get links for this entity
            entity_links = self.db.get_links(entity_id, "both")
            
            for link in entity_links:
                link_key = (link['src'], link['dst'], link['type'])
                
                # Skip if already processed this link
                if link_key in visited_links:
                    continue
                
                # Filter by link type
                if link_types and link['type'] not in link_types:
                    continue
                
                visited_links.add(link_key)
                
                # Determine connected entity
                connected_id = link['dst'] if entity_id == link['src'] else link['src']
                
                # Get connected entity
                connected_entity = await self.memory_manager.get_entity(connected_id)
                if not connected_entity:
                    continue
                
                # Filter by entity type
                if entity_types and connected_entity['type'] not in entity_types:
                    continue
                
                # Add connected entity to visit list if not visited
                if connected_id not in visited_entities and len(entities_data) < max_results:
                    visited_entities.add(connected_id)
                    entities_data[connected_id] = connected_entity
                    entities_to_visit.append((connected_id, depth + 1))
                
                # Add link to results
                links_data.append({
                    'src': link['src'],
                    'dst': link['dst'],
                    'type': link['type'],
                    'metadata': link['metadata'],
                    'created': link['created']
                })
        
        # Convert entities to list format with summaries
        entities_list = []
        for entity_id, entity_data in entities_data.items():
            entities_list.append({
                'id': entity_data['id'],
                'type': entity_data['type'],
                'created': entity_data['created'],
                'summary': self._get_entity_summary(entity_data),
                'is_center': entity_id == center
            })
        
        return GraphNeighborhood(
            center=center,
            entities=entities_list,
            links=links_data,
            total_entities=len(entities_list),
            total_links=len(links_data)
        )
    
    async def find_paths(self, 
                        src: str, 
                        dst: str, 
                        max_depth: int = 4) -> List[List[Dict[str, Any]]]:
        """Find paths between two entities"""
        
        # Verify entities exist
        src_entity = await self.memory_manager.get_entity(src)
        dst_entity = await self.memory_manager.get_entity(dst)
        
        if not src_entity:
            raise ValueError(f"Source entity not found: {src}")
        if not dst_entity:
            raise ValueError(f"Destination entity not found: {dst}")
        
        # BFS to find paths
        paths = []
        queue = [([src], set([src]))]  # (path, visited)
        
        while queue and len(paths) < 10:  # Limit to 10 paths
            path, visited = queue.pop(0)
            current = path[-1]
            
            if len(path) > max_depth:
                continue
            
            if current == dst and len(path) > 1:
                # Found a path
                path_data = await self._build_path_data(path)
                paths.append(path_data)
                continue
            
            # Get neighbors
            links = self.db.get_links(current, "both")
            
            for link in links:
                neighbor = link['dst'] if current == link['src'] else link['src']
                
                if neighbor not in visited:
                    new_path = path + [neighbor]
                    new_visited = visited | {neighbor}
                    queue.append((new_path, new_visited))
        
        return paths
    
    async def get_graph_stats(self) -> Dict[str, Any]:
        """Get graph statistics"""
        stats = self.db.get_stats()
        
        # Get link type distribution
        cur = self.db.connection.execute(
            "SELECT type, COUNT(*) as count FROM links GROUP BY type ORDER BY count DESC"
        )
        link_type_stats = {row['type']: row['count'] for row in cur}
        
        # Get highly connected entities (top 10 by link count)
        cur = self.db.connection.execute("""
            SELECT entity_id, link_count, entity_type FROM (
                SELECT src as entity_id, COUNT(*) as link_count FROM links GROUP BY src
                UNION ALL
                SELECT dst as entity_id, COUNT(*) as link_count FROM links GROUP BY dst
            ) 
            JOIN entities ON entities.id = entity_id
            GROUP BY entity_id, entity_type
            ORDER BY SUM(link_count) DESC
            LIMIT 10
        """)
        
        highly_connected = []
        for row in cur:
            entity = await self.memory_manager.get_entity(row['entity_id'])
            if entity:
                highly_connected.append({
                    'entity_id': row['entity_id'],
                    'entity_type': row['entity_type'],
                    'link_count': row['link_count'],
                    'summary': self._get_entity_summary(entity)
                })
        
        return {
            'total_entities': stats.get('total_entities', 0),
            'total_links': stats.get('total_links', 0),
            'link_types': link_type_stats,
            'highly_connected': highly_connected,
            'entities_by_type': stats.get('entities_by_type', {}),
            'last_updated': datetime.now().isoformat()
        }
    
    def _get_entity_summary(self, entity: Dict[str, Any]) -> str:
        """Get a short summary of an entity for display"""
        payload = entity.get('payload', {})
        
        # Try common summary fields
        for field in ['title', 'subject', 'content', 'snippet', 'name', 'display_name']:
            if field in payload and payload[field]:
                text = str(payload[field])
                return text[:100] + "..." if len(text) > 100 else text
        
        return f"{entity.get('type', 'unknown').title()} Entity"
    
    async def _build_path_data(self, path: List[str]) -> List[Dict[str, Any]]:
        """Build detailed data for a path"""
        path_data = []
        
        for i, entity_id in enumerate(path):
            entity = await self.memory_manager.get_entity(entity_id)
            entity_data = {
                'entity_id': entity_id,
                'entity_type': entity['type'] if entity else 'unknown',
                'summary': self._get_entity_summary(entity) if entity else 'Unknown entity'
            }
            
            # Add link information if not the last entity
            if i < len(path) - 1:
                next_entity_id = path[i + 1]
                # Find the link between current and next entity
                links = self.db.get_links(entity_id, "both")
                link_info = None
                
                for link in links:
                    if (link['src'] == entity_id and link['dst'] == next_entity_id) or \
                       (link['src'] == next_entity_id and link['dst'] == entity_id):
                        link_info = {
                            'type': link['type'],
                            'direction': 'outgoing' if link['src'] == entity_id else 'incoming'
                        }
                        break
                
                entity_data['link_to_next'] = link_info
            
            path_data.append(entity_data)
        
        return path_data


# Global graph manager
_graph_manager: Optional[GraphManager] = None


def get_graph_manager() -> GraphManager:
    """Get or create graph manager instance"""
    global _graph_manager
    if _graph_manager is None:
        _graph_manager = GraphManager()
    return _graph_manager


# API Routes

@router.post("/links")
async def create_link(
    request: CreateLinkRequest,
    device_info: Dict[str, Any] = Depends(require_device_auth("memory.write"))
):
    """Create a link between two entities"""
    
    graph_manager = get_graph_manager()
    
    try:
        success = await graph_manager.create_link(
            src=request.src,
            dst=request.dst,
            link_type=request.type,
            metadata=request.metadata,
            device_id=device_info['device_id']
        )
        
        return {
            'success': True,
            'message': f"Link created: {request.src} --{request.type}--> {request.dst}"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create link: {e}")
        raise HTTPException(status_code=500, detail="Failed to create link")


@router.get("/links/{entity_id}")
async def get_entity_links(
    entity_id: str,
    direction: str = Query("both", regex="^(both|incoming|outgoing)$"),
    link_types: Optional[str] = Query(None, description="Comma-separated link types"),
    device_info: Dict[str, Any] = Depends(require_device_auth("memory.read"))
):
    """Get links for an entity"""
    
    graph_manager = get_graph_manager()
    
    # Parse link types
    link_type_list = None
    if link_types:
        link_type_list = [t.strip() for t in link_types.split(',') if t.strip()]
    
    try:
        links = await graph_manager.get_entity_links(
            entity_id=entity_id,
            direction=direction,
            link_types=link_type_list
        )
        
        return {
            'success': True,
            'data': {
                'entity_id': entity_id,
                'links': links,
                'total_links': len(links)
            },
            'message': f"Found {len(links)} links for entity"
        }
        
    except Exception as e:
        logger.error(f"Failed to get entity links: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve links")


@router.get("/traverse")
async def traverse_graph(
    center: str = Query(..., description="Center entity ID"),
    radius: int = Query(2, ge=1, le=5, description="Traversal radius"),
    link_types: Optional[str] = Query(None, description="Comma-separated link types"),
    entity_types: Optional[str] = Query(None, description="Comma-separated entity types"),
    max_results: int = Query(100, ge=1, le=1000, description="Maximum results"),
    device_info: Dict[str, Any] = Depends(require_device_auth("memory.read"))
):
    """Traverse the entity graph from a center point"""
    
    graph_manager = get_graph_manager()
    
    # Parse filters
    link_type_list = None
    if link_types:
        link_type_list = [t.strip() for t in link_types.split(',') if t.strip()]
    
    entity_type_list = None
    if entity_types:
        entity_type_list = [t.strip() for t in entity_types.split(',') if t.strip()]
    
    try:
        neighborhood = await graph_manager.traverse_graph(
            center=center,
            radius=radius,
            link_types=link_type_list,
            entity_types=entity_type_list,
            max_results=max_results
        )
        
        return {
            'success': True,
            'data': neighborhood.dict(),
            'message': f"Found {neighborhood.total_entities} entities and {neighborhood.total_links} links"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Graph traversal failed: {e}")
        raise HTTPException(status_code=500, detail="Graph traversal failed")


@router.get("/paths")
async def find_paths(
    src: str = Query(..., description="Source entity ID"),
    dst: str = Query(..., description="Destination entity ID"),
    max_depth: int = Query(4, ge=1, le=8, description="Maximum path depth"),
    device_info: Dict[str, Any] = Depends(require_device_auth("memory.read"))
):
    """Find paths between two entities"""
    
    graph_manager = get_graph_manager()
    
    try:
        paths = await graph_manager.find_paths(
            src=src,
            dst=dst,
            max_depth=max_depth
        )
        
        return {
            'success': True,
            'data': {
                'src': src,
                'dst': dst,
                'paths': paths,
                'path_count': len(paths)
            },
            'message': f"Found {len(paths)} paths between entities"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Path finding failed: {e}")
        raise HTTPException(status_code=500, detail="Path finding failed")


@router.get("/stats")
async def get_graph_stats(
    device_info: Dict[str, Any] = Depends(require_device_auth("memory.read"))
):
    """Get graph statistics"""
    
    graph_manager = get_graph_manager()
    
    try:
        stats = await graph_manager.get_graph_stats()
        
        return {
            'success': True,
            'data': stats,
            'message': "Graph statistics retrieved"
        }
        
    except Exception as e:
        logger.error(f"Failed to get graph stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve graph statistics")


@router.delete("/links")
async def delete_link(
    src: str = Query(..., description="Source entity ID"),
    dst: str = Query(..., description="Destination entity ID"),
    link_type: str = Query(..., description="Link type"),
    device_info: Dict[str, Any] = Depends(require_device_auth("memory.write"))
):
    """Delete a specific link between entities"""
    
    graph_manager = get_graph_manager()
    
    try:
        # Delete link from database
        with graph_manager.db.transaction() as conn:
            cur = conn.execute(
                "DELETE FROM links WHERE src = ? AND dst = ? AND type = ?",
                (src, dst, link_type)
            )
            
            deleted = cur.rowcount > 0
        
        if deleted:
            await emit_entity_event("unlinked", "relationship", f"{src}->{dst}", {
                'link_type': link_type,
                'device_id': device_info['device_id']
            })
            
            return {
                'success': True,
                'message': f"Link deleted: {src} --{link_type}--> {dst}"
            }
        else:
            raise HTTPException(status_code=404, detail="Link not found")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete link: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete link")


def register_graph_routes(app):
    """Register graph API routes with FastAPI app"""
    app.include_router(router)