"""
Comprehensive tests for archie_core.models module - Pydantic models validation
"""
import pytest
from datetime import datetime, timedelta
from typing import Dict, Any
import json

from archie_core.models import (
    # Enums
    EntityType, TaskStatus, MediaKind, HealthType,
    
    # Base models
    BaseEntity, Entity, EntityLink,
    
    # Core entity types
    NoteSummary, Event, EmailThread, Task, Contact, Recipe,
    Workout, HealthSummary, Transaction, MediaItem,
    
    # System models
    Device, Job,
    
    # Request/Response models
    MemorySearchRequest, MemoryUpsertRequest,
    DeviceRegisterRequest, DeviceTokenResponse,
    
    # Council models
    CouncilMember, CouncilMeeting, CouncilMessage,
    
    # Stats models
    StorageStats, HealthStats
)


class TestEnums:
    """Test enum values and validation"""
    
    def test_entity_type_values(self):
        """Test EntityType enum values"""
        # Core entity types
        assert EntityType.NOTE == "note"
        assert EntityType.EVENT == "event"
        assert EntityType.EMAIL_THREAD == "email_thread"
        assert EntityType.TASK == "task"
        assert EntityType.CONTACT == "contact"
        assert EntityType.RECIPE == "recipe"
        assert EntityType.WORKOUT == "workout"
        assert EntityType.HEALTH_SUMMARY == "health_summary"
        assert EntityType.TRANSACTION == "transaction"
        assert EntityType.MEDIA_ITEM == "media_item"
        
        # Legacy types
        assert EntityType.MEMORY_ENTRY == "memory_entry"
        assert EntityType.INTERACTION == "interaction"
    
    def test_task_status_values(self):
        """Test TaskStatus enum values"""
        assert TaskStatus.TODO == "todo"
        assert TaskStatus.DOING == "doing"
        assert TaskStatus.DONE == "done"
    
    def test_media_kind_values(self):
        """Test MediaKind enum values"""
        assert MediaKind.BOOK == "book"
        assert MediaKind.SHOW == "show"
        assert MediaKind.MOVIE == "movie"
        assert MediaKind.SONG == "song"
        assert MediaKind.PODCAST == "podcast"
        assert MediaKind.ARTICLE == "article"
    
    def test_health_type_values(self):
        """Test HealthType enum values"""
        assert HealthType.SLEEP == "sleep"
        assert HealthType.HEART_RATE == "hr"
        assert HealthType.HRV == "hrv"
        assert HealthType.WORKOUT == "workout"
        assert HealthType.NUTRITION == "nutrition"
        assert HealthType.MOOD == "mood"


class TestBaseEntity:
    """Test BaseEntity model and datetime handling"""
    
    def test_base_entity_creation(self):
        """Test BaseEntity with minimal data"""
        entity = BaseEntity(id="test_base_entity")
        
        assert entity.id == "test_base_entity"
        assert isinstance(entity.created, datetime)
        assert isinstance(entity.updated, datetime)
    
    def test_base_entity_with_timestamps(self):
        """Test BaseEntity with explicit timestamps"""
        created_time = datetime(2024, 1, 1, 12, 0, 0)
        updated_time = datetime(2024, 1, 2, 12, 0, 0)
        
        entity = BaseEntity(
            id="timestamped_entity",
            created=created_time,
            updated=updated_time
        )
        
        assert entity.created == created_time
        assert entity.updated == updated_time
    
    def test_json_serialization(self):
        """Test datetime JSON serialization"""
        entity = BaseEntity(id="json_test")
        
        # Should serialize to JSON without errors
        json_data = entity.json()
        assert '"created":' in json_data
        assert '"updated":' in json_data
        
        # Timestamps should be ISO format
        data = json.loads(json_data)
        assert 'T' in data['created']  # ISO format indicator


