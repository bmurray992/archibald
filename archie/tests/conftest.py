"""
Comprehensive test configuration and fixtures for ArchieOS tests
"""
import pytest
import tempfile
import shutil
import asyncio
from pathlib import Path
from typing import Generator
import sqlite3
import os
import sys
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from fastapi.testclient import TestClient

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


# Global test configuration
@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Set up test environment variables"""
    # Set test mode
    os.environ["ARCHIE_TEST_MODE"] = "true"
    os.environ["ARCHIE_LOG_LEVEL"] = "WARNING"  # Reduce log noise during tests
    
    # Use test-specific configurations
    os.environ["ARCHIE_SECRET_KEY"] = "test-secret-key-for-testing-only"
    os.environ["ARCHIE_JWT_ISS"] = "archie-test"
    os.environ["ARCHIE_JWT_EXP_DAYS"] = "1"
    
    yield
    
    # Cleanup
    for key in ["ARCHIE_TEST_MODE", "ARCHIE_LOG_LEVEL", "ARCHIE_SECRET_KEY", 
                "ARCHIE_JWT_ISS", "ARCHIE_JWT_EXP_DAYS"]:
        if key in os.environ:
            del os.environ[key]

from archie_core.storage_config import init_storage_config, ArchieStorageConfig
from archie_core.file_manager import ArchieFileManager
from archie_core.auth_manager import AuthManager
from archie_core.memory_backup_system import MemoryBackupSystem
from archie_core.auto_pruner import AutoPruner


@pytest.fixture
def temp_storage_root() -> Generator[Path, None, None]:
    """Create a temporary storage root for testing"""
    temp_dir = tempfile.mkdtemp(prefix="archie_test_")
    temp_path = Path(temp_dir)
    
    yield temp_path
    
    # Cleanup
    if temp_path.exists():
        shutil.rmtree(str(temp_path))


@pytest.fixture
def storage_config(temp_storage_root: Path) -> ArchieStorageConfig:
    """Create a test storage configuration"""
    return init_storage_config(custom_root=str(temp_storage_root))


@pytest.fixture
def file_manager(storage_config: ArchieStorageConfig) -> ArchieFileManager:
    """Create a test file manager"""
    return ArchieFileManager()


@pytest.fixture
def auth_manager(temp_storage_root: Path) -> AuthManager:
    """Create a test auth manager"""
    config_path = temp_storage_root / "test_auth_tokens.json"
    return AuthManager(config_file=str(config_path))


@pytest.fixture
def memory_backup_system(storage_config: ArchieStorageConfig) -> MemoryBackupSystem:
    """Create a test memory backup system"""
    return MemoryBackupSystem()


@pytest.fixture
def auto_pruner(storage_config: ArchieStorageConfig) -> AutoPruner:
    """Create a test auto pruner"""
    return AutoPruner()


@pytest.fixture
def sample_file_content() -> bytes:
    """Sample file content for testing"""
    return b"This is test file content for ArchieOS unit tests."


@pytest.fixture
def sample_text_file(temp_storage_root: Path) -> Path:
    """Create a sample text file for testing"""
    file_path = temp_storage_root / "sample.txt"
    with open(file_path, 'w') as f:
        f.write("Sample text file content for testing.")
    return file_path


@pytest.fixture
def sample_binary_file(temp_storage_root: Path) -> Path:
    """Create a sample binary file for testing"""
    file_path = temp_storage_root / "sample.bin"
    with open(file_path, 'wb') as f:
        f.write(b'\x00\x01\x02\x03\x04\x05' * 100)  # Some binary data
    return file_path


@pytest.fixture
def populated_storage(file_manager: ArchieFileManager, sample_file_content: bytes) -> ArchieFileManager:
    """Create a file manager with some test files"""
    import io
    
    test_files = [
        {
            'content': sample_file_content,
            'filename': 'test1.txt',
            'tags': ['test', 'document'],
            'plugin_source': 'test_plugin',
            'description': 'First test file'
        },
        {
            'content': b'{"key": "value", "test": true}',
            'filename': 'test2.json',
            'tags': ['test', 'json', 'config'],
            'plugin_source': 'config_plugin',
            'description': 'JSON test file'
        },
        {
            'content': b'Binary test data' * 50,
            'filename': 'test3.bin',
            'tags': ['test', 'binary'],
            'plugin_source': 'binary_plugin',
            'description': 'Binary test file'
        }
    ]
    
    for file_data in test_files:
        content_io = io.BytesIO(file_data['content'])
        file_manager.store_file(
            file_content=content_io,
            original_filename=file_data['filename'],
            tags=file_data['tags'],
            plugin_source=file_data['plugin_source'],
            description=file_data['description']
        )
    
    return file_manager


@pytest.fixture
def mock_memory_db(temp_storage_root: Path) -> Path:
    """Create a mock memory database for testing"""
    db_path = temp_storage_root / "test_memory.db"
    
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute("""
            CREATE TABLE memories (
                id INTEGER PRIMARY KEY,
                content TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Insert some test data
        test_memories = [
            ("Test memory 1",),
            ("Test memory 2",),
            ("Test memory 3",)
        ]
        
        conn.executemany(
            "INSERT INTO memories (content) VALUES (?)",
            test_memories
        )
        conn.commit()
    
    return db_path


@pytest.fixture(autouse=True)
def cleanup_global_state():
    """Reset global state before each test"""
    # Reset storage config global instance
    import archie_core.storage_config
    archie_core.storage_config._storage_config = None
    
    yield
    
    # Cleanup after test
    archie_core.storage_config._storage_config = None


# Additional comprehensive fixtures for new test modules

@pytest.fixture
def temp_db_dir():
    """Create temporary directory for test databases (alias for temp_storage_root)"""
    with tempfile.TemporaryDirectory(prefix="archie_test_") as temp_dir:
        yield Path(temp_dir)

@pytest.fixture
def memory_manager_mock():
    """Mock memory manager for testing"""
    mock = Mock()
    
    # Configure common methods
    mock.store_memory.return_value = 123
    mock.store_interaction.return_value = 456
    mock.search_memories.return_value = []
    mock.get_memory_stats.return_value = {
        "total_entries": 0,
        "entries_by_type": {},
        "recent_activity_7d": 0,
        "database_size_mb": 0.1
    }
    mock.archive_old_memories.return_value = 0
    
    return mock


@pytest.fixture
def personality_mock():
    """Mock personality for testing"""
    mock = Mock()
    
    # Configure common methods
    mock.format_response.return_value = "Test personality response"
    mock.add_memory_context.return_value = "Test response with context"
    
    return mock


@pytest.fixture
def test_client_with_mocks(memory_manager_mock, personality_mock):
    """Create FastAPI test client with mocked dependencies"""
    from api.main import app
    
    # Patch global instances
    with patch('api.main.memory_manager', memory_manager_mock), \
         patch('api.main.archie_personality', personality_mock):
        
        client = TestClient(app)
        yield client


@pytest.fixture
def sample_memory_data():
    """Sample memory entry data for testing"""
    return {
        "content": "This is a test memory entry",
        "entry_type": "test",
        "assistant_id": "percy",
        "plugin_source": "test_plugin",
        "metadata": {"test": True, "priority": "high"},
        "tags": ["test", "memory", "sample"],
        "confidence": 0.95,
        "source_method": "api"
    }


@pytest.fixture
def sample_interaction_data():
    """Sample interaction data for testing"""
    return {
        "user_message": "Hello, can you help me?",
        "assistant_response": "Of course! I'm happy to help.",
        "assistant_id": "percy",
        "context": "Help request session",
        "session_id": "test_session_123",
        "plugin_used": "help_assistant",
        "intent_detected": "help_request"
    }


@pytest.fixture
def sample_device_data():
    """Sample device registration data for testing"""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.backends import default_backend
    
    # Generate test key pair
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )
    
    public_key_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()
    
    return {
        "device_name": "test_device",
        "public_key": public_key_pem,
        "scopes": ["memory.read", "memory.write"],
        "device_type": "laptop",
        "os_version": "Test OS 1.0",
        "app_version": "1.0.0"
    }


# Markers configuration
def pytest_configure(config):
    """Configure custom pytest markers"""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "api: API tests")
    config.addinivalue_line("markers", "auth: Authentication tests")
    config.addinivalue_line("markers", "db: Database tests")
    config.addinivalue_line("markers", "memory: Memory management tests")
    config.addinivalue_line("markers", "council: Council collaboration tests")
    config.addinivalue_line("markers", "jobs: Job scheduling tests")
    config.addinivalue_line("markers", "ocr: OCR processing tests")
    config.addinivalue_line("markers", "enricher: Data enrichment tests")
    config.addinivalue_line("markers", "slow: Slow running tests")
    config.addinivalue_line("markers", "external: Tests requiring external services")