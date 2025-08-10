# 🧠💾 ArchieOS - Intelligent Storage Operating System

ArchieOS is a complete intelligent storage and memory management system running on Raspberry Pi. More than just a memory backend, ArchieOS is a **modular, plugin-aware mini operating system** that provides intelligent file storage, long-term memory archival, and seamless integration with Percy and other AI assistants.

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- SQLite 3

### Installation

1. **Clone and setup:**
```bash
cd archie/
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

2. **Configure (optional):**
```bash
cp .env.example .env
# Edit .env with your settings
```

3. **Test the core functionality:**
```bash
python test_archie.py
```

4. **Run ArchieOS:**
```bash
python run_archie.py
# or
python -m api.main
```

## 📡 API Endpoints

### Core Memory Operations
- `GET /` - Welcome and status
- `GET /health` - Health check with stats
- `POST /memory/store` - Store new memory entry
- `POST /memory/search` - Search memories
- `POST /interaction/store` - Store conversation interaction
- `GET /stats` - Get memory statistics
- `POST /maintenance/archive` - Archive old memories
- `GET /archie/greeting` - Get Archie's greeting

### 💾 ArchieOS Storage Operations
- `POST /storage/upload` - Upload files with plugin organization
- `GET /storage/download/{file_id}` - Download files by ID
- `POST /storage/search` - Search files with filters
- `GET /storage/file/{file_id}/info` - Get file metadata
- `DELETE /storage/file/{file_id}` - Delete files
- `POST /storage/file/{file_id}/move` - Move files between storage tiers
- `GET /storage/stats` - Storage system statistics
- `POST /storage/cleanup` - Clean temporary files
- `GET /storage/plugins` - List plugin storage areas

### Example Usage

**Store a memory:**
```bash
curl -X POST "http://localhost:8090/memory/store" \
     -H "Content-Type: application/json" \
     -d '{
       "content": "User completed setup of Archie system",
       "entry_type": "milestone",
       "tags": ["setup", "achievement"],
       "metadata": {"importance": "high"}
     }'
```

**Search memories:**
```bash
curl -X POST "http://localhost:8090/memory/search" \
     -H "Content-Type: application/json" \
     -d '{
       "query": "setup",
       "limit": 10
     }'
```

**Upload a file:**
```bash
curl -X POST "http://localhost:8090/storage/upload" \
     -F "file=@document.pdf" \
     -F "plugin=research" \
     -F "tags=important,project" \
     -F "category=data"
```

**Search files:**
```bash
curl -X POST "http://localhost:8090/storage/search" \
     -H "Content-Type: application/json" \
     -d '{
       "plugin": "calendar",
       "tags": ["meeting"],
       "limit": 20
     }'
