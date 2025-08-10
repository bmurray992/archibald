"""
ArchieOS Ingest API - Specialized endpoints for different data types
"""
import json
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from pydantic import BaseModel, Field

from .db import Database
from .memory_api import get_memory_manager
from .models import EntityType, HealthSummary, Transaction, EmailThread, NoteSummary
from .events import emit_entity_event, emit_health_event
from .auth import require_device_auth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ingest", tags=["ingest"])


class HealthSummaryIngest(BaseModel):
    """Health summary data for ingestion"""
    date: datetime
    type: str  # sleep, hr, hrv, workout, nutrition, mood
    aggregates: Dict[str, Any]
    source_device: Optional[str] = None


class EmailThreadIngest(BaseModel):
    """Email thread data for ingestion"""
    subject: str
    participants: List[str]
    message_count: int
    first_message_date: datetime
    last_message_date: datetime
    has_attachments: bool = False
    labels: List[str] = Field(default_factory=list)
    importance: str = "normal"  # high, normal, low


class StatementTransaction(BaseModel):
    """Transaction from financial statement"""
    date: datetime
    description: str
    amount: float
    account: str
    category: Optional[str] = None
    memo: Optional[str] = None


class WebClipIngest(BaseModel):
    """Web page clip data"""
    url: str
    title: str
    content: str
    clipped_at: datetime = Field(default_factory=datetime.now)
    tags: List[str] = Field(default_factory=list)
    summary: Optional[str] = None


