"""
Archie's Main API Application - The gateway to memory archival services
"""
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from pathlib import Path

from archie_core.memory_manager import MemoryManager
from archie_core.storage_manager import ArchieStorageManager
from archie_core.personality import ArchiePersonality
from api.endpoints import storage, system, web, auth, backup

# Get project paths
PROJECT_ROOT = Path(__file__).parent.parent
WEB_DIR = PROJECT_ROOT / "web"
STATIC_DIR = WEB_DIR / "static"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global instances
memory_manager = None
storage_manager = None
archie_personality = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    global memory_manager, storage_manager, archie_personality
    
    # Startup
    logger.info("🧠 ArchieOS: Starting up the memory and storage systems...")
    memory_manager = MemoryManager()
    storage_manager = ArchieStorageManager()
    archie_personality = ArchiePersonality()
    logger.info("✅ ArchieOS: Ready to serve your memory and file storage needs!")
    
    yield
    
    # Shutdown
    logger.info("🏁 ArchieOS: Shutting down gracefully...")
    if memory_manager:
        memory_manager.close()
    if storage_manager:
        storage_manager.close()


# FastAPI app instance
app = FastAPI(
    title="ArchieOS - Intelligent Storage Operating System",
    description="Long-term memory storage, file management, and intelligent archival services with personality",
    version="2.0.0",
    lifespan=lifespan
)

# CORS middleware for Percy integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8080"],  # Percy's ports
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Include routers
app.include_router(auth.router)
app.include_router(storage.router)
app.include_router(system.router)
app.include_router(web.router)
app.include_router(backup.router)

# Root redirect to login page
@app.get("/")
async def root_redirect():
    """Redirect root to login page"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/auth/login", status_code=302)

# Add redirect from /archivist to /web/archivist for convenience
@app.get("/archivist", response_class=HTMLResponse)
async def archivist_redirect():
    """Redirect to the full archivist interface"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/web/archivist", status_code=302)


# Pydantic models
class MemoryEntry(BaseModel):
    content: str = Field(..., description="The memory content to store")
    entry_type: str = Field(..., description="Type of memory entry")
    assistant_id: str = Field(default="percy", description="ID of the assistant")
    plugin_source: Optional[str] = Field(None, description="Source plugin")
    metadata: Optional[dict] = Field(None, description="Additional metadata")
    tags: Optional[List[str]] = Field(None, description="Memory tags")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence score")
    source_method: str = Field(default="ui", description="How the memory was created")


class InteractionEntry(BaseModel):
    user_message: str = Field(..., description="User's message")
    assistant_response: str = Field(..., description="Assistant's response")
    assistant_id: str = Field(default="percy", description="Assistant ID")
    context: Optional[str] = Field(None, description="Additional context")
    session_id: Optional[str] = Field(None, description="Session identifier")
    plugin_used: Optional[str] = Field(None, description="Plugin that handled interaction")
    intent_detected: Optional[str] = Field(None, description="Detected user intent")


class SearchQuery(BaseModel):
    query: Optional[str] = Field(None, description="Text to search for")
    entry_type: Optional[str] = Field(None, description="Filter by entry type")
    assistant_id: Optional[str] = Field(None, description="Filter by assistant")
    tags: Optional[List[str]] = Field(None, description="Filter by tags")
    date_from: Optional[datetime] = Field(None, description="Start date filter")
    date_to: Optional[datetime] = Field(None, description="End date filter")
    limit: int = Field(default=50, ge=1, le=1000, description="Maximum results")
    archived: bool = Field(default=False, description="Include archived memories")


class ArchieResponse(BaseModel):
    """Standard Archie response format with personality"""
    success: bool
    message: str
    data: Optional[dict] = None
    archie_says: Optional[str] = None  # Archie's personality response


def get_memory_manager() -> MemoryManager:
    """Dependency to get memory manager instance"""
    if memory_manager is None:
        raise HTTPException(status_code=500, detail="Memory manager not initialized")
    return memory_manager


def get_personality() -> ArchiePersonality:
    """Dependency to get personality instance"""
    if archie_personality is None:
        raise HTTPException(status_code=500, detail="Archie's personality not initialized")
    return archie_personality


# API Endpoints



