"""
Council Meeting Protocol - Formal multi-AI collaboration sessions
Implements the Summon/Deliberate/Draft/Deliver process
"""
import json
import logging
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from enum import Enum

from ..db import Database
from ..models import CouncilMeeting
from ..events import emit_council_event
from .council_manager import get_council_manager

logger = logging.getLogger(__name__)


class MeetingStatus(str, Enum):
    SUMMONED = "summoned"
    DELIBERATING = "deliberating" 
    DRAFTING = "drafting"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class DeliberationEntry:
    """A single deliberation contribution from a Council member"""
    
    def __init__(self, member_id: str, contribution: str, supporting_data: Optional[Dict] = None):
        self.id = str(uuid.uuid4())
        self.member_id = member_id
        self.contribution = contribution
        self.supporting_data = supporting_data or {}
        self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'member_id': self.member_id,
            'contribution': self.contribution,
            'supporting_data': self.supporting_data,
            'timestamp': self.timestamp.isoformat()
        }


class MeetingManager:
    """Manages Council meetings and the formal collaboration protocol"""
    
    def __init__(self):
        self.db = Database()
        self.db.initialize()
        self.council_manager = get_council_manager()
        
        # Meeting timeouts
        self.deliberation_timeout_minutes = 30
        self.drafting_timeout_minutes = 15
        
        logger.info("🏛️ Meeting manager initialized")
    
    async def summon_council(self, 
                            topic: str,
                            summoner: str,
                            context: Dict[str, Any],
                            participants: Optional[List[str]] = None,
                            priority: str = "normal") -> str:
        """Summon a Council meeting (Phase 1: Summon)"""
        
        # Validate summoner
        summoner_member = self.council_manager.get_member(summoner)
        if not summoner_member:
            raise ValueError(f"Unknown Council member: {summoner}")
        
        # Determine participants
        if participants is None:
            # Invite all active members except summoner
            all_members = self.council_manager.list_members(exclude_inactive=True)
            participants = [m['id'] for m in all_members if m['id'] != summoner]
        
        # Validate participants
        for participant in participants:
            if not self.council_manager.get_member(participant):
                raise ValueError(f"Unknown Council member: {participant}")
        
        # Create meeting
        meeting_id = str(uuid.uuid4())
        meeting = CouncilMeeting(
            id=meeting_id,
            summoner=summoner,
            topic=topic,
            participants=participants,
            status=MeetingStatus.SUMMONED,
            created_at=datetime.now(),
            context=context
        )
        
        # Store meeting
        self._store_meeting(meeting)
        
        # Send summons to participants
        summons_content = {
            'meeting_id': meeting_id,
            'topic': topic,
            'summoner': summoner,
            'context': context,
            'priority': priority,
            'deliberation_deadline': (datetime.now() + timedelta(minutes=self.deliberation_timeout_minutes)).isoformat()
        }
        
        for participant in participants:
            try:
                await self.council_manager.send_message_to_member(
                    to_member=participant,
                    message_type="meeting_summons",
                    content=summons_content,
                    meeting_id=meeting_id,
                    requires_response=True
                )
            except Exception as e:
                logger.error(f"Failed to send summons to {participant}: {e}")
        
        # Emit Council event
        await emit_council_event("meeting_summoned", {
            'meeting_id': meeting_id,
            'summoner': summoner,
            'topic': topic,
            'participants': participants,
            'priority': priority
        })
        
        logger.info(f"📢 Council summoned by {summoner} for: {topic}")
        return meeting_id
    
    async def contribute_deliberation(self, 
                                    meeting_id: str,
                                    member_id: str,
                                    contribution: str,
                                    supporting_data: Optional[Dict[str, Any]] = None) -> str:
        """Add a deliberation to a meeting (Phase 2: Deliberate)"""
        
        meeting = self._get_meeting(meeting_id)
        if not meeting:
            raise ValueError(f"Meeting not found: {meeting_id}")
        
        if meeting['status'] not in [MeetingStatus.SUMMONED, MeetingStatus.DELIBERATING]:
            raise ValueError(f"Meeting is not in deliberation phase: {meeting['status']}")
        
        # Verify member is a participant or summoner
        if member_id != meeting['summoner'] and member_id not in meeting['participants']:
            raise ValueError(f"Member {member_id} is not a participant in this meeting")
        
        # Create deliberation entry
        deliberation = DeliberationEntry(member_id, contribution, supporting_data)
        
        # Update meeting with new deliberation
        deliberations = meeting['deliberations'].copy()
        deliberations.append(deliberation.to_dict())
        
        # Update meeting status to deliberating if needed
        new_status = MeetingStatus.DELIBERATING if meeting['status'] == MeetingStatus.SUMMONED else meeting['status']
        
        self._update_meeting(meeting_id, {
            'status': new_status.value,
            'deliberations': deliberations
        })
        
        # Notify other participants
        notification_content = {
            'meeting_id': meeting_id,
            'contributor': member_id,
            'contribution_summary': contribution[:200] + "..." if len(contribution) > 200 else contribution,
            'deliberation_count': len(deliberations)
        }
        
        participants_to_notify = [meeting['summoner']] + meeting['participants']
        participants_to_notify = [p for p in participants_to_notify if p != member_id]
        
        for participant in participants_to_notify:
            try:
                await self.council_manager.send_message_to_member(
                    to_member=participant,
                    message_type="deliberation_update",
                    content=notification_content,
                    meeting_id=meeting_id
                )
            except Exception as e:
                logger.error(f"Failed to notify {participant} of deliberation: {e}")
        
        # Emit event
        await emit_council_event("deliberation_added", {
            'meeting_id': meeting_id,
            'contributor': member_id,
            'deliberation_id': deliberation.id,
            'total_deliberations': len(deliberations)
        })
        
        logger.info(f"💭 Deliberation added to meeting {meeting_id} by {member_id}")
        return deliberation.id
    
    async def begin_drafting(self, 
                           meeting_id: str, 
                           drafter: str,
                           draft_approach: str = "synthesize") -> bool:
        """Begin the drafting phase (Phase 3: Draft)"""
        
        meeting = self._get_meeting(meeting_id)
        if not meeting:
            raise ValueError(f"Meeting not found: {meeting_id}")
        
        if meeting['status'] != MeetingStatus.DELIBERATING:
            raise ValueError(f"Meeting is not ready for drafting: {meeting['status']}")
        
        # Verify drafter is authorized (usually the summoner or a designated member)
        if drafter != meeting['summoner']:
            drafter_member = self.council_manager.get_member(drafter)
            if not drafter_member or 'council.draft' not in drafter_member.get('capabilities', []):
                raise ValueError(f"Member {drafter} is not authorized to draft responses")
        
        # Update meeting status
        self._update_meeting(meeting_id, {
            'status': MeetingStatus.DRAFTING.value,
            'drafter': drafter,
            'drafting_started': datetime.now().isoformat()
        })
        
        # Notify participants that drafting has begun
        drafting_content = {
            'meeting_id': meeting_id,
            'drafter': drafter,
            'approach': draft_approach,
            'deliberations_count': len(meeting['deliberations']),
            'drafting_deadline': (datetime.now() + timedelta(minutes=self.drafting_timeout_minutes)).isoformat()
        }
        
        for participant in meeting['participants']:
            if participant != drafter:
                try:
                    await self.council_manager.send_message_to_member(
                        to_member=participant,
                        message_type="drafting_begun",
                        content=drafting_content,
                        meeting_id=meeting_id
                    )
                except Exception as e:
                    logger.error(f"Failed to notify {participant} of drafting: {e}")
        
        # Emit event
        await emit_council_event("drafting_begun", {
            'meeting_id': meeting_id,
            'drafter': drafter,
            'deliberations_count': len(meeting['deliberations'])
        })
        
        logger.info(f"✏️ Drafting begun for meeting {meeting_id} by {drafter}")
        return True
    
    async def submit_draft(self, 
                          meeting_id: str,
                          drafter: str, 
                          draft_response: str,
                          reasoning: Optional[str] = None) -> bool:
        """Submit a draft response (Phase 3: Draft completion)"""
        
        meeting = self._get_meeting(meeting_id)
        if not meeting:
            raise ValueError(f"Meeting not found: {meeting_id}")
        
        if meeting['status'] != MeetingStatus.DRAFTING:
            raise ValueError(f"Meeting is not in drafting phase: {meeting['status']}")
        
        # Update meeting with draft
        self._update_meeting(meeting_id, {
            'draft_response': draft_response,
            'draft_reasoning': reasoning,
            'draft_submitted': datetime.now().isoformat()
        })
        
        # Notify participants of draft completion
        draft_content = {
            'meeting_id': meeting_id,
            'drafter': drafter,
            'draft_length': len(draft_response),
            'reasoning_provided': bool(reasoning),
            'ready_for_delivery': True
        }
        
        for participant in meeting['participants']:
            if participant != drafter:
                try:
                    await self.council_manager.send_message_to_member(
                        to_member=participant,
                        message_type="draft_completed",
                        content=draft_content,
                        meeting_id=meeting_id
                    )
                except Exception as e:
                    logger.error(f"Failed to notify {participant} of draft completion: {e}")
        
        # Emit event
        await emit_council_event("draft_submitted", {
            'meeting_id': meeting_id,
            'drafter': drafter,
            'draft_length': len(draft_response)
        })
        
        logger.info(f"📄 Draft submitted for meeting {meeting_id} by {drafter}")
        return True
    
    async def deliver_response(self, 
                              meeting_id: str,
                              deliverer: str,
                              final_response: Optional[str] = None) -> Dict[str, Any]:
        """Deliver the final response (Phase 4: Deliver)"""
        
        meeting = self._get_meeting(meeting_id)
        if not meeting:
            raise ValueError(f"Meeting not found: {meeting_id}")
        
        if meeting['status'] != MeetingStatus.DRAFTING:
            raise ValueError(f"Meeting is not ready for delivery: {meeting['status']}")
        
        if not meeting.get('draft_response'):
            raise ValueError("No draft response available for delivery")
        
        # Use draft response if no final response provided
        if final_response is None:
            final_response = meeting['draft_response']
        
        # Complete the meeting
        self._update_meeting(meeting_id, {
            'status': MeetingStatus.COMPLETED.value,
            'final_response': final_response,
            'deliverer': deliverer,
            'completed_at': datetime.now().isoformat()
        })
        
        # Create delivery summary
        delivery_summary = {
            'meeting_id': meeting_id,
            'topic': meeting['topic'],
            'summoner': meeting['summoner'],
            'participants': meeting['participants'],
            'deliberations_count': len(meeting['deliberations']),
            'final_response': final_response,
            'deliverer': deliverer,
            'completed_at': datetime.now().isoformat()
        }
        
        # Notify all participants of completion
        for participant in [meeting['summoner']] + meeting['participants']:
            try:
                await self.council_manager.send_message_to_member(
                    to_member=participant,
                    message_type="meeting_completed",
                    content=delivery_summary,
                    meeting_id=meeting_id
                )
            except Exception as e:
                logger.error(f"Failed to notify {participant} of meeting completion: {e}")
        
        # Emit event
        await emit_council_event("meeting_completed", {
            'meeting_id': meeting_id,
            'topic': meeting['topic'],
            'deliverer': deliverer,
            'participants_count': len(meeting['participants']),
            'deliberations_count': len(meeting['deliberations'])
        })
        
        logger.info(f"🎯 Meeting {meeting_id} completed and response delivered by {deliverer}")
        
        return {
            'meeting_id': meeting_id,
            'final_response': final_response,
            'delivery_summary': delivery_summary
        }
    
    async def cancel_meeting(self, 
                           meeting_id: str, 
                           canceller: str, 
                           reason: str) -> bool:
        """Cancel a meeting"""
        
        meeting = self._get_meeting(meeting_id)
        if not meeting:
            raise ValueError(f"Meeting not found: {meeting_id}")
        
        if meeting['status'] in [MeetingStatus.COMPLETED, MeetingStatus.CANCELLED]:
            raise ValueError(f"Meeting is already {meeting['status']}")
        
        # Only summoner or admin can cancel
        if canceller != meeting['summoner']:
            canceller_member = self.council_manager.get_member(canceller)
            if not canceller_member or 'admin.*' not in canceller_member.get('capabilities', []):
                raise ValueError(f"Member {canceller} is not authorized to cancel meetings")
        
        # Update meeting
        self._update_meeting(meeting_id, {
            'status': MeetingStatus.CANCELLED.value,
            'cancelled_by': canceller,
            'cancellation_reason': reason,
            'cancelled_at': datetime.now().isoformat()
        })
        
        # Notify participants
        cancellation_content = {
            'meeting_id': meeting_id,
            'topic': meeting['topic'],
            'cancelled_by': canceller,
            'reason': reason
        }
        
        for participant in [meeting['summoner']] + meeting['participants']:
            if participant != canceller:
                try:
                    await self.council_manager.send_message_to_member(
                        to_member=participant,
                        message_type="meeting_cancelled",
                        content=cancellation_content,
                        meeting_id=meeting_id
                    )
                except Exception as e:
                    logger.error(f"Failed to notify {participant} of cancellation: {e}")
        
        # Emit event
        await emit_council_event("meeting_cancelled", {
            'meeting_id': meeting_id,
            'cancelled_by': canceller,
            'reason': reason
        })
        
        logger.info(f"❌ Meeting {meeting_id} cancelled by {canceller}: {reason}")
        return True
    
    def get_meeting(self, meeting_id: str) -> Optional[Dict[str, Any]]:
        """Get meeting details"""
        return self._get_meeting(meeting_id)
    
    def list_meetings(self, 
                     status: Optional[str] = None,
                     member_id: Optional[str] = None,
                     limit: int = 50) -> List[Dict[str, Any]]:
        """List meetings with optional filters"""
        query = "SELECT * FROM council_meetings"
        params = []
        conditions = []
        
        if status:
            conditions.append("status = ?")
            params.append(status)
        
        if member_id:
            conditions.append("(summoner = ? OR participants LIKE ?)")
            params.extend([member_id, f'%{member_id}%'])
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        
        cur = self.db.connection.execute(query, params)
        
        meetings = []
        for row in cur:
            meeting = {
                'id': row['id'],
                'summoner': row['summoner'],
                'topic': row['topic'],
                'participants': json.loads(row['participants']),
                'status': row['status'],
                'created_at': row['created_at'],
                'completed_at': row['completed_at'],
                'deliberations_count': len(json.loads(row['deliberations'] or '[]'))
            }
            meetings.append(meeting)
        
        return meetings
    
    def get_meeting_stats(self) -> Dict[str, Any]:
        """Get meeting statistics"""
        # Status counts
        cur = self.db.connection.execute(
            "SELECT status, COUNT(*) as count FROM council_meetings GROUP BY status"
        )
        status_counts = {row['status']: row['count'] for row in cur}
        
        # Recent activity (last 7 days)
        cur = self.db.connection.execute("""
            SELECT COUNT(*) as count FROM council_meetings 
            WHERE created_at > ?
        """, (int((datetime.now() - timedelta(days=7)).timestamp()),))
        
        recent_count = cur.fetchone()['count']
        
        # Average deliberations per meeting
        cur = self.db.connection.execute("""
            SELECT AVG(json_array_length(deliberations)) as avg_deliberations
            FROM council_meetings 
            WHERE status = 'completed' AND deliberations IS NOT NULL
        """)
        
        avg_deliberations_row = cur.fetchone()
        avg_deliberations = avg_deliberations_row['avg_deliberations'] or 0
        
        return {
            'total_meetings': sum(status_counts.values()),
            'status_counts': status_counts,
            'meetings_last_7_days': recent_count,
            'average_deliberations_per_meeting': round(avg_deliberations, 1)
        }
    
    def _get_meeting(self, meeting_id: str) -> Optional[Dict[str, Any]]:
        """Get meeting from database"""
        cur = self.db.connection.execute(
            "SELECT * FROM council_meetings WHERE id = ?",
            (meeting_id,)
        )
        row = cur.fetchone()
        
        if row:
            return {
                'id': row['id'],
                'summoner': row['summoner'],
                'topic': row['topic'],
                'participants': json.loads(row['participants']),
                'status': row['status'],
                'created_at': datetime.fromtimestamp(row['created_at']),
                'completed_at': datetime.fromtimestamp(row['completed_at']) if row['completed_at'] else None,
                'context': json.loads(row['context'] or '{}'),
                'deliberations': json.loads(row['deliberations'] or '[]'),
                'draft_response': row['draft_response'],
                'final_response': row['final_response']
            }
        
        return None
    
    def _store_meeting(self, meeting: CouncilMeeting):
        """Store meeting in database"""
        with self.db.transaction() as conn:
            conn.execute("""
                INSERT INTO council_meetings 
                (id, summoner, topic, participants, status, created_at, completed_at,
                 context, deliberations, draft_response, final_response)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                meeting.id,
                meeting.summoner,
                meeting.topic,
                json.dumps(meeting.participants),
                meeting.status.value,
                int(meeting.created_at.timestamp()),
                int(meeting.completed_at.timestamp()) if meeting.completed_at else None,
                json.dumps(meeting.context),
                json.dumps(meeting.deliberations),
                meeting.draft_response,
                meeting.final_response
            ))
    
    def _update_meeting(self, meeting_id: str, updates: Dict[str, Any]):
        """Update meeting in database"""
        set_clauses = []
        params = []
        
        for key, value in updates.items():
            if key in ['participants', 'context', 'deliberations']:
                set_clauses.append(f"{key} = ?")
                params.append(json.dumps(value))
            else:
                set_clauses.append(f"{key} = ?")
                params.append(value)
        
        params.append(meeting_id)
        
        with self.db.transaction() as conn:
            conn.execute(
                f"UPDATE council_meetings SET {', '.join(set_clauses)} WHERE id = ?",
                params
            )


# Global meeting manager
_meeting_manager: Optional[MeetingManager] = None


def get_meeting_manager() -> MeetingManager:
    """Get or create meeting manager instance"""
    global _meeting_manager
    if _meeting_manager is None:
        _meeting_manager = MeetingManager()
    return _meeting_manager