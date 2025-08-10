"""
ArchieOS WebSocket Server - Real-time event streaming
"""
import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Set, Any, Optional
import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException
from pydantic import BaseModel

from archie_core.events import get_event_bus, Event
from archie_core.auth import require_device_auth

logger = logging.getLogger(__name__)


class WebSocketMessage(BaseModel):
    """WebSocket message structure"""
    type: str  # subscribe, unsubscribe, ping, event
    data: Dict[str, Any]
    id: Optional[str] = None


class WebSocketSubscription(BaseModel):
    """WebSocket subscription request"""
    topics: List[str]


class WebSocketManager:
    """Manages WebSocket connections and subscriptions"""
    
    def __init__(self):
        # Active connections: connection_id -> connection_info
        self._connections: Dict[str, Dict[str, Any]] = {}
        
        # Connection subscriptions: connection_id -> set of topics
        self._subscriptions: Dict[str, Set[str]] = {}
        
        # Event bus integration
        self._event_bus = get_event_bus()
        
        # Statistics
        self._stats = {
            'total_connections': 0,
            'active_connections': 0,
            'messages_sent': 0,
            'messages_received': 0,
            'errors': 0
        }
        
        logger.info("🌐 WebSocket manager initialized")
    
    async def connect(self, websocket: WebSocket, device_info: Dict[str, Any]) -> str:
        """Handle new WebSocket connection"""
        await websocket.accept()
        
        connection_id = str(uuid.uuid4())
        
        connection_info = {
            'websocket': websocket,
            'device_info': device_info,
            'connected_at': datetime.now(),
            'last_activity': datetime.now(),
            'message_count': 0
        }
        
        self._connections[connection_id] = connection_info
        self._subscriptions[connection_id] = set()
        
        self._stats['total_connections'] += 1
        self._stats['active_connections'] = len(self._connections)
        
        logger.info(f"✅ WebSocket connected: {connection_id} (device: {device_info.get('device_name', 'unknown')})")
        
        # Send welcome message
        await self._send_message(connection_id, {
            'type': 'connected',
            'data': {
                'connection_id': connection_id,
                'server_time': datetime.now().isoformat()
            }
        })
        
        return connection_id
    
    async def disconnect(self, connection_id: str):
        """Handle WebSocket disconnection"""
        if connection_id in self._connections:
            connection_info = self._connections[connection_id]
            device_name = connection_info['device_info'].get('device_name', 'unknown')
            
            # Remove from event bus
            self._event_bus.unsubscribe_websocket(connection_id)
            
            # Clean up
            del self._connections[connection_id]
            self._subscriptions.pop(connection_id, None)
            
            self._stats['active_connections'] = len(self._connections)
            
            logger.info(f"❌ WebSocket disconnected: {connection_id} (device: {device_name})")
    
    async def handle_message(self, connection_id: str, message: str):
        """Handle incoming WebSocket message"""
        try:
            # Update activity
            if connection_id in self._connections:
                self._connections[connection_id]['last_activity'] = datetime.now()
                self._connections[connection_id]['message_count'] += 1
            
            self._stats['messages_received'] += 1
            
            # Parse message
            try:
                message_data = json.loads(message)
                ws_message = WebSocketMessage(**message_data)
            except (json.JSONDecodeError, ValueError) as e:
                await self._send_error(connection_id, f"Invalid message format: {e}")
                return
            
            # Handle message by type
            if ws_message.type == 'subscribe':
                await self._handle_subscribe(connection_id, ws_message)
            elif ws_message.type == 'unsubscribe':
                await self._handle_unsubscribe(connection_id, ws_message)
            elif ws_message.type == 'ping':
                await self._handle_ping(connection_id, ws_message)
            elif ws_message.type == 'get_stats':
                await self._handle_get_stats(connection_id, ws_message)
            else:
                await self._send_error(connection_id, f"Unknown message type: {ws_message.type}")
        
        except Exception as e:
            logger.error(f"Error handling WebSocket message: {e}")
            await self._send_error(connection_id, "Internal server error")
            self._stats['errors'] += 1
    
    async def _handle_subscribe(self, connection_id: str, message: WebSocketMessage):
        """Handle subscription request"""
        try:
            topics = message.data.get('topics', [])
            
            if not isinstance(topics, list):
                await self._send_error(connection_id, "Topics must be a list")
                return
            
            # Validate topics
            valid_topic_patterns = [
                'entities.*', 'files.*', 'jobs.*', 'health.*', 'council.*',
                'system.*', 'backup.*', 'alert.*'
            ]
            
            for topic in topics:
                if not any(topic.startswith(pattern.replace('*', '')) or topic == pattern 
                          for pattern in valid_topic_patterns):
                    await self._send_error(connection_id, f"Invalid topic: {topic}")
                    return
            
            # Update subscriptions
            self._subscriptions[connection_id] = set(topics)
            
            # Subscribe to event bus
            websocket = self._connections[connection_id]['websocket']
            self._event_bus.subscribe_websocket(connection_id, websocket, topics)
            
            # Confirm subscription
            await self._send_message(connection_id, {
                'type': 'subscribed',
                'data': {
                    'topics': topics,
                    'message_id': message.id
                }
            })
            
            logger.info(f"📝 WebSocket {connection_id} subscribed to: {', '.join(topics)}")
            
        except Exception as e:
            await self._send_error(connection_id, f"Subscription failed: {e}")
    
    async def _handle_unsubscribe(self, connection_id: str, message: WebSocketMessage):
        """Handle unsubscription request"""
        try:
            topics = message.data.get('topics', [])
            
            if topics:
                # Remove specific topics
                current_topics = self._subscriptions.get(connection_id, set())
                remaining_topics = current_topics - set(topics)
                self._subscriptions[connection_id] = remaining_topics
                
                # Update event bus subscription
                websocket = self._connections[connection_id]['websocket']
                self._event_bus.subscribe_websocket(connection_id, websocket, list(remaining_topics))
            else:
                # Unsubscribe from all topics
                self._subscriptions[connection_id] = set()
                self._event_bus.unsubscribe_websocket(connection_id)
            
            await self._send_message(connection_id, {
                'type': 'unsubscribed',
                'data': {
                    'topics': topics or 'all',
                    'message_id': message.id
                }
            })
            
        except Exception as e:
            await self._send_error(connection_id, f"Unsubscription failed: {e}")
    
    async def _handle_ping(self, connection_id: str, message: WebSocketMessage):
        """Handle ping message"""
        await self._send_message(connection_id, {
            'type': 'pong',
            'data': {
                'timestamp': datetime.now().isoformat(),
                'message_id': message.id
            }
        })
    
    async def _handle_get_stats(self, connection_id: str, message: WebSocketMessage):
        """Handle stats request"""
        stats = self.get_stats()
        await self._send_message(connection_id, {
            'type': 'stats',
            'data': stats
        })
    
    async def _send_message(self, connection_id: str, message: Dict[str, Any]):
        """Send message to a WebSocket connection"""
        if connection_id not in self._connections:
            return False
        
        try:
            websocket = self._connections[connection_id]['websocket']
            await websocket.send_text(json.dumps(message))
            self._stats['messages_sent'] += 1
            return True
            
        except (ConnectionClosed, WebSocketException) as e:
            logger.warning(f"Failed to send message to {connection_id}: {e}")
            await self.disconnect(connection_id)
            return False
        except Exception as e:
            logger.error(f"Error sending WebSocket message: {e}")
            self._stats['errors'] += 1
            return False
    
    async def _send_error(self, connection_id: str, error: str):
        """Send error message to WebSocket"""
        await self._send_message(connection_id, {
            'type': 'error',
            'data': {
                'error': error,
                'timestamp': datetime.now().isoformat()
            }
        })
    
    async def broadcast_event(self, event: Event, topic_filter: Optional[str] = None):
        """Broadcast event to all interested connections"""
        if not self._connections:
            return
        
        # Find interested connections
        interested_connections = []
        for connection_id, topics in self._subscriptions.items():
            for topic in topics:
                if self._topic_matches(event.topic, topic):
                    interested_connections.append(connection_id)
                    break
        
        if not interested_connections:
            return
        
        # Prepare message
        message = {
            'type': 'event',
            'data': event.to_dict()
        }
        
        # Send to all interested connections
        for connection_id in interested_connections:
            await self._send_message(connection_id, message)
    
    def _topic_matches(self, event_topic: str, subscription_topic: str) -> bool:
        """Check if event topic matches subscription topic"""
        if event_topic == subscription_topic:
            return True
        
        if subscription_topic.endswith('*'):
            prefix = subscription_topic[:-1]
            return event_topic.startswith(prefix)
        
        return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get WebSocket manager statistics"""
        # Connection stats by device
        device_stats = {}
        for conn_info in self._connections.values():
            device_name = conn_info['device_info'].get('device_name', 'unknown')
            if device_name not in device_stats:
                device_stats[device_name] = 0
            device_stats[device_name] += 1
        
        # Topic subscription stats
        topic_stats = {}
        for topics in self._subscriptions.values():
            for topic in topics:
                topic_stats[topic] = topic_stats.get(topic, 0) + 1
        
        return {
            **self._stats,
            'connections_by_device': device_stats,
            'subscriptions_by_topic': topic_stats,
            'average_message_count': sum(
                conn['message_count'] for conn in self._connections.values()
            ) / max(len(self._connections), 1)
        }
    
    def get_connections(self) -> List[Dict[str, Any]]:
        """Get info about active connections"""
        connections = []
        for connection_id, conn_info in self._connections.items():
            connections.append({
                'connection_id': connection_id,
                'device_name': conn_info['device_info'].get('device_name'),
                'council_member': conn_info['device_info'].get('council_member'),
                'connected_at': conn_info['connected_at'].isoformat(),
                'last_activity': conn_info['last_activity'].isoformat(),
                'message_count': conn_info['message_count'],
                'subscribed_topics': list(self._subscriptions.get(connection_id, set()))
            })
        
        return connections


# Global WebSocket manager
_websocket_manager: Optional[WebSocketManager] = None


def get_websocket_manager() -> WebSocketManager:
    """Get or create WebSocket manager instance"""
    global _websocket_manager
    if _websocket_manager is None:
        _websocket_manager = WebSocketManager()
    return _websocket_manager


# FastAPI WebSocket endpoint
async def websocket_endpoint(
    websocket: WebSocket,
    device_info: Dict[str, Any] = Depends(require_device_auth())
):
    """WebSocket endpoint for real-time events"""
    manager = get_websocket_manager()
    connection_id = None
    
    try:
        # Connect
        connection_id = await manager.connect(websocket, device_info)
        
        # Message loop
        while True:
            # Receive message
            message = await websocket.receive_text()
            await manager.handle_message(connection_id, message)
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected normally: {connection_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        if connection_id:
            await manager.disconnect(connection_id)


# FastAPI app for WebSocket server
def create_websocket_app() -> FastAPI:
    """Create FastAPI app for WebSocket server"""
    app = FastAPI(title="ArchieOS WebSocket Server")
    
    @app.websocket("/ws")
    async def websocket_route(websocket: WebSocket):
        # Extract device info from query parameters or headers
        # This is simplified - in production you'd want proper auth
        device_name = websocket.query_params.get('device_name', 'unknown')
        
        # Mock device info for now
        device_info = {
            'device_id': 'websocket_device',
            'device_name': device_name,
            'scopes': ['memory.read', 'files.read'],
            'council_member': None
        }
        
        await websocket_endpoint(websocket, device_info)
    
    @app.get("/ws/stats")
    async def get_websocket_stats():
        """Get WebSocket server statistics"""
        manager = get_websocket_manager()
        return manager.get_stats()
    
    @app.get("/ws/connections")
    async def get_websocket_connections():
        """Get active WebSocket connections"""
        manager = get_websocket_manager()
        return {
            'connections': manager.get_connections()
        }
    
    return app


# For standalone WebSocket server
ws_app = create_websocket_app()