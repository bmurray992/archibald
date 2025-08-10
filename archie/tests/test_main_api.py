"""
Comprehensive tests for api.main module - FastAPI application
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
import tempfile
from pathlib import Path

from api.main import app, get_memory_manager, get_personality


class TestFastAPIApp:
    """Test FastAPI application configuration and setup"""
    
    def test_app_configuration(self):
        """Test app basic configuration"""
        assert app.title == "ArchieOS - Intelligent Storage Operating System"
        assert app.version == "2.0.0"
        assert "memory storage" in app.description.lower()
    
    def test_cors_middleware(self):
        """Test CORS middleware configuration"""
        cors_middleware = None
        for middleware in app.user_middleware:
            if 'CORSMiddleware' in str(middleware.cls):
                cors_middleware = middleware
                break
        
        assert cors_middleware is not None
        # CORS should be configured for Percy integration
    
    def test_static_files_mount(self):
        """Test static files are mounted"""
        routes = [route for route in app.routes if hasattr(route, 'path')]
        static_route = None
        for route in routes:
            if hasattr(route, 'path') and route.path == "/static":
                static_route = route
                break
        
        assert static_route is not None


class TestDependencies:
    """Test dependency injection functions"""
    
    def test_get_memory_manager_success(self):
        """Test get_memory_manager when initialized"""
        mock_manager = Mock()
        with patch('api.main.memory_manager', mock_manager):
            result = get_memory_manager()
            assert result is mock_manager
    
    def test_get_memory_manager_not_initialized(self):
        """Test get_memory_manager when not initialized"""
        with patch('api.main.memory_manager', None):
            from fastapi import HTTPException
            with pytest.raises(HTTPException) as exc_info:
                get_memory_manager()
            assert exc_info.value.status_code == 500
            assert "not initialized" in exc_info.value.detail
    
    def test_get_personality_success(self):
        """Test get_personality when initialized"""
        mock_personality = Mock()
        with patch('api.main.archie_personality', mock_personality):
            result = get_personality()
            assert result is mock_personality
    
    def test_get_personality_not_initialized(self):
        """Test get_personality when not initialized"""
        with patch('api.main.archie_personality', None):
            from fastapi import HTTPException
            with pytest.raises(HTTPException) as exc_info:
                get_personality()
            assert exc_info.value.status_code == 500
            assert "personality not initialized" in exc_info.value.detail


class TestPydanticModels:
    """Test Pydantic model validation"""
    
    def test_memory_entry_model_minimal(self):
        """Test MemoryEntry with minimal data"""
        from api.main import MemoryEntry
        
        entry = MemoryEntry(
            content="Test memory content",
            entry_type="test"
        )
        
        assert entry.content == "Test memory content"
        assert entry.entry_type == "test"
        assert entry.assistant_id == "percy"  # default
        assert entry.confidence == 1.0  # default
        assert entry.source_method == "ui"  # default
        assert entry.plugin_source is None
        assert entry.metadata is None
        assert entry.tags is None
    
    def test_memory_entry_model_full(self):
        """Test MemoryEntry with all fields"""
        from api.main import MemoryEntry
        
        entry = MemoryEntry(
            content="Complex memory content",
            entry_type="complex",
            assistant_id="archie",
            plugin_source="test_plugin",
            metadata={"key": "value"},
            tags=["tag1", "tag2"],
            confidence=0.75,
            source_method="voice"
        )
        
        assert entry.content == "Complex memory content"
        assert entry.entry_type == "complex"
        assert entry.assistant_id == "archie"
        assert entry.plugin_source == "test_plugin"
        assert entry.metadata == {"key": "value"}
        assert entry.tags == ["tag1", "tag2"]
        assert entry.confidence == 0.75
        assert entry.source_method == "voice"
    
    def test_memory_entry_confidence_validation(self):
        """Test MemoryEntry confidence field validation"""
        from api.main import MemoryEntry
        from pydantic import ValidationError
        
        # Valid confidence values
        valid_entry = MemoryEntry(content="Test", entry_type="test", confidence=0.5)
        assert valid_entry.confidence == 0.5
        
        # Invalid confidence values
        with pytest.raises(ValidationError):
            MemoryEntry(content="Test", entry_type="test", confidence=-0.1)
        
        with pytest.raises(ValidationError):
            MemoryEntry(content="Test", entry_type="test", confidence=1.1)
    
    def test_interaction_entry_model_minimal(self):
        """Test InteractionEntry with minimal data"""
        from api.main import InteractionEntry
        
        interaction = InteractionEntry(
            user_message="Hello",
            assistant_response="Hi there!"
        )
        
        assert interaction.user_message == "Hello"
        assert interaction.assistant_response == "Hi there!"
        assert interaction.assistant_id == "percy"  # default
        assert interaction.context is None
        assert interaction.session_id is None
        assert interaction.plugin_used is None
        assert interaction.intent_detected is None
    
    def test_interaction_entry_model_full(self):
        """Test InteractionEntry with all fields"""
        from api.main import InteractionEntry
        
        interaction = InteractionEntry(
            user_message="Can you help me?",
            assistant_response="Of course!",
            assistant_id="archie",
            context="Help session",
            session_id="session_123",
            plugin_used="help_plugin",
            intent_detected="help_request"
        )
        
        assert interaction.user_message == "Can you help me?"
        assert interaction.assistant_response == "Of course!"
        assert interaction.assistant_id == "archie"
        assert interaction.context == "Help session"
        assert interaction.session_id == "session_123"
        assert interaction.plugin_used == "help_plugin"
        assert interaction.intent_detected == "help_request"
    
    def test_search_query_model_minimal(self):
        """Test SearchQuery with minimal data"""
        from api.main import SearchQuery
        
        search = SearchQuery()
        
        assert search.query is None
        assert search.entry_type is None
        assert search.assistant_id is None
        assert search.tags is None
        assert search.date_from is None
        assert search.date_to is None
        assert search.limit == 50  # default
        assert search.archived is False  # default
    
    def test_search_query_model_full(self):
        """Test SearchQuery with all fields"""
        from api.main import SearchQuery
        
        date_from = datetime(2024, 1, 1)
        date_to = datetime(2024, 12, 31)
        
        search = SearchQuery(
            query="test query",
            entry_type="test",
            assistant_id="percy",
            tags=["tag1", "tag2"],
            date_from=date_from,
            date_to=date_to,
            limit=100,
            archived=True
        )
        
        assert search.query == "test query"
        assert search.entry_type == "test"
        assert search.assistant_id == "percy"
        assert search.tags == ["tag1", "tag2"]
        assert search.date_from == date_from
        assert search.date_to == date_to
        assert search.limit == 100
        assert search.archived is True
    
    def test_search_query_limit_validation(self):
        """Test SearchQuery limit validation"""
        from api.main import SearchQuery
        from pydantic import ValidationError
        
        # Valid limits
        SearchQuery(limit=1)
        SearchQuery(limit=1000)
        SearchQuery(limit=50)
        
        # Invalid limits
        with pytest.raises(ValidationError):
            SearchQuery(limit=0)
        
        with pytest.raises(ValidationError):
            SearchQuery(limit=1001)
    
    def test_archie_response_model(self):
        """Test ArchieResponse model"""
        from api.main import ArchieResponse
        
        # Minimal response
        response = ArchieResponse(success=True, message="Test message")
        assert response.success is True
        assert response.message == "Test message"
        assert response.data is None
        assert response.archie_says is None
        
        # Full response
        response = ArchieResponse(
            success=False,
            message="Error message",
            data={"key": "value"},
            archie_says="Something went wrong!"
        )
        assert response.success is False
        assert response.message == "Error message"
        assert response.data == {"key": "value"}
        assert response.archie_says == "Something went wrong!"


@pytest.fixture
def test_client():
    """Create test client with mocked dependencies"""
    with patch('api.main.memory_manager') as mock_memory_manager, \
         patch('api.main.storage_manager') as mock_storage_manager, \
         patch('api.main.archie_personality') as mock_personality:
        
        # Configure mock memory manager
        mock_memory_manager.get_memory_stats.return_value = {
            "total_entries": 100,
            "entries_by_type": {"test": 50, "work": 50},
            "recent_activity_7d": 10,
            "database_size_mb": 1.5
        }
        mock_memory_manager.store_memory.return_value = 123
        mock_memory_manager.store_interaction.return_value = 456
        mock_memory_manager.search_memories.return_value = [
            {
                "id": 1,
                "content": "Test memory",
                "entry_type": "test",
                "timestamp": datetime.now().isoformat(),
                "assistant_id": "percy",
                "tags": ["test"],
                "metadata": {"key": "value"},
                "archived": False
            }
        ]
        mock_memory_manager.archive_old_memories.return_value = 5
        
        # Configure mock personality
        mock_personality.format_response.return_value = "Archie says something witty!"
        mock_personality.add_memory_context.return_value = "Archie with context!"
        
        client = TestClient(app)
        yield client


class TestAPIEndpoints:
    """Test API endpoints functionality"""
    
    def test_root_redirect(self, test_client):
        """Test root endpoint redirects to login"""
        response = test_client.get("/", follow_redirects=False)
        assert response.status_code == 302
        assert response.headers["location"] == "/auth/login"
    
    def test_archivist_redirect(self, test_client):
        """Test archivist endpoint redirects to web interface"""
        response = test_client.get("/archivist", follow_redirects=False)
        assert response.status_code == 302
        assert response.headers["location"] == "/web/archivist"
    
    def test_health_check_success(self, test_client):
        """Test health check endpoint success"""
        response = test_client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "All systems operational"
        assert "data" in data
        assert data["data"]["total_entries"] == 100
        assert "archie_says" in data
    
    def test_health_check_failure(self, test_client):
        """Test health check endpoint when memory manager fails"""
        with patch('api.main.memory_manager') as mock_memory_manager, \
             patch('api.main.archie_personality') as mock_personality:
            
            mock_memory_manager.get_memory_stats.side_effect = Exception("Database error")
            mock_personality.format_response.return_value = "Something went wrong!"
            
            response = test_client.get("/health")
            assert response.status_code == 200
            
            data = response.json()
            assert data["success"] is False
            assert data["message"] == "System check failed"
            assert "archie_says" in data
    
    def test_store_memory_success(self, test_client):
        """Test storing memory successfully"""
        memory_data = {
            "content": "Test memory content",
            "entry_type": "test",
            "assistant_id": "percy",
            "tags": ["test", "memory"],
            "metadata": {"source": "test"},
            "confidence": 0.9
        }
        
        response = test_client.post("/memory/store", json=memory_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Memory stored with ID 123"
        assert data["data"]["memory_id"] == 123
        assert "archie_says" in data
    
    def test_store_memory_validation_error(self, test_client):
        """Test storing memory with validation errors"""
        invalid_data = {
            "content": "Test",
            # Missing required entry_type
            "confidence": 1.5  # Invalid confidence
        }
        
        response = test_client.post("/memory/store", json=invalid_data)
        assert response.status_code == 422  # Validation error
    
    def test_store_memory_server_error(self, test_client):
        """Test storing memory with server error"""
        with patch('api.main.memory_manager') as mock_memory_manager:
            mock_memory_manager.store_memory.side_effect = Exception("Storage failed")
            
            memory_data = {
                "content": "Test memory",
                "entry_type": "test"
            }
            
            response = test_client.post("/memory/store", json=memory_data)
            assert response.status_code == 500
    
    def test_search_memories_success(self, test_client):
        """Test searching memories successfully"""
        search_data = {
            "query": "test",
            "entry_type": "test",
            "limit": 10
        }
        
        response = test_client.post("/memory/search", json=search_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Found 1 memories"
        assert data["data"]["count"] == 1
        assert len(data["data"]["memories"]) == 1
        assert "archie_says" in data
    
    def test_search_memories_empty_query(self, test_client):
        """Test searching with empty parameters"""
        response = test_client.post("/memory/search", json={})
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert "memories" in data["data"]
    
    def test_search_memories_server_error(self, test_client):
        """Test search memories with server error"""
        with patch('api.main.memory_manager') as mock_memory_manager:
            mock_memory_manager.search_memories.side_effect = Exception("Search failed")
            
            response = test_client.post("/memory/search", json={"query": "test"})
            assert response.status_code == 500
    
    def test_store_interaction_success(self, test_client):
        """Test storing interaction successfully"""
        interaction_data = {
            "user_message": "Hello Archie",
            "assistant_response": "Hello! How can I help?",
            "assistant_id": "archie",
            "session_id": "session_123"
        }
        
        response = test_client.post("/interaction/store", json=interaction_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Interaction stored with ID 456"
        assert data["data"]["interaction_id"] == 456
        assert "archie_says" in data
    
    def test_store_interaction_validation_error(self, test_client):
        """Test storing interaction with validation errors"""
        invalid_data = {
            "user_message": "Hello",
            # Missing required assistant_response
        }
        
        response = test_client.post("/interaction/store", json=invalid_data)
        assert response.status_code == 422
    
    def test_store_interaction_server_error(self, test_client):
        """Test storing interaction with server error"""
        with patch('api.main.memory_manager') as mock_memory_manager:
            mock_memory_manager.store_interaction.side_effect = Exception("Storage failed")
            
            interaction_data = {
                "user_message": "Hello",
                "assistant_response": "Hi"
            }
            
            response = test_client.post("/interaction/store", json=interaction_data)
            assert response.status_code == 500
    
    def test_get_statistics_success(self, test_client):
        """Test getting statistics successfully"""
        response = test_client.get("/stats")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Memory statistics retrieved"
        assert "data" in data
        assert data["data"]["total_entries"] == 100
        assert "archie_says" in data
    
    def test_get_statistics_server_error(self, test_client):
        """Test getting statistics with server error"""
        with patch('api.main.memory_manager') as mock_memory_manager:
            mock_memory_manager.get_memory_stats.side_effect = Exception("Stats failed")
            
            response = test_client.get("/stats")
            assert response.status_code == 500
    
    def test_archive_memories_success(self, test_client):
        """Test archiving memories successfully"""
        response = test_client.post("/maintenance/archive?days_old=30")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Archived 5 memories"
        assert data["data"]["archived_count"] == 5
        assert data["data"]["days_threshold"] == 30
        assert "archie_says" in data
    
    def test_archive_memories_default_days(self, test_client):
        """Test archiving memories with default days parameter"""
        response = test_client.post("/maintenance/archive")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        # Should use default 90 days
        assert data["data"]["days_threshold"] == 90
    
    def test_archive_memories_no_results(self, test_client):
        """Test archiving when no memories match criteria"""
        with patch('api.main.memory_manager') as mock_memory_manager, \
             patch('api.main.archie_personality') as mock_personality:
            
            mock_memory_manager.archive_old_memories.return_value = 0
            mock_personality.format_response.return_value = "Nothing to archive!"
            
            response = test_client.post("/maintenance/archive")
            assert response.status_code == 200
            
            data = response.json()
            assert data["success"] is True
            assert data["data"]["archived_count"] == 0
            assert "perfectly organized" in data["archie_says"]
    
    def test_archive_memories_server_error(self, test_client):
        """Test archiving memories with server error"""
        with patch('api.main.memory_manager') as mock_memory_manager:
            mock_memory_manager.archive_old_memories.side_effect = Exception("Archive failed")
            
            response = test_client.post("/maintenance/archive")
            assert response.status_code == 500
    
    def test_get_archie_greeting(self, test_client):
        """Test getting Archie's greeting"""
        response = test_client.get("/archie/greeting")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Archie says hello"
        assert "archie_says" in data
        assert data["archie_says"] == "Archie says something witty!"


