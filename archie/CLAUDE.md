# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ArchieOS is a Personal Archive Operating System - an intelligent storage and memory management system running on Raspberry Pi. It's a modular, plugin-aware mini operating system that provides intelligent file storage, long-term memory archival, and seamless integration with Percy and other AI assistants.

## Quick Start Commands

```bash
# Setup virtual environment
cd archie/
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Run development server with auto-reload
./run_dev.sh
# or manually:
uvicorn api.main:app --host 0.0.0.0 --port 8090 --reload

# Run production server
python run_archie.py
# or
python -m api.main

# Run tests
python test_archie.py          # Test core memory functionality
python test_archie_os.py       # Test storage system
python test_api_startup.py     # Test API startup
pytest tests/                  # Run full test suite

# Default credentials
URL: http://localhost:8090
Login: admin / admin
```

## Architecture

### Technology Stack
- **Framework**: FastAPI with Uvicorn
- **Database**: SQLite with FTS5 (Full-Text Search)
- **Authentication**: JWT tokens with passlib/bcrypt
- **Frontend**: Vanilla JS with custom CSS (Archivist interface)
- **Testing**: pytest with pytest-asyncio

### Core Architecture

```
ArchieOS
├── Memory Management Layer
│   ├── Long-term memory storage (SQLite + FTS5)
│   ├── Pattern detection and insights
│   └── Automatic archival and pruning
├── Storage Management Layer
│   ├── Multi-tier file storage (Hot/Warm/Cold/Vault)
│   ├── Plugin-aware organization
│   └── Automatic backup system
├── API Layer (FastAPI)
│   ├── RESTful endpoints
│   ├── JWT authentication
│   └── CORS for Percy integration
└── Personality Layer
    └── Archie's character responses
```

### Directory Structure

```
archie/
├── archie_core/              # Core ArchieOS modules
│   ├── memory_manager.py     # Memory operations (search, store, archive)
│   ├── storage_manager.py    # File system management
│   ├── file_manager.py       # File metadata and operations
│   ├── auth_manager.py       # Authentication and token management
│   ├── backup_manager.py     # Automated backup system
│   ├── auto_pruner.py        # Automatic memory pruning
│   ├── scheduler.py          # Task scheduling
│   ├── personality.py        # Archie's personality engine
│   └── storage_config.py     # Storage tier configuration
├── api/                      # FastAPI application
│   ├── main.py              # Main application and lifespan management
│   ├── endpoints/           # API endpoint modules
│   │   ├── auth.py          # Authentication endpoints
│   │   ├── storage.py       # File storage operations
│   │   ├── system.py        # System health and stats
│   │   ├── backup.py        # Backup operations
│   │   └── web.py           # Web interface endpoints
│   └── middleware/          # Custom middleware
│       └── auth.py          # Authentication middleware
├── storage/                 # ArchieOS file system root
│   ├── plugins/            # Plugin-specific storage areas
│   │   ├── calendar/       
│   │   ├── reminders/      
│   │   ├── health/         
│   │   ├── journal/        
│   │   ├── media/          
│   │   ├── research/       
│   │   └── tasks/          
│   ├── media/              # General media storage
│   ├── vault/              # Encrypted sensitive files
│   ├── cold/               # Archived/compressed files
│   ├── exports/            # Export and backup files
│   ├── temp/               # Temporary files
│   └── thumbnails/         # Generated thumbnails
├── database/               # SQLite database files
│   ├── memory.db          # Main database
│   └── schema.sql         # Database schema
├── web/                   # Web interface
│   ├── static/           # CSS, JS, images
│   └── templates/        # HTML templates
└── tests/                # Test suite
```

## API Endpoints

### Authentication
- `GET /auth/login` - Login page
- `POST /auth/token` - Get authentication token
- `GET /auth/tokens` - List active tokens
- `POST /auth/tokens/{name}/revoke` - Revoke token

### Memory Operations
- `POST /memory/store` - Store new memory entry
- `POST /memory/search` - Search memories
- `POST /interaction/store` - Store conversation interaction
- `GET /stats` - Get memory statistics
- `POST /maintenance/archive` - Archive old memories
- `GET /archie/greeting` - Get Archie's greeting

### Storage Operations
- `POST /storage/upload` - Upload files with plugin organization
- `GET /storage/download/{file_id}` - Download files
- `POST /storage/search` - Search files with filters
- `GET /storage/file/{file_id}/info` - Get file metadata
- `DELETE /storage/file/{file_id}` - Delete files
- `POST /storage/file/{file_id}/move` - Move between storage tiers
- `GET /storage/stats` - Storage statistics
- `POST /storage/cleanup` - Clean temporary files
- `GET /storage/plugins` - List plugin storage areas

### System Operations
- `GET /health` - Health check with stats
- `GET /system/info` - System information
- `GET /system/recent-activities` - Recent system activities
- `POST /system/maintenance` - Run maintenance tasks
- `POST /system/shutdown` - Graceful shutdown

