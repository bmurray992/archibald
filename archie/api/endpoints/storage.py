"""
ArchieOS Storage API Endpoints - File system operations for the mini OS
"""
import os
import tempfile
from datetime import datetime
from typing import List, Optional
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query, Depends, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
import io

from archie_core.storage_manager import ArchieStorageManager
from archie_core.file_manager import ArchieFileManager, FileMetadata as CoreFileMetadata
from archie_core.personality import ArchiePersonality
from api.endpoints.auth import require_auth

router = APIRouter(prefix="/storage", tags=["storage"])

class FileMetadata(BaseModel):
    """File metadata for API responses"""
    id: str
    original_filename: str
    size_bytes: int
    mime_type: Optional[str]
    plugin: Optional[str]
    category: str
    tier: str
    tags: List[str]
    created_at: str
    accessed_at: str
    access_count: int


class FileSearchQuery(BaseModel):
    """File search query parameters"""
    query: Optional[str] = Field(None, description="Text to search for")
    plugin: Optional[str] = Field(None, description="Filter by plugin")
    tags: Optional[List[str]] = Field(None, description="Filter by tags")
    mime_type: Optional[str] = Field(None, description="Filter by MIME type")
    date_from: Optional[datetime] = Field(None, description="Start date filter")
    date_to: Optional[datetime] = Field(None, description="End date filter")
    tier: Optional[str] = Field(None, description="Storage tier filter")
    limit: int = Field(default=50, ge=1, le=1000, description="Maximum results")


class ArchieStorageResponse(BaseModel):
    """Standard ArchieOS storage response"""
    success: bool
    message: str
    data: Optional[dict] = None
    archie_says: Optional[str] = None


def get_file_manager() -> ArchieFileManager:
    """Dependency to get file manager instance"""
    return ArchieFileManager()


def get_storage_manager() -> ArchieStorageManager:
    """Dependency to get storage manager instance"""
    return ArchieStorageManager()


def get_personality() -> ArchiePersonality:
    """Dependency to get personality instance"""
    return ArchiePersonality()


@router.post("/upload", response_model=ArchieStorageResponse)
async def upload_file(
    file: UploadFile = File(...),
    plugin: Optional[str] = Form(None),
    storage_tier: str = Form("uploads"),
    tags: Optional[str] = Form(None),  # Comma-separated tags
    description: Optional[str] = Form(""),
    metadata: Optional[str] = Form(None),  # JSON string
    file_mgr: ArchieFileManager = Depends(get_file_manager),
    personality: ArchiePersonality = Depends(get_personality),
    token_name: str = Depends(require_auth("write"))
):
    """Upload a file to ArchieOS storage with enhanced metadata tracking"""
    try:
        # Parse tags
        tag_list = []
        if tags:
            tag_list = [tag.strip() for tag in tags.split(',') if tag.strip()]
        
        # Parse metadata
        metadata_dict = {}
        if metadata:
            import json
            try:
                metadata_dict = json.loads(metadata)
            except json.JSONDecodeError:
                pass
        
        # Store file using new file manager
        unique_filename, file_metadata = file_mgr.store_file(
            file_content=file.file,
            original_filename=file.filename,
            storage_tier=storage_tier,
            plugin_source=plugin or "",
            tags=tag_list,
            description=description or "",
            metadata=metadata_dict
        )
        
        # Build response data
        file_info = {
            "filename": unique_filename,
            "original_name": file_metadata.original_name,
            "size_bytes": file_metadata.file_size,
            "mime_type": file_metadata.mime_type,
            "plugin_source": file_metadata.plugin_source,
            "storage_tier": file_metadata.storage_tier,
            "tags": file_metadata.tags,
            "description": file_metadata.description,
            "file_hash": file_metadata.file_hash,
            "created_at": file_metadata.created_at.isoformat() if hasattr(file_metadata.created_at, 'isoformat') else str(file_metadata.created_at)
        }
        
        # Archie's response
        archie_comment = personality.format_response("memory_stored", {
            'entry_type': 'file',
            'plugin': plugin or 'general'
        })
        archie_comment = f"{archie_comment} That {file.filename} is now perfectly cataloged in my {storage_tier} archives!"
        
        return ArchieStorageResponse(
            success=True,
            message=f"File uploaded successfully as {unique_filename}",
            data=file_info,
            archie_says=archie_comment
        )
        
    except Exception as e:
        return ArchieStorageResponse(
            success=False,
            message=f"Upload failed: {str(e)}",
            archie_says=personality.format_response("error") 
        )