```

## 🏗️ ArchieOS Architecture

```
archie/
├── archie_core/          # Core ArchieOS modules
│   ├── memory_manager.py # Long-term memory operations
│   ├── storage_manager.py # File system management
│   ├── personality.py    # Archie's voice and character
│   └── pattern_detector.py # Pattern recognition (future)
├── api/                  # FastAPI application
│   ├── main.py          # Main ArchieOS server
│   └── endpoints/       # API endpoint modules
│       └── storage.py   # File storage operations
├── storage/             # ArchieOS file system
│   ├── plugins/         # Plugin-specific storage
│   │   ├── calendar/    # Calendar plugin files
│   │   ├── reminders/   # Reminders plugin files
│   │   ├── health/      # Health plugin files
│   │   └── ...          # Other plugin folders
│   ├── media/           # General media storage
│   ├── vault/           # Encrypted sensitive files
│   ├── cold/            # Archived files
│   └── exports/         # Export and backup files
├── database/            # SQLite database and schema
├── config/              # Configuration management
└── deployment/          # Production deployment scripts
```

## 💾 ArchieOS Storage Tiers

| Tier | Purpose | Location | Description |
|------|---------|----------|-------------|
| **Hot** | Active files | `storage/plugins/` | Frequently accessed files |
| **Warm** | Regular files | `storage/` | Occasionally accessed files |
| **Cold** | Archived files | `storage/cold/` | Rarely accessed, compressed |
| **Vault** | Secure files | `storage/vault/` | Encrypted sensitive data |

## 🌟 ArchieOS Features

### 🗂️ **Intelligent File Management**
- **Plugin-Aware Storage**: Automatic organization by Percy's plugins
- **Smart Metadata**: Automatic file type detection and tagging
- **Multi-Tier Storage**: Hot, warm, cold, and vault storage tiers
- **Advanced Search**: Find files by content, tags, plugin, or date
- **Access Tracking**: Monitor file usage and access patterns

### 🧠 **Memory Integration**
- **Dual Storage**: Both files and memory entries in one system
- **Cross-Referencing**: Link files to memory entries automatically
- **Pattern Detection**: AI-powered insights across files and memories
- **Unified Search**: Search both files and memories simultaneously

### 🔒 **Security & Privacy**
- **Tiered Access**: Different security levels for different data types
- **Audit Logging**: Complete access and modification tracking
- **Encrypted Vaults**: Secure storage for sensitive documents
- **Local-First**: All data stays on your Raspberry Pi

### 🎭 **Archie's Personality**

Archie brings character to your storage system:
- **Diligent & Precise**: Methodical approach to data management
- **Enthusiastic**: Gets excited about patterns and organization
- **Friendly**: Warm, helpful responses with light humor
- **Slightly Nerdy**: References to data structures and archival methods

Example responses:
- "Archiving that for posterity!"
- "Oho! A fascinating pattern has emerged!"
- "The filing system is now even tidier!"

## 🔧 Configuration

Archie can be configured via environment variables or `.env` file:

| Setting | Default | Description |
|---------|---------|-------------|
| `ARCHIE_API_PORT` | 8090 | API server port |
| `ARCHIE_DATABASE_PATH` | `database/memory.db` | SQLite database path |
| `ARCHIE_PERSONALITY_MODE` | content | Personality mode (excited/content/focused/concerned) |
| `ARCHIE_AUTO_ARCHIVE_DAYS` | 90 | Days before auto-archiving memories |
| `ARCHIE_LOG_LEVEL` | INFO | Logging level |

See `.env.example` for full configuration options.

## 🔒 Security Features

- Audit logging for all operations
- Token-based authentication (planned)
- Database encryption support (planned)
- Access control and rate limiting (planned)

## 🧪 Testing

```bash
# Test core memory functionality
python test_archie.py

# Test ArchieOS storage system
python test_archie_os.py

# Test API startup components
python test_api_startup.py

# Future: Run full test suite
pytest tests/
```

## 📊 Database Schema

Archie uses SQLite with the following main tables:
- `memory_entries` - Core memory storage with FTS
- `interactions` - Conversation logs
- `patterns` - Detected behavioral patterns
- `insights` - Generated summaries and suggestions
- `audit_log` - Security and access tracking

## 🚀 Deployment

### Development (Mac to Raspberry Pi)
```bash
# On Mac: Push changes
git add . && git commit -m "Update Archie" && git push

# On Raspberry Pi: Pull and restart
git pull
source .venv/bin/activate
python -m api.main
```

### Production Service (systemd)
```bash
# Copy service file
sudo cp deployment/archie.service /etc/systemd/system/
sudo systemctl enable archie
sudo systemctl start archie
```

## 🤝 Integration with Percy

Archie is designed to work seamlessly with Percy:
- Percy sends memory entries via API calls
- Archie provides search and retrieval services
- Pattern detection informs Percy's suggestions
- Secure token-based communication

## 📈 Future Features

- [ ] Advanced pattern detection and ML insights
- [ ] Memory visualization and graph relationships  
- [ ] Voice interface for direct Archie interaction
- [ ] Multi-assistant support and memory namespacing
- [ ] Distributed storage and backup systems
- [ ] Memory export and import functionality

## 🐛 Troubleshooting

**Database locked error:**
- Ensure no other Archie instances are running
- Check file permissions on database directory

**API connection issues:**
- Verify port 8090 is available
- Check firewall settings for local network access

**Memory search not working:**
- Ensure FTS (Full-Text Search) is enabled
- Check database integrity with `PRAGMA integrity_check`

## 📝 License

Copyright (c) 2024 - Archie Memory Archivist Project

---

*"A memory unprotected is a truth unguarded — and that is unacceptable."* - Archie's motto