class TestNoteSummary:
    """Test NoteSummary model"""
    
    @pytest.fixture
    def sample_note_data(self):
        return {
            'id': 'note_123',
            'title': 'Test Note',
            'snippet': 'This is a test note snippet',
            'tags': ['test', 'sample'],
            'source_paths': ['/path/to/document.txt'],
            'word_count': 150,
            'key_topics': ['testing', 'documentation'],
            'sentiment': 'positive',
            'language': 'en'
        }
    
    def test_note_summary_creation(self, sample_note_data):
        """Test NoteSummary with full data"""
        note = NoteSummary(**sample_note_data)
        
        assert note.id == sample_note_data['id']
        assert note.title == sample_note_data['title']
        assert note.snippet == sample_note_data['snippet']
        assert note.tags == sample_note_data['tags']
        assert note.word_count == sample_note_data['word_count']
        assert note.backlinks_count == 0  # Default value
    
    def test_note_summary_minimal(self):
        """Test NoteSummary with minimal required fields"""
        note = NoteSummary(
            id="minimal_note",
            title="Minimal Note",
            snippet="Minimal snippet"
        )
        
        assert note.tags == []  # Default empty list
        assert note.source_paths == []  # Default empty list
        assert note.key_topics == []  # Default empty list
        assert note.backlinks_count == 0
        assert note.language == "en"  # Default value
        assert note.word_count is None
        assert note.sentiment is None
    
    def test_note_summary_validation(self):
        """Test NoteSummary field validation"""
        # Test missing required fields
        with pytest.raises(ValueError):
            NoteSummary(id="test")  # Missing title and snippet


class TestEvent:
    """Test Event model"""
    
    @pytest.fixture
    def sample_event_data(self):
        start_time = datetime(2024, 6, 15, 10, 0, 0)
        end_time = datetime(2024, 6, 15, 11, 30, 0)
        
        return {
            'id': 'event_123',
            'title': 'Team Meeting',
            'start': start_time,
            'end': end_time,
            'location': 'Conference Room A',
            'attendees_hash': 'hash123',
            'source': 'google_calendar',
            'all_day': False,
            'recurring': True,
            'rrule': 'FREQ=WEEKLY;BYDAY=MO',
            'reminder_minutes': 15,
            'conference_url': 'https://meet.google.com/abc-def-ghi',
            'status': 'confirmed'
        }
    
    def test_event_creation(self, sample_event_data):
        """Test Event with full data"""
        event = Event(**sample_event_data)
        
        assert event.title == sample_event_data['title']
        assert event.start == sample_event_data['start']
        assert event.end == sample_event_data['end']
        assert event.location == sample_event_data['location']
        assert event.recurring == sample_event_data['recurring']
        assert event.status == sample_event_data['status']
    
    def test_event_minimal(self):
        """Test Event with minimal fields"""
        start_time = datetime.now()
        end_time = start_time + timedelta(hours=1)
        
        event = Event(
            id="minimal_event",
            title="Minimal Event",
            start=start_time,
            end=end_time
        )
        
        assert event.location is None
        assert event.all_day is False  # Default
        assert event.recurring is False  # Default
        assert event.status == "confirmed"  # Default
        assert event.source == "calendar"  # Default
    
    def test_event_status_validation(self):
        """Test Event status field validation"""
        start_time = datetime.now()
        end_time = start_time + timedelta(hours=1)
        
        # Valid status
        event = Event(
            id="status_test",
            title="Status Test",
            start=start_time,
            end=end_time,
            status="tentative"
        )
        assert event.status == "tentative"
        
        # Invalid status should raise error
        with pytest.raises(ValueError):
            Event(
                id="bad_status",
                title="Bad Status",
                start=start_time,
                end=end_time,
                status="invalid_status"
            )


class TestEmailThread:
    """Test EmailThread model"""
    
    def test_email_thread_creation(self):
        """Test EmailThread with full data"""
        first_time = datetime(2024, 6, 1, 9, 0, 0)
        last_time = datetime(2024, 6, 5, 17, 30, 0)
        
        thread = EmailThread(
            id="thread_123",
            subject="Project Discussion",
            participants=["alice@example.com", "bob@example.com"],
            first_ts=first_time,
            last_ts=last_time,
            message_count=5,
            unread_count=2,
            has_attachments=True,
            labels=["important", "project"],
            importance="high"
        )
        
        assert thread.subject == "Project Discussion"
        assert len(thread.participants) == 2
        assert thread.message_count == 5
        assert thread.unread_count == 2
        assert thread.importance == "high"
    
    def test_email_thread_minimal(self):
        """Test EmailThread with minimal fields"""
        first_time = datetime.now()
        last_time = first_time + timedelta(days=1)
        
        thread = EmailThread(
            id="minimal_thread",
            subject="Minimal Thread",
            participants=["user@example.com"],
            first_ts=first_time,
            last_ts=last_time,
            message_count=1
        )
        
        assert thread.unread_count == 0  # Default
        assert thread.has_attachments is False  # Default
        assert thread.labels == []  # Default
        assert thread.importance == "normal"  # Default


