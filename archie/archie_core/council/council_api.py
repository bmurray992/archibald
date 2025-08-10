"""
Council API - REST endpoints for Council management and meeting protocol
"""
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from .council_manager import get_council_manager
from .meeting_protocol import get_meeting_manager, MeetingStatus
from ..auth import require_device_auth
from ..events import emit_council_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/council", tags=["council"])


# Request/Response Models

class RegisterMemberRequest(BaseModel):
    """Request to register a new Council member"""
    member_id: str = Field(..., description="Unique member identifier")
    name: str = Field(..., description="Display name")
    role: str = Field(..., description="Member role (chairperson, archivist, specialist, envoy)")
    capabilities: List[str] = Field(..., description="List of member capabilities")
    endpoint_url: Optional[str] = Field(None, description="API endpoint for communication")
    public_key: str = Field(default="", description="Public key for secure communication")


class SummonMeetingRequest(BaseModel):
    """Request to summon a Council meeting"""
    topic: str = Field(..., description="Meeting topic/purpose")
    context: Dict[str, Any] = Field(..., description="Context and background information")
    participants: Optional[List[str]] = Field(None, description="Specific participants (default: all members)")
    priority: str = Field(default="normal", description="Meeting priority (low, normal, high, urgent)")


class DeliberationRequest(BaseModel):
    """Request to contribute to a meeting deliberation"""
    contribution: str = Field(..., description="Deliberation contribution")
    supporting_data: Optional[Dict[str, Any]] = Field(None, description="Supporting data or analysis")


class DraftRequest(BaseModel):
    """Request to submit a draft response"""
    draft_response: str = Field(..., description="Draft response content")
    reasoning: Optional[str] = Field(None, description="Reasoning behind the draft")


class SendMessageRequest(BaseModel):
    """Request to send a message to another Council member"""
    to_member: str = Field(..., description="Recipient member ID")
    message_type: str = Field(..., description="Type of message")
    content: Dict[str, Any] = Field(..., description="Message content")
    requires_response: bool = Field(default=False, description="Whether a response is required")


class AssistanceRequest(BaseModel):
    """Request assistance from Council members"""
    topic: str = Field(..., description="Topic needing assistance")
    context: Dict[str, Any] = Field(..., description="Context information")
    required_capabilities: List[str] = Field(..., description="Required member capabilities")
    priority: str = Field(default="normal", description="Request priority")


# API Routes

