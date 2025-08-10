"""
ArchieOS Core Models - Typed entities for unified memory system
"""
from datetime import datetime
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field, validator
from enum import Enum


class EntityType(str, Enum):
    """Supported entity types in the unified memory system"""
    NOTE = "note"
    EVENT = "event"
    EMAIL_THREAD = "email_thread"
    TASK = "task"
    CONTACT = "contact"
    RECIPE = "recipe"
    WORKOUT = "workout"
    HEALTH_SUMMARY = "health_summary"
    TRANSACTION = "transaction"
    MEDIA_ITEM = "media_item"
    
    # Legacy support
    MEMORY_ENTRY = "memory_entry"
    INTERACTION = "interaction"


class TaskStatus(str, Enum):
    """Task completion states"""
    TODO = "todo"
    DOING = "doing"
    DONE = "done"


class MediaKind(str, Enum):
    """Types of media items"""
    BOOK = "book"
    SHOW = "show"
    MOVIE = "movie"
    SONG = "song"
    PODCAST = "podcast"
    ARTICLE = "article"


class HealthType(str, Enum):
    """Health summary types"""
    SLEEP = "sleep"
    HEART_RATE = "hr"
    HRV = "hrv"
    WORKOUT = "workout"
    NUTRITION = "nutrition"
    MOOD = "mood"


# Base Entity Model
class BaseEntity(BaseModel):
    """Base class for all entities"""
    id: str
    created: datetime = Field(default_factory=datetime.now)
    updated: datetime = Field(default_factory=datetime.now)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# Core Entity Types
class NoteSummary(BaseEntity):
    """Summary of a note or document"""
    title: str
    snippet: str
    tags: List[str] = Field(default_factory=list)
    backlinks_count: int = 0
    source_paths: List[str] = Field(default_factory=list)
    
    # Extended fields
    word_count: Optional[int] = None
    key_topics: List[str] = Field(default_factory=list)
    sentiment: Optional[str] = None  # positive, neutral, negative
    language: str = "en"


class Event(BaseEntity):
    """Calendar event or scheduled item"""
    title: str
    start: datetime
    end: datetime
    location: Optional[str] = None
    attendees_hash: Optional[str] = None  # Privacy-preserving hash
    source: str = "calendar"
    
    # Extended fields
    all_day: bool = False
    recurring: bool = False
    rrule: Optional[str] = None
    reminder_minutes: Optional[int] = None
    conference_url: Optional[str] = None
    status: Literal["confirmed", "tentative", "cancelled"] = "confirmed"


class EmailThread(BaseEntity):
    """Email conversation thread"""
    subject: str
    participants: List[str]  # Email addresses
    first_ts: datetime
    last_ts: datetime
    message_count: int
    
    # Extended fields
    unread_count: int = 0
    has_attachments: bool = False
    labels: List[str] = Field(default_factory=list)
    importance: Literal["high", "normal", "low"] = "normal"


class Task(BaseEntity):
    """Actionable task or todo item"""
    title: str
    due: Optional[datetime] = None
    status: TaskStatus = TaskStatus.TODO
    plugin_source: Optional[str] = None
    
    # Extended fields
    description: Optional[str] = None
    priority: Literal["high", "medium", "low"] = "medium"
    project: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    assigned_to: Optional[str] = None
    completed_at: Optional[datetime] = None
    recurring: bool = False
    rrule: Optional[str] = None


class Contact(BaseEntity):
    """Person or organization contact"""
    display_name: str
    emails: List[str] = Field(default_factory=list)
    phones: List[str] = Field(default_factory=list)
    relations: List[str] = Field(default_factory=list)
    
    # Extended fields
    organization: Optional[str] = None
    title: Optional[str] = None
    birthday: Optional[datetime] = None
    address: Optional[str] = None
    notes: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    last_contacted: Optional[datetime] = None