class TestTask:
    """Test Task model"""
    
    def test_task_creation(self):
        """Test Task with full data"""
        due_date = datetime(2024, 6, 30, 23, 59, 0)
        completed_date = datetime(2024, 6, 25, 14, 30, 0)
        
        task = Task(
            id="task_123",
            title="Complete project documentation",
            due=due_date,
            status=TaskStatus.DONE,
            plugin_source="todoist",
            description="Write comprehensive documentation for the project",
            priority="high",
            project="Project Alpha",
            tags=["documentation", "high-priority"],
            assigned_to="alice@example.com",
            completed_at=completed_date,
            recurring=True,
            rrule="FREQ=MONTHLY"
        )
        
        assert task.title == "Complete project documentation"
        assert task.status == TaskStatus.DONE
        assert task.priority == "high"
        assert task.recurring is True
        assert task.completed_at == completed_date
    
    def test_task_minimal(self):
        """Test Task with minimal fields"""
        task = Task(
            id="minimal_task",
            title="Simple task"
        )
        
        assert task.due is None
        assert task.status == TaskStatus.TODO  # Default
        assert task.priority == "medium"  # Default
        assert task.recurring is False  # Default
        assert task.tags == []  # Default
    
    def test_task_status_validation(self):
        """Test Task status validation"""
        task = Task(id="status_test", title="Status Test", status="doing")
        assert task.status == TaskStatus.DOING
        
        # Invalid status should raise error
        with pytest.raises(ValueError):
            Task(id="bad_task", title="Bad Task", status="invalid_status")
    
    def test_task_priority_validation(self):
        """Test Task priority validation"""
        # Valid priorities
        for priority in ["high", "medium", "low"]:
            task = Task(id=f"task_{priority}", title="Test", priority=priority)
            assert task.priority == priority
        
        # Invalid priority should raise error
        with pytest.raises(ValueError):
            Task(id="bad_priority", title="Bad Priority", priority="urgent")


class TestContact:
    """Test Contact model"""
    
    def test_contact_creation(self):
        """Test Contact with full data"""
        birthday = datetime(1990, 5, 15)
        last_contact = datetime(2024, 6, 1)
        
        contact = Contact(
            id="contact_123",
            display_name="John Doe",
            emails=["john@example.com", "johndoe@gmail.com"],
            phones=["+1234567890", "+0987654321"],
            relations=["colleague", "friend"],
            organization="Acme Corp",
            title="Software Engineer",
            birthday=birthday,
            address="123 Main St, City, State 12345",
            notes="Met at conference 2023",
            tags=["colleague", "tech"],
            last_contacted=last_contact
        )
        
        assert contact.display_name == "John Doe"
        assert len(contact.emails) == 2
        assert len(contact.phones) == 2
        assert contact.organization == "Acme Corp"
        assert contact.birthday == birthday
    
    def test_contact_minimal(self):
        """Test Contact with minimal fields"""
        contact = Contact(
            id="minimal_contact",
            display_name="Jane Smith"
        )
        
        assert contact.emails == []  # Default
        assert contact.phones == []  # Default
        assert contact.relations == []  # Default
        assert contact.tags == []  # Default
        assert contact.organization is None
        assert contact.last_contacted is None


class TestRecipe:
    """Test Recipe model"""
    
    def test_recipe_creation(self):
        """Test Recipe with full data"""
        recipe = Recipe(
            id="recipe_123",
            title="Chocolate Chip Cookies",
            yields="24 cookies",
            time_total=90,
            tags=["dessert", "baking", "cookies"],
            macros={"calories": 150, "protein": 2.5, "carbs": 20, "fat": 7},
            time_prep=30,
            time_cook=12,
            difficulty="easy",
            ingredients=[
                "2 cups flour",
                "1 cup butter",
                "1/2 cup sugar",
                "1 cup chocolate chips"
            ],
            instructions=[
                "Preheat oven to 350°F",
                "Mix dry ingredients",
                "Cream butter and sugar",
                "Combine all ingredients",
                "Bake for 10-12 minutes"
            ],
            source_url="https://example.com/recipe/123",
            rating=4.5,
            notes="Family favorite recipe"
        )
        
        assert recipe.title == "Chocolate Chip Cookies"
        assert recipe.time_total == 90
        assert recipe.difficulty == "easy"
        assert len(recipe.ingredients) == 4
        assert len(recipe.instructions) == 5
        assert recipe.rating == 4.5
    
    def test_recipe_minimal(self):
        """Test Recipe with minimal fields"""
        recipe = Recipe(
            id="minimal_recipe",
            title="Simple Recipe",
            yields="2 servings",
            time_total=30
        )
        
        assert recipe.tags == []  # Default
        assert recipe.macros == {}  # Default
        assert recipe.ingredients == []  # Default
        assert recipe.instructions == []  # Default
        assert recipe.difficulty == "medium"  # Default
        assert recipe.rating is None
    
    def test_recipe_difficulty_validation(self):
        """Test Recipe difficulty validation"""
        for difficulty in ["easy", "medium", "hard"]:
            recipe = Recipe(
                id=f"recipe_{difficulty}",
                title="Test Recipe",
                yields="1 serving",
                time_total=30,
                difficulty=difficulty
            )
            assert recipe.difficulty == difficulty
        
        # Invalid difficulty should raise error
        with pytest.raises(ValueError):
            Recipe(
                id="bad_recipe",
                title="Bad Recipe",
                yields="1 serving",
                time_total=30,
                difficulty="impossible"
            )