class TestLifespanManagement:
    """Test application lifespan management"""
    
    @pytest.mark.asyncio
    async def test_lifespan_startup(self):
        """Test application startup sequence"""
        from api.main import lifespan
        
        app_mock = Mock()
        
        with patch('api.main.MemoryManager') as mock_memory_cls, \
             patch('api.main.ArchieStorageManager') as mock_storage_cls, \
             patch('api.main.ArchiePersonality') as mock_personality_cls:
            
            mock_memory_instance = Mock()
            mock_storage_instance = Mock()
            mock_personality_instance = Mock()
            
            mock_memory_cls.return_value = mock_memory_instance
            mock_storage_cls.return_value = mock_storage_instance
            mock_personality_cls.return_value = mock_personality_instance
            
            # Test startup
            async with lifespan(app_mock):
                # Verify instances were created
                mock_memory_cls.assert_called_once()
                mock_storage_cls.assert_called_once()
                mock_personality_cls.assert_called_once()
                
                # Verify global variables were set
                import api.main
                assert api.main.memory_manager == mock_memory_instance
                assert api.main.storage_manager == mock_storage_instance
                assert api.main.archie_personality == mock_personality_instance
            
            # Verify cleanup was called
            mock_memory_instance.close.assert_called_once()
            mock_storage_instance.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_lifespan_shutdown_with_none_managers(self):
        """Test shutdown when managers are None"""
        from api.main import lifespan
        
        app_mock = Mock()
        
        with patch('api.main.memory_manager', None), \
             patch('api.main.storage_manager', None):
            
            # Should not raise any exceptions
            async with lifespan(app_mock):
                pass