class Recipe(BaseEntity):
    """Cooking recipe or meal"""
    title: str
    yields: str  # e.g., "4 servings", "2 loaves"
    time_total: int  # minutes
    tags: List[str] = Field(default_factory=list)
    macros: Dict[str, float] = Field(default_factory=dict)  # calories, protein, etc.
    
    # Extended fields
    time_prep: Optional[int] = None  # minutes
    time_cook: Optional[int] = None  # minutes
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    ingredients: List[str] = Field(default_factory=list)
    instructions: List[str] = Field(default_factory=list)
    source_url: Optional[str] = None
    rating: Optional[float] = None  # 0-5
    notes: Optional[str] = None


class Workout(BaseEntity):
    """Exercise or workout session"""
    date: datetime
    type: str  # run, bike, swim, strength, yoga, etc.
    duration_m: int  # minutes
    avg_hr: Optional[int] = None  # average heart rate
    distance_km: Optional[float] = None
    source: str = "health"
    
    # Extended fields
    calories: Optional[int] = None
    elevation_m: Optional[float] = None
    pace_min_per_km: Optional[float] = None
    notes: Optional[str] = None
    route: Optional[str] = None
    weather: Optional[str] = None


class HealthSummary(BaseEntity):
    """Daily health metrics summary"""
    date: datetime
    type: HealthType
    aggregates_json: Dict[str, Any]  # Flexible structure for various health data
    source_device: Optional[str] = None
    
    # Common aggregate fields (in aggregates_json):
    # sleep: {total_m, deep_m, rem_m, light_m, awake_m}
    # hr: {resting, avg, max, min}
    # hrv: {rmssd, sdnn}
    # nutrition: {calories, protein_g, carbs_g, fat_g, water_ml}


class Transaction(BaseEntity):
    """Financial transaction"""
    date: datetime
    amount: float
    currency: str = "USD"
    account: str
    category: Optional[str] = None
    memo: Optional[str] = None
    
    # Extended fields
    merchant: Optional[str] = None
    pending: bool = False
    tags: List[str] = Field(default_factory=list)
    receipt_path: Optional[str] = None
    split_amount: Optional[float] = None  # For shared expenses
    reimbursable: bool = False


class MediaItem(BaseEntity):
    """Books, movies, shows, music consumed"""
    kind: MediaKind
    title: str
    creator: str  # author, director, artist
    started: Optional[datetime] = None
    completed: Optional[datetime] = None
    rating: Optional[float] = None  # 0-5
    
    # Extended fields
    year: Optional[int] = None
    genre: List[str] = Field(default_factory=list)
    notes: Optional[str] = None
    source: Optional[str] = None  # netflix, spotify, library, etc.
    isbn: Optional[str] = None  # For books
    imdb_id: Optional[str] = None  # For movies/shows
    duration_minutes: Optional[int] = None
    progress_percent: Optional[float] = None


# Entity wrapper for database storage
class Entity(BaseModel):
    """Database entity wrapper"""
    id: str
    type: EntityType
    payload: Dict[str, Any]  # The actual entity data
    created: int  # Unix timestamp
    updated: int  # Unix timestamp
    
    # Optional metadata
    tags: List[str] = Field(default_factory=list)
    assistant_id: str = "archie"
    sensitive: bool = False  # For encrypted/protected data
    archived: bool = False
    
    @validator('created', 'updated', pre=True)
    def convert_datetime_to_timestamp(cls, v):
        if isinstance(v, datetime):
            return int(v.timestamp())
        return v


# Link between entities
class EntityLink(BaseModel):
    """Relationship between two entities"""
    src: str  # Source entity ID
    dst: str  # Destination entity ID
    type: str  # Link type: references, mentions, parent, child, etc.
    created: int  # Unix timestamp
    metadata: Dict[str, Any] = Field(default_factory=dict)