class TestWorkout:
    """Test Workout model"""
    
    def test_workout_creation(self):
        """Test Workout with full data"""
        workout_date = datetime(2024, 6, 15, 7, 0, 0)
        
        workout = Workout(
            id="workout_123",
            date=workout_date,
            type="running",
            duration_m=45,
            avg_hr=150,
            distance_km=5.2,
            source="strava",
            calories=350,
            elevation_m=120.5,
            pace_min_per_km=8.65,
            notes="Morning run in the park",
            route="Park Loop",
            weather="Sunny, 18°C"
        )
        
        assert workout.type == "running"
        assert workout.duration_m == 45
        assert workout.distance_km == 5.2
        assert workout.avg_hr == 150
        assert workout.calories == 350
        assert workout.notes == "Morning run in the park"
    
    def test_workout_minimal(self):
        """Test Workout with minimal fields"""
        workout_date = datetime.now()
        
        workout = Workout(
            id="minimal_workout",
            date=workout_date,
            type="yoga",
            duration_m=30
        )
        
        assert workout.source == "health"  # Default
        assert workout.avg_hr is None
        assert workout.distance_km is None
        assert workout.calories is None


class TestHealthSummary:
    """Test HealthSummary model"""
    
    def test_health_summary_sleep(self):
        """Test HealthSummary for sleep data"""
        summary_date = datetime(2024, 6, 15)
        sleep_data = {
            "total_m": 480,  # 8 hours
            "deep_m": 120,
            "rem_m": 90,
            "light_m": 210,
            "awake_m": 60
        }
        
        health = HealthSummary(
            id="sleep_123",
            date=summary_date,
            type=HealthType.SLEEP,
            aggregates_json=sleep_data,
            source_device="apple_watch"
        )
        
        assert health.type == HealthType.SLEEP
        assert health.aggregates_json == sleep_data
        assert health.source_device == "apple_watch"
    
    def test_health_summary_heart_rate(self):
        """Test HealthSummary for heart rate data"""
        summary_date = datetime(2024, 6, 15)
        hr_data = {
            "resting": 55,
            "avg": 75,
            "max": 165,
            "min": 48
        }
        
        health = HealthSummary(
            id="hr_123",
            date=summary_date,
            type=HealthType.HEART_RATE,
            aggregates_json=hr_data
        )
        
        assert health.type == HealthType.HEART_RATE
        assert health.aggregates_json == hr_data
        assert health.source_device is None  # Default


class TestTransaction:
    """Test Transaction model"""
    
    def test_transaction_creation(self):
        """Test Transaction with full data"""
        transaction_date = datetime(2024, 6, 15, 14, 30, 0)
        
        transaction = Transaction(
            id="txn_123",
            date=transaction_date,
            amount=45.67,
            currency="USD",
            account="checking",
            category="groceries",
            memo="Weekly grocery shopping",
            merchant="Whole Foods",
            pending=False,
            tags=["food", "essential"],
            receipt_path="/receipts/2024-06-15-whole-foods.pdf",
            split_amount=22.84,
            reimbursable=True
        )
        
        assert transaction.amount == 45.67
        assert transaction.currency == "USD"
        assert transaction.category == "groceries"
        assert transaction.merchant == "Whole Foods"
        assert transaction.reimbursable is True
        assert transaction.split_amount == 22.84
    
    def test_transaction_minimal(self):
        """Test Transaction with minimal fields"""
        transaction_date = datetime.now()
        
        transaction = Transaction(
            id="minimal_txn",
            date=transaction_date,
            amount=10.00,
            account="savings"
        )
        
        assert transaction.currency == "USD"  # Default
        assert transaction.pending is False  # Default
        assert transaction.reimbursable is False  # Default
        assert transaction.tags == []  # Default
        assert transaction.category is None