class IngestManager:
    """Manages data ingestion from various sources"""
    
    def __init__(self):
        self.db = Database()
        self.db.initialize()
        self.memory_manager = get_memory_manager()
    
    async def ingest_health_data(self, health_data: List[HealthSummaryIngest], device_id: str) -> Dict[str, Any]:
        """Ingest health summary data"""
        ingested_count = 0
        failed_count = 0
        results = []
        
        for health_item in health_data:
            try:
                # Create entity ID based on date and type for deduplication
                entity_id = f"health_{health_item.type}_{health_item.date.strftime('%Y%m%d')}_{device_id}"
                
                # Create health summary entity
                health_entity = {
                    'id': entity_id,
                    'date': health_item.date,
                    'type': health_item.type,
                    'aggregates_json': health_item.aggregates,
                    'source_device': health_item.source_device or device_id,
                    'created': health_item.date,
                    'updated': datetime.now()
                }
                
                # Upsert to database
                await self.memory_manager.upsert_entity(
                    entity_type=EntityType.HEALTH_SUMMARY,
                    entity_data=health_entity,
                    tags=['health', health_item.type, 'automated'],
                    device_id=device_id
                )
                
                results.append({
                    'entity_id': entity_id,
                    'status': 'success',
                    'type': health_item.type,
                    'date': health_item.date.isoformat()
                })
                
                ingested_count += 1
                
            except Exception as e:
                logger.error(f"Failed to ingest health data: {e}")
                results.append({
                    'status': 'failed',
                    'error': str(e),
                    'type': health_item.type,
                    'date': health_item.date.isoformat()
                })
                failed_count += 1
        
        # Emit health event
        await emit_health_event("batch_ingested", {
            'device_id': device_id,
            'ingested_count': ingested_count,
            'failed_count': failed_count,
            'types': list(set(item.type for item in health_data))
        })
        
        return {
            'ingested_count': ingested_count,
            'failed_count': failed_count,
            'total_items': len(health_data),
            'results': results
        }
    
    async def ingest_email_thread(self, email_data: EmailThreadIngest, device_id: str) -> str:
        """Ingest email thread data"""
        
        # Generate entity ID
        entity_id = f"email_{hash(email_data.subject)}_{int(email_data.first_message_date.timestamp())}"
        
        # Create email thread entity
        email_entity = {
            'id': entity_id,
            'subject': email_data.subject,
            'participants': email_data.participants,
            'first_ts': email_data.first_message_date,
            'last_ts': email_data.last_message_date,
            'message_count': email_data.message_count,
            'unread_count': 0,  # Assume read when ingested
            'has_attachments': email_data.has_attachments,
            'labels': email_data.labels,
            'importance': email_data.importance,
            'created': email_data.first_message_date,
            'updated': email_data.last_message_date
        }
        
        # Save to database
        await self.memory_manager.upsert_entity(
            entity_type=EntityType.EMAIL_THREAD,
            entity_data=email_entity,
            tags=['email', 'communication'] + email_data.labels,
            device_id=device_id
        )
        
        logger.info(f"📧 Email thread ingested: {email_data.subject}")
        return entity_id
    
    async def ingest_statement(self, 
                              transactions: List[StatementTransaction], 
                              account: str,
                              statement_period: str,
                              device_id: str) -> Dict[str, Any]:
        """Ingest financial statement transactions"""
        
        ingested_count = 0
        failed_count = 0
        results = []
        
        for txn in transactions:
            try:
                # Generate transaction ID
                entity_id = f"txn_{account}_{int(txn.date.timestamp())}_{hash(txn.description[:50])}"
                
                # Create transaction entity
                txn_entity = {
                    'id': entity_id,
                    'date': txn.date,
                    'amount': txn.amount,
                    'currency': 'USD',  # Default, could be parameterized
                    'account': txn.account or account,
                    'category': txn.category,
                    'memo': txn.memo or txn.description,
                    'merchant': txn.description,
                    'pending': False,
                    'created': txn.date,
                    'updated': datetime.now()
                }
                
                # Save to database
                await self.memory_manager.upsert_entity(
                    entity_type=EntityType.TRANSACTION,
                    entity_data=txn_entity,
                    tags=['finance', 'transaction', account, statement_period],
                    device_id=device_id
                )
                
                results.append({
                    'entity_id': entity_id,
                    'status': 'success',
                    'amount': txn.amount,
                    'date': txn.date.isoformat()
                })
                
                ingested_count += 1
                
            except Exception as e:
                logger.error(f"Failed to ingest transaction: {e}")
                results.append({
                    'status': 'failed',
                    'error': str(e),
                    'amount': txn.amount,
                    'date': txn.date.isoformat()
                })
                failed_count += 1
        
        # Emit finance event
        await emit_entity_event("statement_ingested", EntityType.TRANSACTION.value, account, {
            'device_id': device_id,
            'account': account,
            'statement_period': statement_period,
            'ingested_count': ingested_count,
            'failed_count': failed_count,
            'total_amount': sum(txn.amount for txn in transactions)
        })
        
        return {
            'ingested_count': ingested_count,
            'failed_count': failed_count,
            'total_transactions': len(transactions),
            'account': account,
            'statement_period': statement_period,
            'results': results
        }
    
    async def ingest_web_clip(self, clip_data: WebClipIngest, device_id: str) -> str:
        """Ingest web page clip"""
        
        # Generate entity ID
        entity_id = f"webclip_{hash(clip_data.url)}_{int(clip_data.clipped_at.timestamp())}"
        
        # Create note summary entity for web clip
        note_entity = {
            'id': entity_id,
            'title': clip_data.title,
            'snippet': clip_data.summary or clip_data.content[:500] + "..." if len(clip_data.content) > 500 else clip_data.content,
            'tags': clip_data.tags + ['webclip'],
            'backlinks_count': 0,
            'source_paths': [clip_data.url],
            'word_count': len(clip_data.content.split()),
            'language': 'en',  # Could be detected
            'created': clip_data.clipped_at,
            'updated': clip_data.clipped_at
        }
        
        # Save to database
        await self.memory_manager.upsert_entity(
            entity_type=EntityType.NOTE,
            entity_data=note_entity,
            tags=['webclip', 'research'] + clip_data.tags,
            device_id=device_id
        )
        
        logger.info(f"🌐 Web clip ingested: {clip_data.title}")
        return entity_id


# Global ingest manager
_ingest_manager: Optional[IngestManager] = None


def get_ingest_manager() -> IngestManager:
    """Get or create ingest manager instance"""
    global _ingest_manager
    if _ingest_manager is None:
        _ingest_manager = IngestManager()
    return _ingest_manager


# API Routes

@router.post("/health")
async def ingest_health_data(
    health_data: List[HealthSummaryIngest],
    device_info: Dict[str, Any] = Depends(require_device_auth("ingest.health"))
):
    """Ingest health summary data from devices"""
    
    if not health_data:
        raise HTTPException(status_code=400, detail="No health data provided")
    
    ingest_manager = get_ingest_manager()
    
    try:
        result = await ingest_manager.ingest_health_data(
            health_data, 
            device_info['device_id']
        )
        
        return {
            'success': True,
            'data': result,
            'message': f"Ingested {result['ingested_count']} health items"
        }
        
    except Exception as e:
        logger.error(f"Health data ingestion failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to ingest health data")


@router.post("/email")
async def ingest_email_thread(
    email_data: EmailThreadIngest,
    device_info: Dict[str, Any] = Depends(require_device_auth("ingest.email"))
):
    """Ingest email thread data"""
    
    ingest_manager = get_ingest_manager()
    
    try:
        entity_id = await ingest_manager.ingest_email_thread(
            email_data,
            device_info['device_id']
        )
        
        return {
            'success': True,
            'data': {'entity_id': entity_id},
            'message': "Email thread ingested successfully"
        }
        
    except Exception as e:
        logger.error(f"Email ingestion failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to ingest email thread")