### Backup Operations
- `POST /backup/create` - Create full backup
- `POST /backup/create/memory` - Backup memory only
- `POST /backup/create/files` - Backup files only
- `GET /backup/list` - List available backups
- `POST /backup/restore/{backup_id}` - Restore from backup
- `GET /backup/download/{backup_id}` - Download backup
- `DELETE /backup/{backup_id}` - Delete backup

### Web Interface
- `GET /web/archivist` - Main Archivist interface
- `GET /` - Redirects to login

## Database Schema

### Core Tables
- `memory_entries` - Long-term memory storage with full-text search
- `interactions` - Conversation logs between users and assistants
- `patterns` - Detected behavioral patterns and trends
- `insights` - Generated summaries and suggestions
- `assistant_tokens` - Authentication tokens for API access
- `audit_log` - Security and access tracking
- `pruning_history` - Memory pruning history
- `memory_fts` - Full-text search virtual table

### Key Indexes
- Timestamp-based for performance
- Assistant ID for multi-assistant support
- Entry type for categorization
- Archive status for lifecycle management

## Configuration

Environment variables (via `.env` file):
- `ARCHIE_API_PORT` (default: 8090)
- `ARCHIE_DATABASE_PATH` (default: database/memory.db)
- `ARCHIE_PERSONALITY_MODE` (content/excited/focused/concerned)
- `ARCHIE_AUTO_ARCHIVE_DAYS` (default: 90)
- `ARCHIE_LOG_LEVEL` (default: INFO)
- `ARCHIE_SECRET_KEY` (for JWT tokens)
- `ARCHIE_CORS_ORIGINS` (for Percy integration)

## Storage Tiers

| Tier | Purpose | Location | Auto-Migration |
|------|---------|----------|----------------|
| Hot | Active files | `storage/plugins/` | Never |
| Warm | Regular files | `storage/` | After 30 days |
| Cold | Archived files | `storage/cold/` | After 90 days |
| Vault | Secure files | `storage/vault/` | Manual only |

## Development Patterns

### Adding New Endpoints
1. Create endpoint module in `api/endpoints/`
2. Define Pydantic models for request/response
3. Add authentication dependency: `token_name: str = Depends(require_auth("read"))`
4. Include router in `api/main.py`
5. Add Archie personality responses

### Working with Memory Manager
```python
from archie_core.memory_manager import MemoryManager

# Store memory
memory_id = memory_mgr.store_memory(
    content="Memory content",
    entry_type="interaction",
    assistant_id="percy",
    tags=["important", "milestone"]
)

# Search memories
results = memory_mgr.search_memories(
    query="search term",
    limit=50
)
```

### Working with File Manager
```python
from archie_core.file_manager import ArchieFileManager

# Store file
file_metadata = file_mgr.store_file(
    file_content=content,
    original_filename="document.pdf",
    plugin="research",
    tags=["important"]
)

# Search files
results = file_mgr.search_files(
    plugin="research",
    tags=["important"]
)
```

## Security Considerations

- JWT token authentication required for all API endpoints
- Tokens stored with bcrypt hashing
- Audit logging for all operations
- CORS configured for Percy integration only
- File uploads validated for size and type
- SQL injection prevention via parameterized queries

## Testing Strategy

- Unit tests for core managers (memory, storage, file)
- Integration tests for API endpoints
- Test database created in memory for isolation
- Mock file system for storage tests
- Run `pytest tests/` for full test suite

## Deployment

### Raspberry Pi Deployment
```bash
# Use deployment script
cd deployment/
./install_pi.sh

# Or manual systemd service
sudo cp deployment/archie.service /etc/systemd/system/
sudo systemctl enable archie
sudo systemctl start archie
```

### External Drive Setup
```bash
./deployment/setup_external_drive.sh /dev/sda1
```

## Common Tasks

### Check System Health
```bash
curl http://localhost:8090/health
```

### Create Full Backup
```bash
curl -X POST http://localhost:8090/backup/create \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Search Memories
```bash
curl -X POST http://localhost:8090/memory/search \
  -H "Content-Type: application/json" \
  -d '{"query": "important milestone", "limit": 10}'
```

### Upload File to Plugin Storage
```bash
curl -X POST http://localhost:8090/storage/upload \
  -F "file=@document.pdf" \
  -F "plugin=research" \
  -F "tags=important,project"
```

## Integration with Percy

ArchieOS is designed as Percy's memory and storage backend:
1. Percy sends memories via `/memory/store` endpoint
2. Percy queries memories via `/memory/search` 
3. Percy uploads files via `/storage/upload` with plugin parameter
4. Authentication via JWT tokens
5. CORS configured for Percy's ports (3000, 8080)

## Archie's Personality

Archie responds with character-appropriate messages:
- Enthusiastic about organization and patterns
- Slightly nerdy references to archival methods
- Warm and helpful tone
- Gets excited about discovering patterns

Example personality modes:
- `content`: Default balanced responses
- `excited`: Extra enthusiastic about discoveries
- `focused`: More technical and precise
- `concerned`: Worried about data integrity