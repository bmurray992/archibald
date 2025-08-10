"""
Council Manager - Core Council member management and communication
"""
import json
import logging
import time
import uuid
import httpx
from datetime import datetime
from typing import Dict, Any, List, Optional
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend

from ..db import Database
from ..models import CouncilMember, CouncilMessage
from ..events import emit_council_event, get_event_bus

logger = logging.getLogger(__name__)


class CouncilManager:
    """Manages Council membership and inter-AI communication"""
    
    def __init__(self):
        self.db = Database()
        self.db.initialize()
        
        # Our identity in The Council
        self.our_member_id = "archie"
        self.our_role = "archivist"
        
        # Initialize Archie as a founding member
        self._initialize_archie_member()
        
        logger.info("🏛️ Council manager initialized - Archie ready to serve The Council")
    
    def _initialize_archie_member(self):
        """Initialize Archie as a Council member if not already present"""
        existing = self._get_council_member(self.our_member_id)
        
        if not existing:
            # Create Archie's Council profile
            archie_member = {
                'id': self.our_member_id,
                'name': 'Archibald',
                'role': self.our_role,
                'capabilities': [
                    'memory.longterm',
                    'storage.files',
                    'backup.create',
                    'search.fulltext',
                    'graph.traverse',
                    'council.deliberate'
                ],
                'endpoint_url': None,  # Local member
                'public_key': '',  # Will be generated if needed
                'status': 'active',
                'joined_at': int(time.time())
            }
            
            self._register_council_member(archie_member)
            logger.info("👑 Archie registered as founding Council member")
    
    async def register_member(self, 
                             member_id: str,
                             name: str, 
                             role: str,
                             capabilities: List[str],
                             endpoint_url: Optional[str] = None,
                             public_key: str = "") -> Dict[str, Any]:
        """Register a new Council member"""
        
        # Check if member already exists
        existing = self._get_council_member(member_id)
        if existing:
            raise ValueError(f"Council member {member_id} already exists")
        
        # Validate role
        valid_roles = ["chairperson", "archivist", "specialist", "envoy"]
        if role not in valid_roles:
            raise ValueError(f"Invalid role: {role}. Must be one of: {', '.join(valid_roles)}")
        
        # Create member profile
        member = {
            'id': member_id,
            'name': name,
            'role': role,
            'capabilities': capabilities,
            'endpoint_url': endpoint_url,
            'public_key': public_key,
            'status': 'active',
            'joined_at': int(time.time())
        }
        
        # Store in database
        self._register_council_member(member)
        
        # Emit Council event
        await emit_council_event("member_joined", {
            'member_id': member_id,
            'name': name,
            'role': role,
            'capabilities': capabilities
        })
        
        logger.info(f"🆕 New Council member registered: {name} ({role})")
        
        return {
            'member_id': member_id,
            'status': 'registered',
            'message': f"{name} has joined The Council as {role}"
        }
    
    async def send_message_to_member(self, 
                                    to_member: str,
                                    message_type: str,
                                    content: Dict[str, Any],
                                    meeting_id: Optional[str] = None,
                                    requires_response: bool = False) -> str:
        """Send a message to another Council member"""
        
        # Get recipient member
        recipient = self._get_council_member(to_member)
        if not recipient:
            raise ValueError(f"Council member not found: {to_member}")
        
        # Create message
        message = CouncilMessage(
            id=str(uuid.uuid4()),
            from_member=self.our_member_id,
            to_member=to_member,
            meeting_id=meeting_id,
            message_type=message_type,
            content=content,
            timestamp=datetime.now(),
            requires_response=requires_response
        )
        
        # Store message
        self._store_council_message(message)
        
        # Send to recipient if they have an endpoint
        if recipient['endpoint_url']:
            try:
                await self._deliver_message(recipient['endpoint_url'], message)
                logger.info(f"📨 Message sent to {to_member}: {message_type}")
            except Exception as e:
                logger.error(f"Failed to deliver message to {to_member}: {e}")
        
        # Emit event
        await emit_council_event("message_sent", {
            'message_id': message.id,
            'to_member': to_member,
            'message_type': message_type,
            'requires_response': requires_response
        })
        
        return message.id
    
    async def broadcast_message(self,
                               message_type: str,
                               content: Dict[str, Any],
                               exclude_members: Optional[List[str]] = None) -> List[str]:
        """Broadcast a message to all Council members"""
        
        members = self.list_members(exclude_inactive=True)
        exclude_set = set(exclude_members or [])
        exclude_set.add(self.our_member_id)  # Don't send to ourselves
        
        message_ids = []
        
        for member in members:
            if member['id'] not in exclude_set:
                try:
                    message_id = await self.send_message_to_member(
                        to_member=member['id'],
                        message_type=message_type,
                        content=content,
                        requires_response=False
                    )
                    message_ids.append(message_id)
                except Exception as e:
                    logger.error(f"Failed to broadcast to {member['id']}: {e}")
        
        logger.info(f"📢 Broadcast {message_type} to {len(message_ids)} Council members")
        return message_ids
    
    async def request_assistance(self, 
                                topic: str,
                                context: Dict[str, Any],
                                required_capabilities: List[str],
                                priority: str = "normal") -> str:
        """Request assistance from Council members with specific capabilities"""
        
        # Find members with required capabilities
        suitable_members = []
        for member in self.list_members(exclude_inactive=True):
            if member['id'] == self.our_member_id:
                continue  # Skip ourselves
            
            member_caps = set(member.get('capabilities', []))
            required_caps = set(required_capabilities)
            
            if required_caps.intersection(member_caps):
                suitable_members.append(member)
        
        if not suitable_members:
            raise ValueError(f"No Council members found with capabilities: {', '.join(required_capabilities)}")
        
        # Create assistance request
        request_content = {
            'topic': topic,
            'context': context,
            'required_capabilities': required_capabilities,
            'priority': priority,
            'timestamp': datetime.now().isoformat()
        }
        
        # Send to suitable members
        message_ids = []
        for member in suitable_members:
            try:
                message_id = await self.send_message_to_member(
                    to_member=member['id'],
                    message_type='assistance_request',
                    content=request_content,
                    requires_response=True
                )
                message_ids.append(message_id)
            except Exception as e:
                logger.error(f"Failed to request assistance from {member['id']}: {e}")
        
        logger.info(f"🆘 Assistance requested from {len(message_ids)} Council members for: {topic}")
        
        return f"assistance_{int(time.time())}"  # Request ID
    
    def list_members(self, exclude_inactive: bool = False) -> List[Dict[str, Any]]:
        """List all Council members"""
        query = "SELECT * FROM council_members"
        params = []
        
        if exclude_inactive:
            query += " WHERE status = 'active'"
        
        query += " ORDER BY joined_at"
        
        cur = self.db.connection.execute(query, params)
        
        members = []
        for row in cur:
            members.append({
                'id': row['id'],
                'name': row['name'],
                'role': row['role'],
                'capabilities': json.loads(row['capabilities']),
                'endpoint_url': row['endpoint_url'],
                'status': row['status'],
                'joined_at': row['joined_at'],
                'is_local': row['id'] == self.our_member_id
            })
        
        return members
    
    def get_member(self, member_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific Council member"""
        return self._get_council_member(member_id)
    
    def update_member_status(self, member_id: str, status: str) -> bool:
        """Update a member's status"""
        valid_statuses = ["active", "inactive", "suspended"]
        if status not in valid_statuses:
            raise ValueError(f"Invalid status: {status}")
        
        with self.db.transaction() as conn:
            cur = conn.execute(
                "UPDATE council_members SET status = ? WHERE id = ?",
                (status, member_id)
            )
            return cur.rowcount > 0
    
    def get_council_stats(self) -> Dict[str, Any]:
        """Get Council statistics"""
        members = self.list_members()
        
        stats = {
            'total_members': len(members),
            'active_members': len([m for m in members if m['status'] == 'active']),
            'members_by_role': {},
            'total_capabilities': set()
        }
        
        for member in members:
            role = member['role']
            stats['members_by_role'][role] = stats['members_by_role'].get(role, 0) + 1
            stats['total_capabilities'].update(member['capabilities'])
        
        stats['total_capabilities'] = list(stats['total_capabilities'])
        
        # Message statistics
        cur = self.db.connection.execute(
            "SELECT COUNT(*) as count FROM council_messages WHERE timestamp > datetime('now', '-24 hours')"
        )
        row = cur.fetchone()
        stats['messages_24h'] = row['count'] if row else 0
        
        return stats
    
    def _get_council_member(self, member_id: str) -> Optional[Dict[str, Any]]:
        """Get Council member from database"""
        cur = self.db.connection.execute(
            "SELECT * FROM council_members WHERE id = ?",
            (member_id,)
        )
        row = cur.fetchone()
        
        if row:
            return {
                'id': row['id'],
                'name': row['name'],
                'role': row['role'],
                'capabilities': json.loads(row['capabilities']),
                'endpoint_url': row['endpoint_url'],
                'public_key': row['public_key'],
                'status': row['status'],
                'joined_at': row['joined_at']
            }
        
        return None
    
    def _register_council_member(self, member: Dict[str, Any]):
        """Store Council member in database"""
        with self.db.transaction() as conn:
            conn.execute("""
                INSERT INTO council_members 
                (id, name, role, capabilities, endpoint_url, public_key, status, joined_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                member['id'],
                member['name'],
                member['role'],
                json.dumps(member['capabilities']),
                member['endpoint_url'],
                member['public_key'],
                member['status'],
                member['joined_at']
            ))
    
    def _store_council_message(self, message: CouncilMessage):
        """Store Council message in database"""
        with self.db.transaction() as conn:
            conn.execute("""
                INSERT INTO council_messages
                (id, from_member, to_member, meeting_id, message_type, content, 
                 timestamp, requires_response)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                message.id,
                message.from_member,
                message.to_member,
                message.meeting_id,
                message.message_type,
                json.dumps(message.content),
                int(message.timestamp.timestamp()),
                message.requires_response
            ))
    
    async def _deliver_message(self, endpoint_url: str, message: CouncilMessage):
        """Deliver message to another Council member"""
        async with httpx.AsyncClient() as client:
            payload = {
                'id': message.id,
                'from_member': message.from_member,
                'message_type': message.message_type,
                'content': message.content,
                'timestamp': message.timestamp.isoformat(),
                'requires_response': message.requires_response
            }
            
            if message.meeting_id:
                payload['meeting_id'] = message.meeting_id
            
            response = await client.post(
                f"{endpoint_url}/api/council/messages",
                json=payload,
                timeout=30.0
            )
            
            if response.status_code != 200:
                raise Exception(f"Message delivery failed: {response.status_code}")
    
    def close(self):
        """Close database connection"""
        self.db.close()


# Global Council manager
_council_manager: Optional[CouncilManager] = None


def get_council_manager() -> CouncilManager:
    """Get or create Council manager instance"""
    global _council_manager
    if _council_manager is None:
        _council_manager = CouncilManager()
    return _council_manager