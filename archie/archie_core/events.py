"""
ArchieOS Event Bus - Pub/Sub system for inter-component communication
"""
import asyncio
import logging
import json
from datetime import datetime
from typing import Dict, List, Any, Callable, Awaitable, Optional, Set
from dataclasses import dataclass
from enum import Enum
import weakref

logger = logging.getLogger(__name__)


class EventPriority(int, Enum):
    """Event priority levels"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class Event:
    """Event data structure"""
    topic: str
    data: Dict[str, Any]
    timestamp: datetime
    priority: EventPriority = EventPriority.NORMAL
    source: Optional[str] = None
    correlation_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for serialization"""
        return {
            'topic': self.topic,
            'data': self.data,
            'timestamp': self.timestamp.isoformat(),
            'priority': self.priority.value,
            'source': self.source,
            'correlation_id': self.correlation_id
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Event':
        """Create event from dictionary"""
        return cls(
            topic=data['topic'],
            data=data['data'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            priority=EventPriority(data.get('priority', EventPriority.NORMAL.value)),
            source=data.get('source'),
            correlation_id=data.get('correlation_id')
        )


class EventBus:
    """Asynchronous event bus with topic-based pub/sub"""
    
    def __init__(self):
        # Subscribers: topic -> list of (callback, subscriber_id)
        self._subscribers: Dict[str, List[tuple]] = {}
        
        # WebSocket connections: connection_id -> websocket
        self._websocket_subscribers: Dict[str, Any] = {}
        
        # WebSocket subscriptions: connection_id -> set of topics
        self._websocket_topics: Dict[str, Set[str]] = {}
        
        # Event queue for async processing
        self._event_queue: asyncio.Queue = asyncio.Queue(maxsize=10000)
        
        # Processing state
        self._processing = False
        self._processor_task = None
        
        # Statistics
        self._stats = {
            'events_published': 0,
            'events_processed': 0,
            'events_dropped': 0,
            'subscribers_count': 0,
            'websocket_connections': 0
        }
        
        logger.info("📡 Event bus initialized")
    
    async def start(self):
        """Start the event processor"""
        if self._processing:
            return
        
        self._processing = True
        self._processor_task = asyncio.create_task(self._process_events())
        logger.info("🚀 Event bus started")
    
    async def stop(self):
        """Stop the event processor"""
        if not self._processing:
            return
        
        self._processing = False
        
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
        
        # Clear all subscribers
        self._subscribers.clear()
        self._websocket_subscribers.clear()
        self._websocket_topics.clear()
        
        logger.info("⏹️ Event bus stopped")
    
    def subscribe(self, 
                 topic: str, 
                 callback: Callable[[Event], Awaitable[None]], 
                 subscriber_id: Optional[str] = None) -> str:
        """Subscribe to events on a topic"""
        if subscriber_id is None:
            subscriber_id = f"sub_{id(callback)}"
        
        if topic not in self._subscribers:
            self._subscribers[topic] = []
        
        # Use weak reference to allow garbage collection
        weak_callback = weakref.WeakMethod(callback) if hasattr(callback, '__self__') else callback
        self._subscribers[topic].append((weak_callback, subscriber_id))
        
        self._stats['subscribers_count'] = sum(len(subs) for subs in self._subscribers.values())
        
        logger.debug(f"📝 Subscribed {subscriber_id} to topic: {topic}")
        return subscriber_id
    
    def unsubscribe(self, topic: str, subscriber_id: str):
        """Unsubscribe from a topic"""
        if topic in self._subscribers:
            self._subscribers[topic] = [
                (cb, sid) for cb, sid in self._subscribers[topic] 
                if sid != subscriber_id
            ]
            
            if not self._subscribers[topic]:
                del self._subscribers[topic]
        
        self._stats['subscribers_count'] = sum(len(subs) for subs in self._subscribers.values())
        logger.debug(f"📝 Unsubscribed {subscriber_id} from topic: {topic}")
    
    def subscribe_websocket(self, 
                           connection_id: str, 
                           websocket: Any, 
                           topics: List[str]):
        """Subscribe a WebSocket connection to topics"""
        self._websocket_subscribers[connection_id] = websocket
        self._websocket_topics[connection_id] = set(topics)
        
        self._stats['websocket_connections'] = len(self._websocket_subscribers)
        
        logger.info(f"🌐 WebSocket {connection_id} subscribed to: {', '.join(topics)}")
    
    def unsubscribe_websocket(self, connection_id: str):
        """Unsubscribe a WebSocket connection"""
        self._websocket_subscribers.pop(connection_id, None)
        self._websocket_topics.pop(connection_id, None)
        
        self._stats['websocket_connections'] = len(self._websocket_subscribers)
        
        logger.info(f"🌐 WebSocket {connection_id} unsubscribed")
    
    async def publish(self, event: Event):
        """Publish an event to the bus"""
        try:
            # Add to processing queue
            await self._event_queue.put(event)
            self._stats['events_published'] += 1
            
            logger.debug(f"📤 Published event: {event.topic}")
            
        except asyncio.QueueFull:
            self._stats['events_dropped'] += 1
            logger.warning(f"Event queue full, dropped event: {event.topic}")
    
    async def publish_event(self, 
                           topic: str, 
                           data: Dict[str, Any],
                           priority: EventPriority = EventPriority.NORMAL,
                           source: Optional[str] = None,
                           correlation_id: Optional[str] = None):
        """Convenience method to publish an event"""
        event = Event(
            topic=topic,
            data=data,
            timestamp=datetime.now(),
            priority=priority,
            source=source,
            correlation_id=correlation_id
        )
        await self.publish(event)
    
    async def _process_events(self):
        """Process events from the queue"""
        while self._processing:
            try:
                # Wait for events with timeout
                try:
                    event = await asyncio.wait_for(self._event_queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue
                
                # Process the event
                await self._dispatch_event(event)
                self._stats['events_processed'] += 1
                
            except Exception as e:
                logger.error(f"Error processing event: {e}")
    
    async def _dispatch_event(self, event: Event):
        """Dispatch event to all subscribers"""
        # Find matching subscribers
        matching_topics = []
        
        # Exact topic match
        if event.topic in self._subscribers:
            matching_topics.append(event.topic)
        
        # Wildcard matching (e.g., "files.*" matches "files.uploaded")
        for topic in self._subscribers:
            if self._topic_matches(event.topic, topic):
                matching_topics.append(topic)
        
        # Dispatch to function subscribers
        for topic in matching_topics:
            for weak_callback, subscriber_id in self._subscribers[topic][:]:  # Copy to avoid modification during iteration
                try:
                    # Resolve weak reference
                    if hasattr(weak_callback, '__call__'):
                        callback = weak_callback
                    else:
                        callback = weak_callback()
                        if callback is None:
                            # Weak reference died, remove subscription
                            self._subscribers[topic] = [
                                (cb, sid) for cb, sid in self._subscribers[topic]
                                if sid != subscriber_id
                            ]
                            continue
                    
                    # Call subscriber
                    asyncio.create_task(self._safe_callback(callback, event, subscriber_id))
                    
                except Exception as e:
                    logger.error(f"Error calling subscriber {subscriber_id}: {e}")
        
        # Dispatch to WebSocket subscribers
        await self._dispatch_to_websockets(event)
    
    async def _dispatch_to_websockets(self, event: Event):
        """Send event to interested WebSocket connections"""
        if not self._websocket_subscribers:
            return
        
        # Find WebSocket connections interested in this event
        interested_connections = []
        for connection_id, topics in self._websocket_topics.items():
            for topic in topics:
                if self._topic_matches(event.topic, topic):
                    interested_connections.append(connection_id)
                    break
        
        if not interested_connections:
            return
        
        # Prepare message
        message = json.dumps(event.to_dict())
        
        # Send to interested connections
        for connection_id in interested_connections:
            websocket = self._websocket_subscribers.get(connection_id)
            if websocket:
                try:
                    await websocket.send_text(message)
                except Exception as e:
                    logger.warning(f"Failed to send event to WebSocket {connection_id}: {e}")
                    # Remove broken connection
                    self.unsubscribe_websocket(connection_id)
    
    async def _safe_callback(self, callback: Callable, event: Event, subscriber_id: str):
        """Safely call a callback with error handling"""
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(event)
            else:
                # Run sync callback in thread pool
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, callback, event)
                
        except Exception as e:
            logger.error(f"Callback error for subscriber {subscriber_id}: {e}")
    
    def _topic_matches(self, event_topic: str, subscription_topic: str) -> bool:
        """Check if event topic matches subscription topic (supports wildcards)"""
        if event_topic == subscription_topic:
            return True
        
        # Simple wildcard matching
        if subscription_topic.endswith('*'):
            prefix = subscription_topic[:-1]
            return event_topic.startswith(prefix)
        
        if subscription_topic.endswith('.*'):
            prefix = subscription_topic[:-2]
            return event_topic.startswith(prefix + '.')
        
        return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get event bus statistics"""
        return {
            **self._stats,
            'queue_size': self._event_queue.qsize(),
            'active_topics': list(self._subscribers.keys()),
            'processing': self._processing
        }
    
    def get_subscribers(self, topic: Optional[str] = None) -> Dict[str, Any]:
        """Get subscriber information"""
        if topic:
            return {
                topic: [sid for _, sid in self._subscribers.get(topic, [])]
            }
        
        return {
            topic: [sid for _, sid in subscribers]
            for topic, subscribers in self._subscribers.items()
        }


# Global event bus instance
_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """Get or create global event bus instance"""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


async def start_event_bus():
    """Start the global event bus"""
    bus = get_event_bus()
    await bus.start()


async def stop_event_bus():
    """Stop the global event bus"""
    bus = get_event_bus()
    await bus.stop()


# Convenience functions for common events
async def emit_entity_event(action: str, entity_type: str, entity_id: str, data: Dict[str, Any]):
    """Emit an entity-related event"""
    bus = get_event_bus()
    await bus.publish_event(
        topic=f"entities.{action}",
        data={
            'entity_type': entity_type,
            'entity_id': entity_id,
            'action': action,
            **data
        },
        source='archie_core'
    )


async def emit_file_event(action: str, file_id: str, data: Dict[str, Any]):
    """Emit a file-related event"""
    bus = get_event_bus()
    await bus.publish_event(
        topic=f"files.{action}",
        data={
            'file_id': file_id,
            'action': action,
            **data
        },
        source='archie_core'
    )


async def emit_job_event(action: str, job_id: str, data: Dict[str, Any]):
    """Emit a job-related event"""
    bus = get_event_bus()
    await bus.publish_event(
        topic=f"jobs.{action}",
        data={
            'job_id': job_id,
            'action': action,
            **data
        },
        source='archie_core'
    )


async def emit_health_event(action: str, data: Dict[str, Any]):
    """Emit a health-related event"""
    bus = get_event_bus()
    await bus.publish_event(
        topic=f"health.{action}",
        data={
            'action': action,
            **data
        },
        source='archie_health'
    )


async def emit_council_event(action: str, data: Dict[str, Any]):
    """Emit a Council-related event"""
    bus = get_event_bus()
    await bus.publish_event(
        topic=f"council.{action}",
        data={
            'action': action,
            **data
        },
        source='archie_council',
        priority=EventPriority.HIGH
    )