@router.post("/statement")
async def ingest_financial_statement(
    transactions: List[StatementTransaction],
    account: str = Form(...),
    statement_period: str = Form(...),
    device_info: Dict[str, Any] = Depends(require_device_auth("ingest.statement"))
):
    """Ingest financial statement transactions"""
    
    if not transactions:
        raise HTTPException(status_code=400, detail="No transactions provided")
    
    ingest_manager = get_ingest_manager()
    
    try:
        result = await ingest_manager.ingest_statement(
            transactions,
            account,
            statement_period,
            device_info['device_id']
        )
        
        return {
            'success': True,
            'data': result,
            'message': f"Ingested {result['ingested_count']} transactions for {account}"
        }
        
    except Exception as e:
        logger.error(f"Statement ingestion failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to ingest statement")


@router.post("/web-clip")
async def ingest_web_clip(
    clip_data: WebClipIngest,
    device_info: Dict[str, Any] = Depends(require_device_auth("ingest.webclip"))
):
    """Ingest web page clip"""
    
    ingest_manager = get_ingest_manager()
    
    try:
        entity_id = await ingest_manager.ingest_web_clip(
            clip_data,
            device_info['device_id']
        )
        
        return {
            'success': True,
            'data': {'entity_id': entity_id},
            'message': "Web clip ingested successfully"
        }
        
    except Exception as e:
        logger.error(f"Web clip ingestion failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to ingest web clip")


@router.post("/batch")
async def ingest_batch_data(
    data: Dict[str, Any],
    device_info: Dict[str, Any] = Depends(require_device_auth("ingest.health"))  # Requires at least one ingest scope
):
    """Ingest multiple data types in a single request"""
    
    ingest_manager = get_ingest_manager()
    results = {}
    
    # Process health data
    if 'health' in data:
        try:
            health_items = [HealthSummaryIngest(**item) for item in data['health']]
            results['health'] = await ingest_manager.ingest_health_data(
                health_items, 
                device_info['device_id']
            )
        except Exception as e:
            results['health'] = {'error': str(e)}
    
    # Process email threads
    if 'emails' in data:
        results['emails'] = []
        for email_item in data['emails']:
            try:
                email_data = EmailThreadIngest(**email_item)
                entity_id = await ingest_manager.ingest_email_thread(
                    email_data,
                    device_info['device_id']
                )
                results['emails'].append({'entity_id': entity_id, 'status': 'success'})
            except Exception as e:
                results['emails'].append({'error': str(e), 'status': 'failed'})
    
    # Process web clips
    if 'web_clips' in data:
        results['web_clips'] = []
        for clip_item in data['web_clips']:
            try:
                clip_data = WebClipIngest(**clip_item)
                entity_id = await ingest_manager.ingest_web_clip(
                    clip_data,
                    device_info['device_id']
                )
                results['web_clips'].append({'entity_id': entity_id, 'status': 'success'})
            except Exception as e:
                results['web_clips'].append({'error': str(e), 'status': 'failed'})
    
    return {
        'success': True,
        'data': results,
        'message': "Batch ingestion completed"
    }


@router.get("/stats")
async def get_ingest_stats(
    device_info: Dict[str, Any] = Depends(require_device_auth("admin.system"))
):
    """Get ingestion statistics"""
    
    ingest_manager = get_ingest_manager()
    
    # Get stats by entity type and recent activity
    stats = ingest_manager.db.get_stats()
    
    # Recent ingestion activity (last 24 hours)
    recent_cutoff = int((datetime.now().timestamp() - 86400))
    recent_entities = ingest_manager.db.search_entities(
        since=recent_cutoff,
        limit=1000,
        include_archived=False
    )
    
    recent_by_type = {}
    for entity in recent_entities:
        entity_type = entity['type']
        recent_by_type[entity_type] = recent_by_type.get(entity_type, 0) + 1
    
    return {
        'success': True,
        'data': {
            'total_entities': stats.get('total_entities', 0),
            'entities_by_type': stats.get('entities_by_type', {}),
            'recent_24h_by_type': recent_by_type,
            'database_size_bytes': stats.get('database_size_bytes', 0)
        },
        'message': "Ingestion statistics retrieved"
    }


def register_ingest_routes(app):
    """Register ingest API routes with FastAPI app"""
    app.include_router(router)