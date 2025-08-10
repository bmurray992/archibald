# 🧠💾 ArchieOS Command Reference

A comprehensive guide to ArchieOS API commands and capabilities.

## 🚀 Quick Start Commands

### Check ArchieOS Status
```bash
curl http://localhost:8090/
curl http://localhost:8090/health
```

### View Storage Statistics
```bash
curl http://localhost:8090/storage/stats
```

---

## 📁 File Storage Commands

### Upload Files

**Basic Upload:**
```bash
curl -X POST "http://localhost:8090/storage/upload" \
     -F "file=@document.pdf" \
     -F "plugin=research"
```

**Advanced Upload with Metadata:**
```bash
curl -X POST "http://localhost:8090/storage/upload" \
     -F "file=@meeting_notes.md" \
     -F "plugin=calendar" \
     -F "category=data" \
     -F "tags=meeting,important,Q4" \
     -F "tier=hot" \
     -F 'metadata={"project": "Q4_planning", "attendees": 5}'
```

**Upload to Different Storage Tiers:**
```bash
# Hot storage (default)
curl -X POST "http://localhost:8090/storage/upload" \
     -F "file=@active_project.docx" \
     -F "tier=hot"

# Cold storage for archival
curl -X POST "http://localhost:8090/storage/upload" \
     -F "file=@old_report.pdf" \
     -F "tier=cold"

# Vault for sensitive data
curl -X POST "http://localhost:8090/storage/upload" \
     -F "file=@financial_data.xlsx" \
     -F "tier=vault" \
     -F "plugin=finance"
```

### Download Files

**Download by File ID:**
```bash
curl "http://localhost:8090/storage/download/abc123-def456" \
     --output downloaded_file.pdf
```

### File Information

**Get File Metadata:**
```bash
curl "http://localhost:8090/storage/file/abc123-def456/info"
```

### File Management

**Delete Files:**
```bash
curl -X DELETE "http://localhost:8090/storage/file/abc123-def456"
```

**Move Files Between Tiers:**
```bash
# Move to cold storage
curl -X POST "http://localhost:8090/storage/file/abc123-def456/move?target_tier=cold"

# Move to vault
curl -X POST "http://localhost:8090/storage/file/abc123-def456/move?target_tier=vault"
```

---

## 🔍 Search Commands

### Search Files

**Basic Text Search:**
```bash
curl -X POST "http://localhost:8090/storage/search" \
     -H "Content-Type: application/json" \
     -d '{"query": "meeting notes"}'
```

**Search by Plugin:**
```bash
curl -X POST "http://localhost:8090/storage/search" \
     -H "Content-Type: application/json" \
     -d '{"plugin": "calendar", "limit": 20}'
```

**Search by Tags:**
```bash
curl -X POST "http://localhost:8090/storage/search" \
     -H "Content-Type: application/json" \
     -d '{"tags": ["important", "Q4"], "limit": 10}'
```

**Search by File Type:**
```bash
curl -X POST "http://localhost:8090/storage/search" \
     -H "Content-Type: application/json" \
     -d '{"mime_type": "application/pdf"}'
```

**Search by Date Range:**
```bash
curl -X POST "http://localhost:8090/storage/search" \
     -H "Content-Type: application/json" \
     -d '{
       "date_from": "2024-01-01T00:00:00",
       "date_to": "2024-12-31T23:59:59",
       "limit": 50
     }'
```

**Advanced Combined Search:**
```bash
curl -X POST "http://localhost:8090/storage/search" \
     -H "Content-Type: application/json" \
     -d '{
       "query": "project planning",
       "plugin": "tasks",
       "tags": ["urgent"],
       "mime_type": "text",
       "tier": "hot",
       "limit": 25
     }'
```

---

## 🗂️ Plugin Storage Commands

### List Available Plugins
```bash
curl "http://localhost:8090/storage/plugins"
```

### Plugin-Specific Operations

**Upload to Specific Plugin:**
```bash
# Calendar plugin
curl -X POST "http://localhost:8090/storage/upload" \
     -F "file=@calendar_export.ics" \
     -F "plugin=calendar" \
     -F "category=exports"

# Health plugin
curl -X POST "http://localhost:8090/storage/upload" \
     -F "file=@health_data.json" \
     -F "plugin=health" \
     -F "category=backups"

# Finance plugin
curl -X POST "http://localhost:8090/storage/upload" \
     -F "file=@budget_2024.xlsx" \
     -F "plugin=finance" \
     -F "category=data" \
     -F "tier=vault"
```