class TestMediaItem:
    """Test MediaItem model"""
    
    def test_media_item_book(self):
        """Test MediaItem for a book"""
        started_date = datetime(2024, 5, 1)
        completed_date = datetime(2024, 5, 20)
        
        media = MediaItem(
            id="book_123",
            kind=MediaKind.BOOK,
            title="The Great Gatsby",
            creator="F. Scott Fitzgerald",
            started=started_date,
            completed=completed_date,
            rating=4.2,
            year=1925,
            genre=["fiction", "classic"],
            notes="Beautifully written, complex characters",
            source="library",
            isbn="978-0-7432-7356-5",
            duration_minutes=None,  # Not applicable for books
            progress_percent=100.0
        )
        
        assert media.kind == MediaKind.BOOK
        assert media.creator == "F. Scott Fitzgerald"
        assert media.year == 1925
        assert media.isbn == "978-0-7432-7356-5"
        assert media.progress_percent == 100.0
    
    def test_media_item_movie(self):
        """Test MediaItem for a movie"""
        watched_date = datetime(2024, 6, 1)
        
        media = MediaItem(
            id="movie_123",
            kind=MediaKind.MOVIE,
            title="Inception",
            creator="Christopher Nolan",
            completed=watched_date,
            rating=4.8,
            year=2010,
            genre=["sci-fi", "thriller"],
            source="netflix",
            imdb_id="tt1375666",
            duration_minutes=148
        )
        
        assert media.kind == MediaKind.MOVIE
        assert media.creator == "Christopher Nolan"
        assert media.imdb_id == "tt1375666"
        assert media.duration_minutes == 148
    
    def test_media_item_minimal(self):
        """Test MediaItem with minimal fields"""
        media = MediaItem(
            id="minimal_media",
            kind=MediaKind.PODCAST,
            title="Tech Talk",
            creator="Tech Podcast Network"
        )
        
        assert media.genre == []  # Default
        assert media.started is None
        assert media.completed is None
        assert media.rating is None


class TestEntity:
    """Test Entity wrapper model"""
    
    def test_entity_creation(self):
        """Test Entity with full data"""
        now = datetime.now()
        entity_data = {
            "title": "Test Note",
            "content": "This is test content"
        }
        
        entity = Entity(
            id="entity_123",
            type=EntityType.NOTE,
            payload=entity_data,
            created=now,
            updated=now,
            tags=["test", "sample"],
            assistant_id="test_assistant",
            sensitive=True,
            archived=False
        )
        
        assert entity.id == "entity_123"
        assert entity.type == EntityType.NOTE
        assert entity.payload == entity_data
        assert entity.tags == ["test", "sample"]
        assert entity.sensitive is True
    
    def test_entity_datetime_conversion(self):
        """Test Entity datetime to timestamp conversion"""
        now = datetime.now()
        
        entity = Entity(
            id="timestamp_test",
            type=EntityType.TASK,
            payload={"title": "Test"},
            created=now,
            updated=now
        )
        
        # Should convert datetime to int timestamp
        assert isinstance(entity.created, int)
        assert isinstance(entity.updated, int)
        assert entity.created == int(now.timestamp())
    
    def test_entity_minimal(self):
        """Test Entity with minimal fields"""
        entity = Entity(
            id="minimal_entity",
            type=EntityType.NOTE,
            payload={"title": "Minimal"}
        )
        
        assert entity.tags == []  # Default
        assert entity.assistant_id == "archie"  # Default
        assert entity.sensitive is False  # Default
        assert entity.archived is False  # Default


class TestEntityLink:
    """Test EntityLink model"""
    
    def test_entity_link_creation(self):
        """Test EntityLink with metadata"""
        now = int(datetime.now().timestamp())
        metadata = {"strength": 0.8, "auto_generated": True}
        
        link = EntityLink(
            src="entity_1",
            dst="entity_2",
            type="references",
            created=now,
            metadata=metadata
        )
        
        assert link.src == "entity_1"
        assert link.dst == "entity_2"
        assert link.type == "references"
        assert link.metadata == metadata
    
    def test_entity_link_minimal(self):
        """Test EntityLink with minimal fields"""
        now = int(datetime.now().timestamp())
        
        link = EntityLink(
            src="src_entity",
            dst="dst_entity",
            type="related",
            created=now
        )
        
        assert link.metadata == {}  # Default