@router.get("/download/{filename}")
async def download_file(
    filename: str,
    file_mgr: ArchieFileManager = Depends(get_file_manager),
    token_name: str = Depends(require_auth("read"))
):
    """Download a file by filename"""
    try:
        file_metadata = file_mgr.get_file_by_filename(filename)
        if not file_metadata:
            raise HTTPException(status_code=404, detail="File not found")
        
        file_path = Path(file_metadata.file_path)
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found on disk")
        
        return FileResponse(
            path=str(file_path),
            media_type=file_metadata.mime_type,
            filename=file_metadata.original_name
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")


@router.post("/search", response_model=ArchieStorageResponse)
async def search_files(
    search_query: FileSearchQuery,
    file_mgr: ArchieFileManager = Depends(get_file_manager),
    personality: ArchiePersonality = Depends(get_personality),
    token_name: str = Depends(require_auth("read"))
):
    """Search files with advanced filtering"""
    try:
        files = file_mgr.search_files(
            query=search_query.query or "",
            tags=search_query.tags or [],
            plugin_source=search_query.plugin or "",
            storage_tier=search_query.tier or "",
            limit=search_query.limit
        )
        
        # Convert to API format
        file_results = []
        for file_meta in files:
            file_results.append({
                "filename": file_meta.filename,
                "original_name": file_meta.original_name,
                "size_bytes": file_meta.file_size,
                "mime_type": file_meta.mime_type,
                "plugin_source": file_meta.plugin_source,
                "storage_tier": file_meta.storage_tier,
                "tags": file_meta.tags,
                "description": file_meta.description,
                "created_at": file_meta.created_at.isoformat() if hasattr(file_meta.created_at, 'isoformat') else str(file_meta.created_at)
            })
        
        archie_comment = f"I found {len(file_results)} files matching your search criteria. Each one carefully cataloged and ready for retrieval!"
        
        return ArchieStorageResponse(
            success=True,
            message=f"Found {len(file_results)} files",
            data={"files": file_results, "total": len(file_results)},
            archie_says=archie_comment
        )
        
    except Exception as e:
        return ArchieStorageResponse(
            success=False,
            message=f"Search failed: {str(e)}",
            archie_says=personality.format_response("error")
        )


@router.get("/files", response_model=ArchieStorageResponse)
async def list_files(
    plugin: Optional[str] = Query(None),
    storage_tier: Optional[str] = Query(None),
    limit: int = Query(50, le=1000),
    file_mgr: ArchieFileManager = Depends(get_file_manager),
    personality: ArchiePersonality = Depends(get_personality),
    token_name: str = Depends(require_auth("read"))
):
    """List files with optional filtering"""
    try:
        if plugin:
            files = file_mgr.get_files_by_plugin(plugin, limit)
        else:
            files = file_mgr.search_files(
                storage_tier=storage_tier or "",
                limit=limit
            )
        
        # Convert to API format
        file_results = []
        for file_meta in files:
            file_results.append({
                "filename": file_meta.filename,
                "original_name": file_meta.original_name,
                "size_bytes": file_meta.file_size,
                "mime_type": file_meta.mime_type,
                "plugin_source": file_meta.plugin_source,
                "storage_tier": file_meta.storage_tier,
                "tags": file_meta.tags,
                "description": file_meta.description,
                "created_at": file_meta.created_at.isoformat() if hasattr(file_meta.created_at, 'isoformat') else str(file_meta.created_at)
            })
        
        return ArchieStorageResponse(
            success=True,
            message=f"Retrieved {len(file_results)} files",
            data={"files": file_results},
            archie_says=f"Here are {len(file_results)} files from the archives, all perfectly organized!"
        )
        
    except Exception as e:
        return ArchieStorageResponse(
            success=False,
            message=f"Failed to list files: {str(e)}",
            archie_says=personality.format_response("error")
        )


@router.get("/stats", response_model=ArchieStorageResponse)
async def get_storage_stats(
    file_mgr: ArchieFileManager = Depends(get_file_manager),
    personality: ArchiePersonality = Depends(get_personality),
    token_name: str = Depends(require_auth("read"))
):
    """Get storage statistics and usage information"""
    try:
        stats = file_mgr.get_storage_stats()
        
        archie_comment = f"The vaults are running smoothly! I'm managing {stats['database']['total_files']} files across multiple storage tiers."
        
        return ArchieStorageResponse(
            success=True,
            message="Storage statistics retrieved",
            data=stats,
            archie_says=archie_comment
        )
        
    except Exception as e:
        return ArchieStorageResponse(
            success=False,
            message=f"Failed to get storage stats: {str(e)}",
            archie_says=personality.format_response("error")
        )


@router.delete("/files/{filename}", response_model=ArchieStorageResponse)
async def delete_file(
    filename: str,
    file_mgr: ArchieFileManager = Depends(get_file_manager),
    personality: ArchiePersonality = Depends(get_personality),
    token_name: str = Depends(require_auth("delete"))
):
    """Delete a file from storage"""
    try:
        deleted = file_mgr.delete_file(filename)
        
        if not deleted:
            raise HTTPException(status_code=404, detail="File not found")
        
        return ArchieStorageResponse(
            success=True,
            message=f"File {filename} deleted successfully",
            archie_says=f"File {filename} has been securely removed from the archives."
        )
        
    except Exception as e:
        return ArchieStorageResponse(
            success=False,
            message=f"Failed to delete file: {str(e)}",
            archie_says=personality.format_response("error")
        )