---

## 🧠 Memory Commands

### Store Memories
```bash
curl -X POST "http://localhost:8090/memory/store" \
     -H "Content-Type: application/json" \
     -d '{
       "content": "User uploaded important project files to ArchieOS",
       "entry_type": "file_activity",
       "tags": ["upload", "project", "files"],
       "metadata": {"file_count": 3}
     }'
```

### Search Memories
```bash
curl -X POST "http://localhost:8090/memory/search" \
     -H "Content-Type: application/json" \
     -d '{
       "query": "project files",
       "entry_type": "file_activity",
       "limit": 10
     }'
```

---

## 🧹 Maintenance Commands

### Storage Cleanup

**Clean Temporary Files:**
```bash
# Clean files older than 1 day (default)
curl -X POST "http://localhost:8090/storage/cleanup"

# Clean files older than 7 days
curl -X POST "http://localhost:8090/storage/cleanup?older_than_days=7"
```

**Archive Old Memories:**
```bash
# Archive memories older than 90 days (default)
curl -X POST "http://localhost:8090/maintenance/archive"

# Archive memories older than 30 days
curl -X POST "http://localhost:8090/maintenance/archive?days_old=30"
```

### System Statistics

**Memory Statistics:**
```bash
curl "http://localhost:8090/stats"
```

**Storage Statistics:**
```bash
curl "http://localhost:8090/storage/stats"
```

**Combined System Health:**
```bash
curl "http://localhost:8090/health"
```

---

## 🎭 Archie Interaction Commands

### Get Archie's Greeting
```bash
curl "http://localhost:8090/archie/greeting"
```

### Interactive Commands (via API responses)

All ArchieOS commands return responses with Archie's personality:

```json
{
  "success": true,
  "message": "File uploaded successfully",
  "data": {...},
  "archie_says": "Archiving that for posterity! That document.pdf is now perfectly organized in the research archives!"
}
```

---

## 📊 Advanced Usage Patterns

### Batch File Operations

**Upload Multiple Files:**
```bash
# Upload a series of files
for file in *.pdf; do
  curl -X POST "http://localhost:8090/storage/upload" \
       -F "file=@$file" \
       -F "plugin=research" \
       -F "tags=batch_upload,documents"
done
```

### Automated Workflows

**Daily Backup Script:**
```bash
#!/bin/bash
# Daily backup routine

# Clean temp files
curl -X POST "http://localhost:8090/storage/cleanup?older_than_days=1"

# Archive old memories
curl -X POST "http://localhost:8090/maintenance/archive?days_old=90"

# Get system stats
curl "http://localhost:8090/health"
```

### Integration with Percy

**Store Percy Plugin Data:**
```bash
# Example: Backup calendar data from Percy
curl -X POST "http://localhost:8090/storage/upload" \
     -F "file=@percy_calendar_backup.json" \
     -F "plugin=calendar" \
     -F "category=backups" \
     -F "tags=percy,automated,daily" \
     -F 'metadata={"source": "percy", "backup_date": "2024-08-05"}'
```

---

## 🔧 Configuration Commands

### Environment Variables

```bash
# Set ArchieOS configuration
export ARCHIE_API_PORT=8090
export ARCHIE_PERSONALITY_MODE=excited
export ARCHIE_AUTO_ARCHIVE_DAYS=60

# Run ArchieOS with custom config
python run_archie.py
```

---

## 🚨 Error Handling

All ArchieOS commands return structured responses:

**Success Response:**
```json
{
  "success": true,
  "message": "Operation completed",
  "data": {...},
  "archie_says": "Perfectly executed!"
}
```

**Error Response:**
```json
{
  "success": false,
  "message": "Operation failed: File not found",
  "archie_says": "Oh dear! I couldn't locate that file in the archives."
}
```

---

## 📈 Future Commands (Planned)

These commands will be available in future ArchieOS versions:

```bash
# Pattern detection
curl "http://localhost:8090/patterns/analyze"

# Voice interface
curl -X POST "http://localhost:8090/voice/query" -F "audio=@question.wav"

# Web desktop
open "http://localhost:8090/archivist"

# Backup to cloud
curl -X POST "http://localhost:8090/backup/cloud"
```

---

*"Every file deserves a proper home, and every command deserves a thoughtful response!"* - Archie's command philosophy