class TestDevice:
    """Test Device model"""
    
    def test_device_creation(self):
        """Test Device with full data"""
        last_seen = int(datetime.now().timestamp())
        
        device = Device(
            id="device_123",
            name="iPhone 15",
            public_key="test_public_key_data",
            capabilities=["memory.read", "memory.write", "council.deliberate"],
            last_seen=last_seen,
            device_type="iphone",
            os_version="iOS 17.0",
            app_version="1.2.3",
            ip_address="192.168.1.100",
            council_member="percy"
        )
        
        assert device.name == "iPhone 15"
        assert len(device.capabilities) == 3
        assert device.device_type == "iphone"
        assert device.council_member == "percy"
    
    def test_device_minimal(self):
        """Test Device with minimal fields"""
        last_seen = int(datetime.now().timestamp())
        
        device = Device(
            id="minimal_device",
            name="Basic Device",
            public_key="basic_key",
            capabilities=["basic"],
            last_seen=last_seen
        )
        
        assert device.device_type is None  # Default
        assert device.council_member is None  # Default


class TestJob:
    """Test Job model"""
    
    def test_job_creation(self):
        """Test Job with full data"""
        now = int(datetime.now().timestamp())
        next_run = now + 3600
        payload = {"param1": "value1", "param2": 42}
        result = {"output": "success", "processed": 100}
        
        job = Job(
            id="job_123",
            name="data_sync",
            status="completed",
            last_run=now,
            next_run=next_run,
            payload=payload,
            retries=2,
            rrule="FREQ=HOURLY",
            max_retries=5,
            timeout_seconds=600,
            error_message=None,
            result=result
        )
        
        assert job.name == "data_sync"
        assert job.status == "completed"
        assert job.payload == payload
        assert job.result == result
        assert job.max_retries == 5
    
    def test_job_minimal(self):
        """Test Job with minimal fields"""
        job = Job(
            id="minimal_job",
            name="simple_job",
            status="pending"
        )
        
        assert job.payload == {}  # Default
        assert job.retries == 0  # Default
        assert job.max_retries == 3  # Default
        assert job.timeout_seconds == 300  # Default
    
    def test_job_status_validation(self):
        """Test Job status validation"""
        valid_statuses = ["pending", "running", "completed", "failed", "cancelled"]
        
        for status in valid_statuses:
            job = Job(id=f"job_{status}", name="test", status=status)
            assert job.status == status
        
        # Invalid status should raise error
        with pytest.raises(ValueError):
            Job(id="bad_job", name="test", status="invalid_status")


class TestRequestResponseModels:
    """Test API request/response models"""
    
    def test_memory_search_request(self):
        """Test MemorySearchRequest model"""
        since_date = datetime(2024, 1, 1)
        until_date = datetime(2024, 6, 30)
        
        request = MemorySearchRequest(
            query="test search",
            type=EntityType.NOTE,
            since=since_date,
            until=until_date,
            tags=["important", "work"],
            limit=100,
            offset=50,
            include_archived=True
        )
        
        assert request.query == "test search"
        assert request.type == EntityType.NOTE
        assert request.since == since_date
        assert request.limit == 100
        assert request.include_archived is True
    
    def test_memory_search_request_minimal(self):
        """Test MemorySearchRequest with defaults"""
        request = MemorySearchRequest()
        
        assert request.query is None
        assert request.type is None
        assert request.tags == []  # Default
        assert request.limit == 50  # Default
        assert request.offset == 0  # Default
        assert request.include_archived is False  # Default
    
    def test_memory_search_request_validation(self):
        """Test MemorySearchRequest validation"""
        # Test limit validation
        with pytest.raises(ValueError):
            MemorySearchRequest(limit=0)  # Below minimum
        
        with pytest.raises(ValueError):
            MemorySearchRequest(limit=2000)  # Above maximum
        
        # Test offset validation
        with pytest.raises(ValueError):
            MemorySearchRequest(offset=-1)  # Below minimum
    
    def test_memory_upsert_request(self):
        """Test MemoryUpsertRequest model"""
        entity_data = {"title": "Test Note", "content": "Test content"}
        
        request = MemoryUpsertRequest(
            type=EntityType.NOTE,
            entity=entity_data,
            tags=["test", "api"],
            sensitive=True
        )
        
        assert request.type == EntityType.NOTE
        assert request.entity == entity_data
        assert request.sensitive is True
    
    def test_device_register_request(self):
        """Test DeviceRegisterRequest model"""
        request = DeviceRegisterRequest(
            device_name="Test Device",
            public_key="test_key_data",
            scopes=["memory.read", "council.deliberate"],
            device_type="laptop",
            os_version="macOS 14.0",
            app_version="1.0.0"
        )
        
        assert request.device_name == "Test Device"
        assert len(request.scopes) == 2
        assert request.device_type == "laptop"
    
    def test_device_token_response(self):
        """Test DeviceTokenResponse model"""
        expires_at = datetime.now() + timedelta(days=30)
        
        response = DeviceTokenResponse(
            device_id="device_123",
            token="jwt_token_here",
            scopes=["memory.read", "memory.write"],
            expires_at=expires_at
        )
        
        assert response.device_id == "device_123"
        assert response.token == "jwt_token_here"
        assert response.expires_at == expires_at