# Device registration
class Device(BaseModel):
    """Registered device with Council access"""
    id: str
    name: str
    public_key: str
    capabilities: List[str]  # Scopes/permissions
    last_seen: int  # Unix timestamp
    
    # Extended fields
    device_type: Optional[str] = None  # mac, iphone, pi, etc.
    os_version: Optional[str] = None
    app_version: Optional[str] = None
    ip_address: Optional[str] = None
    council_member: Optional[str] = None  # percy, archie, etc.


# Job definition
class Job(BaseModel):
    """Background job definition"""
    id: str
    name: str
    status: Literal["pending", "running", "completed", "failed", "cancelled"]
    last_run: Optional[int] = None  # Unix timestamp
    next_run: Optional[int] = None  # Unix timestamp
    payload: Dict[str, Any] = Field(default_factory=dict)
    retries: int = 0
    
    # Extended fields
    rrule: Optional[str] = None  # Recurrence rule
    max_retries: int = 3
    timeout_seconds: int = 300
    error_message: Optional[str] = None
    result: Optional[Dict[str, Any]] = None


# Request/Response models for APIs
class MemorySearchRequest(BaseModel):
    """Search request for unified memory"""
    query: Optional[str] = None
    type: Optional[EntityType] = None
    since: Optional[datetime] = None
    until: Optional[datetime] = None
    tags: List[str] = Field(default_factory=list)
    limit: int = Field(default=50, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)
    include_archived: bool = False


class MemoryUpsertRequest(BaseModel):
    """Create or update an entity"""
    type: EntityType
    entity: Dict[str, Any]  # The actual entity data matching the type
    tags: List[str] = Field(default_factory=list)
    sensitive: bool = False


class DeviceRegisterRequest(BaseModel):
    """Device registration request"""
    device_name: str
    public_key: str
    scopes: List[str]  # Requested permissions
    device_type: Optional[str] = None
    os_version: Optional[str] = None
    app_version: Optional[str] = None


class DeviceTokenResponse(BaseModel):
    """Device registration response"""
    device_id: str
    token: str
    scopes: List[str]
    expires_at: datetime


# Council-specific models
class CouncilMember(BaseModel):
    """AI assistant member of The Council"""
    id: str
    name: str
    role: str  # executive, archivist, specialist
    capabilities: List[str]
    endpoint_url: Optional[str] = None
    public_key: str
    status: Literal["active", "inactive", "suspended"] = "active"
    joined_at: datetime = Field(default_factory=datetime.now)


class CouncilMeeting(BaseModel):
    """Multi-AI collaboration session"""
    id: str
    summoner: str  # Member who called the meeting
    topic: str
    participants: List[str]  # Member IDs
    status: Literal["summoned", "deliberating", "drafting", "completed", "cancelled"]
    created_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    
    # Meeting content
    context: Dict[str, Any] = Field(default_factory=dict)
    deliberations: List[Dict[str, Any]] = Field(default_factory=list)
    draft_response: Optional[str] = None
    final_response: Optional[str] = None


class CouncilMessage(BaseModel):
    """Inter-AI message within The Council"""
    id: str
    from_member: str
    to_member: Optional[str] = None  # None = broadcast
    meeting_id: Optional[str] = None
    message_type: Literal["request", "response", "notification", "summon"]
    content: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.now)
    requires_response: bool = False


# Aggregation models
class StorageStats(BaseModel):
    """Storage system statistics"""
    total_entities: int
    entities_by_type: Dict[str, int]
    total_files: int
    storage_used_bytes: int
    hot_tier_count: int
    warm_tier_count: int
    cold_tier_count: int
    vault_tier_count: int
    recent_uploads: int
    recent_accesses: int


class HealthStats(BaseModel):
    """System health statistics"""
    uptime_hours: float
    memory_usage_mb: float
    disk_usage_percent: float
    active_jobs: int
    failed_jobs_24h: int
    api_requests_24h: int
    last_backup: Optional[datetime] = None
    last_snapshot: Optional[datetime] = None
    alerts: List[str] = Field(default_factory=list)