@app.get("/health", response_model=ArchieResponse)
async def health_check(
    memory_mgr: MemoryManager = Depends(get_memory_manager),
    personality: ArchiePersonality = Depends(get_personality)
):
    """Health check endpoint with memory stats"""
    try:
        stats = memory_mgr.get_memory_stats()
        archie_comment = personality.format_response("stats_summary", stats)
        
        return ArchieResponse(
            success=True,
            message="All systems operational",
            data=stats,
            archie_says=archie_comment
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return ArchieResponse(
            success=False,
            message="System check failed",
            archie_says=personality.format_response("error")
        )


@app.post("/memory/store", response_model=ArchieResponse)
async def store_memory(
    entry: MemoryEntry,
    memory_mgr: MemoryManager = Depends(get_memory_manager),
    personality: ArchiePersonality = Depends(get_personality)
):
    """Store a new memory entry"""
    try:
        memory_id = memory_mgr.store_memory(
            content=entry.content,
            entry_type=entry.entry_type,
            assistant_id=entry.assistant_id,
            plugin_source=entry.plugin_source,
            metadata=entry.metadata,
            tags=entry.tags,
            confidence=entry.confidence,
            source_method=entry.source_method
        )
        
        archie_comment = personality.format_response("memory_stored", entry.dict())
        archie_comment = personality.add_memory_context(archie_comment, entry.entry_type)
        
        return ArchieResponse(
            success=True,
            message=f"Memory stored with ID {memory_id}",
            data={"memory_id": memory_id},
            archie_says=archie_comment
        )
        
    except Exception as e:
        logger.error(f"Failed to store memory: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/memory/search", response_model=ArchieResponse)
async def search_memories(
    search: SearchQuery,
    memory_mgr: MemoryManager = Depends(get_memory_manager),
    personality: ArchiePersonality = Depends(get_personality)
):
    """Search through stored memories"""
    try:
        results = memory_mgr.search_memories(
            query=search.query,
            entry_type=search.entry_type,
            assistant_id=search.assistant_id,
            tags=search.tags,
            date_from=search.date_from,
            date_to=search.date_to,
            limit=search.limit,
            archived=search.archived
        )
        
        archie_comment = personality.format_response("search_results", results)
        
        return ArchieResponse(
            success=True,
            message=f"Found {len(results)} memories",
            data={"memories": results, "count": len(results)},
            archie_says=archie_comment
        )
        
    except Exception as e:
        logger.error(f"Memory search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/interaction/store", response_model=ArchieResponse)
async def store_interaction(
    interaction: InteractionEntry,
    memory_mgr: MemoryManager = Depends(get_memory_manager),
    personality: ArchiePersonality = Depends(get_personality)
):
    """Store a conversation interaction"""
    try:
        interaction_id = memory_mgr.store_interaction(
            user_message=interaction.user_message,
            assistant_response=interaction.assistant_response,
            assistant_id=interaction.assistant_id,
            context=interaction.context,
            session_id=interaction.session_id,
            plugin_used=interaction.plugin_used,
            intent_detected=interaction.intent_detected
        )
        
        archie_comment = personality.add_memory_context(
            personality.format_response("memory_stored"),
            "interaction"
        )
        
        return ArchieResponse(
            success=True,
            message=f"Interaction stored with ID {interaction_id}",
            data={"interaction_id": interaction_id},
            archie_says=archie_comment
        )
        
    except Exception as e:
        logger.error(f"Failed to store interaction: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats", response_model=ArchieResponse)
async def get_statistics(
    memory_mgr: MemoryManager = Depends(get_memory_manager),
    personality: ArchiePersonality = Depends(get_personality)
):
    """Get detailed memory statistics"""
    try:
        stats = memory_mgr.get_memory_stats()
        archie_comment = personality.format_response("stats_summary", stats)
        
        return ArchieResponse(
            success=True,
            message="Memory statistics retrieved",
            data=stats,
            archie_says=archie_comment
        )
        
    except Exception as e:
        logger.error(f"Failed to get statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/maintenance/archive", response_model=ArchieResponse)
async def archive_old_memories(
    days_old: int = Query(default=90, ge=1, description="Archive memories older than this many days"),
    memory_mgr: MemoryManager = Depends(get_memory_manager),
    personality: ArchiePersonality = Depends(get_personality)
):
    """Archive old memories"""
    try:
        archived_count = memory_mgr.archive_old_memories(days_old)
        
        if archived_count > 0:
            archie_comment = f"Splendid! I've archived {archived_count} old memories. The filing system is now even tidier!"
        else:
            archie_comment = "Nothing needed archiving - the memory vaults are already perfectly organized!"
        
        return ArchieResponse(
            success=True,
            message=f"Archived {archived_count} memories",
            data={"archived_count": archived_count, "days_threshold": days_old},
            archie_says=archie_comment
        )
        
    except Exception as e:
        logger.error(f"Failed to archive memories: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/archie/greeting", response_model=ArchieResponse)
async def get_archie_greeting(
    personality: ArchiePersonality = Depends(get_personality)
):
    """Get a friendly greeting from Archie"""
    greeting = personality.format_response("greeting")
    return ArchieResponse(
        success=True,
        message="Archie says hello",
        archie_says=greeting
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8090, log_level="info")