class TestCouncilModels:
    """Test Council-related models"""
    
    def test_council_member(self):
        """Test CouncilMember model"""
        joined_date = datetime(2024, 1, 1)
        
        member = CouncilMember(
            id="percy",
            name="Percival",
            role="executive",
            capabilities=["ui.interact", "council.summon", "council.deliberate"],
            endpoint_url="https://percy.local:8080",
            public_key="percy_public_key",
            status="active",
            joined_at=joined_date
        )
        
        assert member.id == "percy"
        assert member.name == "Percival"
        assert member.role == "executive"
        assert len(member.capabilities) == 3
        assert member.status == "active"
    
    def test_council_member_minimal(self):
        """Test CouncilMember with minimal fields"""
        member = CouncilMember(
            id="archie",
            name="Archibald",
            role="archivist",
            capabilities=["memory", "storage"],
            public_key="archie_key"
        )
        
        assert member.status == "active"  # Default
        assert isinstance(member.joined_at, datetime)
    
    def test_council_meeting(self):
        """Test CouncilMeeting model"""
        created_time = datetime.now()
        completed_time = created_time + timedelta(minutes=30)
        context = {"user_request": "Analyze data trends"}
        deliberations = [
            {"member": "percy", "contribution": "UI analysis shows..."},
            {"member": "archie", "contribution": "Historical data indicates..."}
        ]
        
        meeting = CouncilMeeting(
            id="meeting_123",
            summoner="percy",
            topic="Data Analysis Request",
            participants=["percy", "archie"],
            status="completed",
            created_at=created_time,
            completed_at=completed_time,
            context=context,
            deliberations=deliberations,
            draft_response="Based on analysis...",
            final_response="Final synthesized response"
        )
        
        assert meeting.summoner == "percy"
        assert len(meeting.participants) == 2
        assert meeting.status == "completed"
        assert len(meeting.deliberations) == 2
    
    def test_council_meeting_minimal(self):
        """Test CouncilMeeting with minimal fields"""
        meeting = CouncilMeeting(
            id="minimal_meeting",
            summoner="archie",
            topic="Simple Request",
            participants=["archie"],
            status="summoned"
        )
        
        assert meeting.context == {}  # Default
        assert meeting.deliberations == []  # Default
        assert meeting.completed_at is None
    
    def test_council_message(self):
        """Test CouncilMessage model"""
        timestamp = datetime.now()
        content = {"request": "Need help with analysis", "data": {"key": "value"}}
        
        message = CouncilMessage(
            id="msg_123",
            from_member="percy",
            to_member="archie",
            meeting_id="meeting_456",
            message_type="request",
            content=content,
            timestamp=timestamp,
            requires_response=True
        )
        
        assert message.from_member == "percy"
        assert message.to_member == "archie"
        assert message.message_type == "request"
        assert message.requires_response is True
    
    def test_council_message_broadcast(self):
        """Test CouncilMessage for broadcast"""
        message = CouncilMessage(
            id="broadcast_msg",
            from_member="archie",
            message_type="notification",
            content={"announcement": "System updated"}
        )
        
        assert message.to_member is None  # Broadcast
        assert message.requires_response is False  # Default