@router.post("/members/register")
async def register_member(
    request: RegisterMemberRequest,
    device_info: Dict[str, Any] = Depends(require_device_auth("council.admin"))
):
    """Register a new Council member"""
    
    council_manager = get_council_manager()
    
    try:
        result = await council_manager.register_member(
            member_id=request.member_id,
            name=request.name,
            role=request.role,
            capabilities=request.capabilities,
            endpoint_url=request.endpoint_url,
            public_key=request.public_key
        )
        
        return {
            'success': True,
            'data': result,
            'message': f"Council member {request.name} registered successfully"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to register Council member: {e}")
        raise HTTPException(status_code=500, detail="Failed to register member")


@router.get("/members")
async def list_members(
    exclude_inactive: bool = False,
    device_info: Dict[str, Any] = Depends(require_device_auth("council.deliberate"))
):
    """List all Council members"""
    
    council_manager = get_council_manager()
    members = council_manager.list_members(exclude_inactive=exclude_inactive)
    
    return {
        'success': True,
        'data': {
            'members': members,
            'total_count': len(members)
        },
        'message': f"Found {len(members)} Council members"
    }


@router.get("/members/{member_id}")
async def get_member(
    member_id: str,
    device_info: Dict[str, Any] = Depends(require_device_auth("council.deliberate"))
):
    """Get details of a specific Council member"""
    
    council_manager = get_council_manager()
    member = council_manager.get_member(member_id)
    
    if not member:
        raise HTTPException(status_code=404, detail="Council member not found")
    
    return {
        'success': True,
        'data': member,
        'message': f"Member {member_id} details retrieved"
    }


@router.post("/members/{member_id}/status")
async def update_member_status(
    member_id: str,
    status: str,
    device_info: Dict[str, Any] = Depends(require_device_auth("council.admin"))
):
    """Update a member's status"""
    
    council_manager = get_council_manager()
    
    try:
        success = council_manager.update_member_status(member_id, status)
        
        if success:
            return {
                'success': True,
                'message': f"Member {member_id} status updated to {status}"
            }
        else:
            raise HTTPException(status_code=404, detail="Member not found")
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/messages/send")
async def send_message(
    request: SendMessageRequest,
    device_info: Dict[str, Any] = Depends(require_device_auth("council.deliberate"))
):
    """Send a message to another Council member"""
    
    council_manager = get_council_manager()
    
    try:
        message_id = await council_manager.send_message_to_member(
            to_member=request.to_member,
            message_type=request.message_type,
            content=request.content,
            requires_response=request.requires_response
        )
        
        return {
            'success': True,
            'data': {'message_id': message_id},
            'message': f"Message sent to {request.to_member}"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to send Council message: {e}")
        raise HTTPException(status_code=500, detail="Failed to send message")


@router.post("/assistance/request")
async def request_assistance(
    request: AssistanceRequest,
    device_info: Dict[str, Any] = Depends(require_device_auth("council.summon"))
):
    """Request assistance from Council members with specific capabilities"""
    
    council_manager = get_council_manager()
    
    try:
        request_id = await council_manager.request_assistance(
            topic=request.topic,
            context=request.context,
            required_capabilities=request.required_capabilities,
            priority=request.priority
        )
        
        return {
            'success': True,
            'data': {'request_id': request_id},
            'message': f"Assistance requested for: {request.topic}"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to request assistance: {e}")
        raise HTTPException(status_code=500, detail="Failed to request assistance")


@router.get("/stats")
async def get_council_stats(
    device_info: Dict[str, Any] = Depends(require_device_auth("council.deliberate"))
):
    """Get Council statistics"""
    
    council_manager = get_council_manager()
    meeting_manager = get_meeting_manager()
    
    council_stats = council_manager.get_council_stats()
    meeting_stats = meeting_manager.get_meeting_stats()
    
    return {
        'success': True,
        'data': {
            'council': council_stats,
            'meetings': meeting_stats,
            'last_updated': datetime.now().isoformat()
        },
        'message': "Council statistics retrieved"
    }


# Meeting Protocol Routes

@router.post("/meetings/summon")
async def summon_meeting(
    request: SummonMeetingRequest,
    device_info: Dict[str, Any] = Depends(require_device_auth("council.summon"))
):
    """Summon a Council meeting"""
    
    meeting_manager = get_meeting_manager()
    summoner = device_info.get('council_member', device_info['device_name'])
    
    try:
        meeting_id = await meeting_manager.summon_council(
            topic=request.topic,
            summoner=summoner,
            context=request.context,
            participants=request.participants,
            priority=request.priority
        )
        
        return {
            'success': True,
            'data': {'meeting_id': meeting_id},
            'message': f"Council meeting summoned for: {request.topic}"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to summon meeting: {e}")
        raise HTTPException(status_code=500, detail="Failed to summon meeting")


@router.post("/meetings/{meeting_id}/deliberate")
async def contribute_deliberation(
    meeting_id: str,
    request: DeliberationRequest,
    device_info: Dict[str, Any] = Depends(require_device_auth("council.deliberate"))
):
    """Contribute to a meeting deliberation"""
    
    meeting_manager = get_meeting_manager()
    member_id = device_info.get('council_member', device_info['device_name'])
    
    try:
        deliberation_id = await meeting_manager.contribute_deliberation(
            meeting_id=meeting_id,
            member_id=member_id,
            contribution=request.contribution,
            supporting_data=request.supporting_data
        )
        
        return {
            'success': True,
            'data': {'deliberation_id': deliberation_id},
            'message': "Deliberation contributed successfully"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to contribute deliberation: {e}")
        raise HTTPException(status_code=500, detail="Failed to contribute deliberation")


@router.post("/meetings/{meeting_id}/draft/begin")
async def begin_drafting(
    meeting_id: str,
    draft_approach: str = "synthesize",
    device_info: Dict[str, Any] = Depends(require_device_auth("council.draft"))
):
    """Begin the drafting phase of a meeting"""
    
    meeting_manager = get_meeting_manager()
    drafter = device_info.get('council_member', device_info['device_name'])
    
    try:
        success = await meeting_manager.begin_drafting(
            meeting_id=meeting_id,
            drafter=drafter,
            draft_approach=draft_approach
        )
        
        return {
            'success': success,
            'message': f"Drafting phase begun by {drafter}"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to begin drafting: {e}")
        raise HTTPException(status_code=500, detail="Failed to begin drafting")


@router.post("/meetings/{meeting_id}/draft/submit")
async def submit_draft(
    meeting_id: str,
    request: DraftRequest,
    device_info: Dict[str, Any] = Depends(require_device_auth("council.draft"))
):
    """Submit a draft response"""
    
    meeting_manager = get_meeting_manager()
    drafter = device_info.get('council_member', device_info['device_name'])
    
    try:
        success = await meeting_manager.submit_draft(
            meeting_id=meeting_id,
            drafter=drafter,
            draft_response=request.draft_response,
            reasoning=request.reasoning
        )
        
        return {
            'success': success,
            'message': "Draft response submitted successfully"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to submit draft: {e}")
        raise HTTPException(status_code=500, detail="Failed to submit draft")


@router.post("/meetings/{meeting_id}/deliver")
async def deliver_response(
    meeting_id: str,
    final_response: Optional[str] = None,
    device_info: Dict[str, Any] = Depends(require_device_auth("council.deliberate"))
):
    """Deliver the final meeting response"""
    
    meeting_manager = get_meeting_manager()
    deliverer = device_info.get('council_member', device_info['device_name'])
    
    try:
        result = await meeting_manager.deliver_response(
            meeting_id=meeting_id,
            deliverer=deliverer,
            final_response=final_response
        )
        
        return {
            'success': True,
            'data': result,
            'message': "Meeting response delivered successfully"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to deliver response: {e}")
        raise HTTPException(status_code=500, detail="Failed to deliver response")


@router.get("/meetings")
async def list_meetings(
    status: Optional[str] = None,
    member_id: Optional[str] = None,
    limit: int = 50,
    device_info: Dict[str, Any] = Depends(require_device_auth("council.deliberate"))
):
    """List Council meetings"""
    
    meeting_manager = get_meeting_manager()
    
    # If no member_id specified, use current member
    if member_id is None:
        member_id = device_info.get('council_member', device_info['device_name'])
    
    meetings = meeting_manager.list_meetings(
        status=status,
        member_id=member_id,
        limit=limit
    )
    
    return {
        'success': True,
        'data': {
            'meetings': meetings,
            'total_count': len(meetings)
        },
        'message': f"Found {len(meetings)} meetings"
    }


@router.get("/meetings/{meeting_id}")
async def get_meeting(
    meeting_id: str,
    device_info: Dict[str, Any] = Depends(require_device_auth("council.deliberate"))
):
    """Get details of a specific meeting"""
    
    meeting_manager = get_meeting_manager()
    meeting = meeting_manager.get_meeting(meeting_id)
    
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    
    return {
        'success': True,
        'data': meeting,
        'message': f"Meeting {meeting_id} details retrieved"
    }


@router.post("/meetings/{meeting_id}/cancel")
async def cancel_meeting(
    meeting_id: str,
    reason: str,
    device_info: Dict[str, Any] = Depends(require_device_auth("council.summon"))
):
    """Cancel a meeting"""
    
    meeting_manager = get_meeting_manager()
    canceller = device_info.get('council_member', device_info['device_name'])
    
    try:
        success = await meeting_manager.cancel_meeting(
            meeting_id=meeting_id,
            canceller=canceller,
            reason=reason
        )
        
        return {
            'success': success,
            'message': f"Meeting {meeting_id} cancelled"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to cancel meeting: {e}")
        raise HTTPException(status_code=500, detail="Failed to cancel meeting")


@router.post("/messages/receive")
async def receive_message(
    message: Dict[str, Any],
    device_info: Dict[str, Any] = Depends(require_device_auth("council.deliberate"))
):
    """Receive a message from another Council member"""
    
    # This endpoint handles incoming messages from other Council members
    # It would be called by other Council members via HTTP
    
    try:
        message_type = message.get('message_type')
        content = message.get('content', {})
        from_member = message.get('from_member')
        
        # Handle different message types
        if message_type == 'meeting_summons':
            # Handle meeting summons
            await emit_council_event("summons_received", {
                'from_member': from_member,
                'meeting_id': message.get('meeting_id'),
                'topic': content.get('topic')
            })
        
        elif message_type == 'assistance_request':
            # Handle assistance request
            await emit_council_event("assistance_requested", {
                'from_member': from_member,
                'topic': content.get('topic'),
                'required_capabilities': content.get('required_capabilities', [])
            })
        
        # Store the message
        council_manager = get_council_manager()
        council_manager._store_council_message({
            'id': message['id'],
            'from_member': from_member,
            'to_member': 'archie',  # We are Archie
            'meeting_id': message.get('meeting_id'),
            'message_type': message_type,
            'content': content,
            'timestamp': datetime.now(),
            'requires_response': message.get('requires_response', False)
        })
        
        return {
            'success': True,
            'message': f"Message received from {from_member}"
        }
        
    except Exception as e:
        logger.error(f"Failed to receive Council message: {e}")
        raise HTTPException(status_code=500, detail="Failed to process message")


def register_council_routes(app):
    """Register Council API routes with FastAPI app"""
    app.include_router(router)