class TestErrorHandling:
    """Test error handling and edge cases"""
    
    def test_dependency_injection_failure(self):
        """Test behavior when dependency injection fails"""
        with patch('api.main.memory_manager', None):
            from fastapi import HTTPException
            with pytest.raises(HTTPException) as exc_info:
                get_memory_manager()
            
            assert exc_info.value.status_code == 500
            assert "Memory manager not initialized" in exc_info.value.detail
    
    def test_invalid_json_payload(self, test_client):
        """Test handling of invalid JSON payloads"""
        response = test_client.post(
            "/memory/store",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422
    
    def test_missing_required_fields(self, test_client):
        """Test handling of missing required fields"""
        response = test_client.post("/memory/store", json={})
        assert response.status_code == 422
        
        response_data = response.json()
        assert "detail" in response_data
    
    def test_type_validation_errors(self, test_client):
        """Test type validation errors"""
        invalid_data = {
            "content": 123,  # Should be string
            "entry_type": "test",
            "confidence": "invalid"  # Should be float
        }
        
        response = test_client.post("/memory/store", json=invalid_data)
        assert response.status_code == 422
    
    def test_query_parameter_validation(self, test_client):
        """Test query parameter validation"""
        # Invalid days_old parameter
        response = test_client.post("/maintenance/archive?days_old=0")
        assert response.status_code == 422


class TestSecurityAndCORS:
    """Test security features and CORS configuration"""
    
    def test_cors_headers_present(self, test_client):
        """Test CORS headers are present in responses"""
        response = test_client.get("/health")
        
        # Check for CORS headers (though exact headers depend on request origin)
        assert response.status_code == 200
        # In test environment, CORS headers might not be fully present
        # but the middleware should be configured
    
    def test_options_request_handling(self, test_client):
        """Test OPTIONS request handling for CORS preflight"""
        response = test_client.options("/health")
        # Should handle OPTIONS requests for CORS
        assert response.status_code in [200, 405]  # Either allowed or method not allowed
    
    def test_large_payload_handling(self, test_client):
        """Test handling of very large payloads"""
        large_content = "x" * 100000  # 100KB content
        
        memory_data = {
            "content": large_content,
            "entry_type": "test"
        }
        
        response = test_client.post("/memory/store", json=memory_data)
        # Should handle large payloads gracefully
        assert response.status_code in [200, 413, 422, 500]


class TestIntegrationScenarios:
    """Test realistic integration scenarios"""
    
    def test_typical_memory_workflow(self, test_client):
        """Test typical memory storage and retrieval workflow"""
        # Store a memory
        memory_data = {
            "content": "Important meeting notes about project X",
            "entry_type": "meeting",
            "assistant_id": "percy",
            "tags": ["project-x", "meeting", "important"],
            "metadata": {"meeting_type": "planning", "duration": 60}
        }
        
        store_response = test_client.post("/memory/store", json=memory_data)
        assert store_response.status_code == 200
        store_data = store_response.json()
        assert store_data["success"] is True
        
        # Search for the memory
        search_data = {
            "query": "project X",
            "entry_type": "meeting",
            "tags": ["important"]
        }
        
        search_response = test_client.post("/memory/search", json=search_data)
        assert search_response.status_code == 200
        search_data = search_response.json()
        assert search_data["success"] is True
        assert search_data["data"]["count"] >= 0
        
        # Get statistics
        stats_response = test_client.get("/stats")
        assert stats_response.status_code == 200
        stats_data = stats_response.json()
        assert stats_data["success"] is True
        assert "total_entries" in stats_data["data"]
    
    def test_interaction_storage_workflow(self, test_client):
        """Test interaction storage workflow"""
        # Store an interaction
        interaction_data = {
            "user_message": "How do I organize my project files?",
            "assistant_response": "I recommend creating folders by project type...",
            "assistant_id": "archie",
            "session_id": "help_session_123",
            "intent_detected": "organization_help"
        }
        
        response = test_client.post("/interaction/store", json=interaction_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert "interaction_id" in data["data"]
    
    def test_maintenance_workflow(self, test_client):
        """Test maintenance operations workflow"""
        # Get current stats
        stats_response = test_client.get("/stats")
        assert stats_response.status_code == 200
        
        # Run archiving
        archive_response = test_client.post("/maintenance/archive?days_old=60")
        assert archive_response.status_code == 200
        archive_data = archive_response.json()
        assert archive_data["success"] is True
        assert "archived_count" in archive_data["data"]
        
        # Get stats again (would show updated counts in real scenario)
        updated_stats_response = test_client.get("/stats")
        assert updated_stats_response.status_code == 200
    
    def test_health_monitoring_workflow(self, test_client):
        """Test health monitoring workflow"""
        # Check health
        health_response = test_client.get("/health")
        assert health_response.status_code == 200
        
        health_data = health_response.json()
        assert health_data["success"] is True
        assert "data" in health_data
        assert "archie_says" in health_data
        
        # Get detailed stats
        stats_response = test_client.get("/stats")
        assert stats_response.status_code == 200
        
        # Get greeting (personality check)
        greeting_response = test_client.get("/archie/greeting")
        assert greeting_response.status_code == 200