class TestStatsModels:
    """Test statistics models"""
    
    def test_storage_stats(self):
        """Test StorageStats model"""
        entities_by_type = {
            "note": 150,
            "task": 75,
            "event": 25,
            "contact": 50
        }
        
        stats = StorageStats(
            total_entities=300,
            entities_by_type=entities_by_type,
            total_files=1250,
            storage_used_bytes=5368709120,  # 5GB
            hot_tier_count=100,
            warm_tier_count=800,
            cold_tier_count=300,
            vault_tier_count=50,
            recent_uploads=15,
            recent_accesses=45
        )
        
        assert stats.total_entities == 300
        assert stats.entities_by_type["note"] == 150
        assert stats.storage_used_bytes == 5368709120
        assert stats.vault_tier_count == 50
    
    def test_health_stats(self):
        """Test HealthStats model"""
        last_backup = datetime(2024, 6, 15, 2, 0, 0)
        last_snapshot = datetime(2024, 6, 15, 12, 0, 0)
        alerts = ["Disk usage high", "Job failed: data_sync"]
        
        stats = HealthStats(
            uptime_hours=72.5,
            memory_usage_mb=512.3,
            disk_usage_percent=85.2,
            active_jobs=3,
            failed_jobs_24h=1,
            api_requests_24h=1250,
            last_backup=last_backup,
            last_snapshot=last_snapshot,
            alerts=alerts
        )
        
        assert stats.uptime_hours == 72.5
        assert stats.disk_usage_percent == 85.2
        assert len(stats.alerts) == 2
        assert stats.last_backup == last_backup
    
    def test_health_stats_minimal(self):
        """Test HealthStats with minimal fields"""
        stats = HealthStats(
            uptime_hours=24.0,
            memory_usage_mb=256.0,
            disk_usage_percent=45.0,
            active_jobs=0,
            failed_jobs_24h=0,
            api_requests_24h=500
        )
        
        assert stats.last_backup is None  # Default
        assert stats.last_snapshot is None  # Default
        assert stats.alerts == []  # Default


class TestModelEdgeCases:
    """Test edge cases and error conditions"""
    
    def test_invalid_enum_values(self):
        """Test invalid enum values raise errors"""
        # Invalid EntityType
        with pytest.raises(ValueError):
            Entity(
                id="bad_entity",
                type="invalid_type",
                payload={"test": "data"}
            )
        
        # Invalid TaskStatus
        with pytest.raises(ValueError):
            Task(id="bad_task", title="Test", status="invalid_status")
        
        # Invalid MediaKind
        with pytest.raises(ValueError):
            MediaItem(
                id="bad_media",
                kind="invalid_kind",
                title="Test",
                creator="Test Creator"
            )
    
    def test_datetime_edge_cases(self):
        """Test datetime handling edge cases"""
        # Test with timezone-aware datetime
        import pytz
        utc_time = datetime(2024, 6, 15, 12, 0, 0, tzinfo=pytz.UTC)
        
        entity = BaseEntity(id="tz_test", created=utc_time)
        assert entity.created == utc_time
        
        # Test JSON serialization preserves timezone info
        json_data = entity.json()
        assert '+00:00' in json_data  # UTC timezone marker
    
    def test_empty_lists_and_dicts(self):
        """Test models with empty collections"""
        note = NoteSummary(
            id="empty_test",
            title="Empty Test",
            snippet="Test",
            tags=[],  # Explicit empty list
            source_paths=[]
        )
        
        assert note.tags == []
        assert note.source_paths == []
        
        # Test serialization
        json_data = note.json()
        assert '"tags":[]' in json_data
    
    def test_field_validation_errors(self):
        """Test field validation error messages"""
        # Test required field missing
        try:
            NoteSummary(id="test")  # Missing required fields
        except ValueError as e:
            assert "field required" in str(e).lower()
        
        # Test invalid literal value
        try:
            Event(
                id="bad_event",
                title="Test",
                start=datetime.now(),
                end=datetime.now(),
                status="invalid_status"
            )
        except ValueError as e:
            assert "not permitted" in str(e).lower() or "invalid" in str(e).lower()
    
    def test_model_serialization_roundtrip(self):
        """Test model serialization and deserialization"""
        original_note = NoteSummary(
            id="roundtrip_test",
            title="Serialization Test",
            snippet="Test serialization roundtrip",
            tags=["test", "serialization"],
            word_count=42,
            sentiment="positive"
        )
        
        # Serialize to JSON
        json_data = original_note.json()
        
        # Deserialize back to model
        restored_note = NoteSummary.parse_raw(json_data)
        
        # Should be identical
        assert restored_note.id == original_note.id
        assert restored_note.title == original_note.title
        assert restored_note.tags == original_note.tags
        assert restored_note.word_count == original_note.word_count
    
    def test_nested_dict_validation(self):
        """Test validation of nested dictionary fields"""
        # Test valid nested data
        health = HealthSummary(
            id="nested_test",
            date=datetime.now(),
            type=HealthType.SLEEP,
            aggregates_json={
                "total_m": 480,
                "deep_m": 120,
                "nested": {"key": "value"}
            }
        )
        
        assert "nested" in health.aggregates_json
        assert health.aggregates_json["nested"]["key"] == "value"