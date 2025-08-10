-- Archie's Memory Database Schema
-- Long-term memory storage for AI assistants

-- Main memory entries table
CREATE TABLE IF NOT EXISTS memory_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assistant_id TEXT NOT NULL DEFAULT 'percy',
    plugin_source TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    entry_type TEXT NOT NULL,  -- 'interaction', 'reminder', 'calendar', 'journal', etc.
    content TEXT NOT NULL,
    metadata JSON,
    tags TEXT,  -- Comma-separated tags
    confidence REAL DEFAULT 1.0,
    source_method TEXT,  -- 'voice', 'ui', 'automation'
    archived BOOLEAN DEFAULT FALSE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- User interactions with assistants
CREATE TABLE IF NOT EXISTS interactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assistant_id TEXT NOT NULL DEFAULT 'percy',
    user_message TEXT,
    assistant_response TEXT,
    context TEXT,  -- Additional context data
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    session_id TEXT,
    plugin_used TEXT,
    intent_detected TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Detected patterns and insights
CREATE TABLE IF NOT EXISTS patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern_type TEXT NOT NULL,  -- 'habit', 'trend', 'anomaly', 'correlation'
    description TEXT NOT NULL,
    confidence REAL DEFAULT 1.0,
    frequency TEXT,  -- 'daily', 'weekly', 'monthly'
    data_points INTEGER DEFAULT 1,
    first_detected DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_confirmed DATETIME DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'active',  -- 'active', 'inactive', 'archived'
    metadata JSON,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Generated insights and summaries
CREATE TABLE IF NOT EXISTS insights (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    insight_type TEXT NOT NULL,  -- 'weekly_summary', 'monthly_report', 'suggestion'
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    related_patterns TEXT,  -- Comma-separated pattern IDs
    generated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    relevance_score REAL DEFAULT 1.0,
    read_status BOOLEAN DEFAULT FALSE,
    archived BOOLEAN DEFAULT FALSE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Authentication tokens for assistants
CREATE TABLE IF NOT EXISTS assistant_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assistant_id TEXT NOT NULL UNIQUE,
    token_hash TEXT NOT NULL,
    permissions TEXT NOT NULL DEFAULT 'read,write',  -- Comma-separated permissions
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME,
    last_used DATETIME,
    active BOOLEAN DEFAULT TRUE
);

-- Audit log for security and access tracking
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assistant_id TEXT,
    action TEXT NOT NULL,  -- 'read', 'write', 'delete', 'query', 'auth'
    resource TEXT,  -- Table/endpoint accessed
    ip_address TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    status TEXT NOT NULL,  -- 'success', 'failure', 'blocked'
    details TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Memory pruning rules and history
CREATE TABLE IF NOT EXISTS pruning_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_type TEXT NOT NULL,  -- 'redundancy', 'age', 'relevance'
    entries_affected INTEGER DEFAULT 0,
    bytes_freed INTEGER DEFAULT 0,
    executed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    details TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_memory_timestamp ON memory_entries(timestamp);
CREATE INDEX IF NOT EXISTS idx_memory_assistant ON memory_entries(assistant_id);
CREATE INDEX IF NOT EXISTS idx_memory_type ON memory_entries(entry_type);
CREATE INDEX IF NOT EXISTS idx_memory_archived ON memory_entries(archived);
CREATE INDEX IF NOT EXISTS idx_interactions_timestamp ON interactions(timestamp);
CREATE INDEX IF NOT EXISTS idx_interactions_assistant ON interactions(assistant_id);
CREATE INDEX IF NOT EXISTS idx_patterns_type ON patterns(pattern_type);
CREATE INDEX IF NOT EXISTS idx_patterns_status ON patterns(status);
CREATE INDEX IF NOT EXISTS idx_insights_type ON insights(insight_type);
CREATE INDEX IF NOT EXISTS idx_insights_archived ON insights(archived);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_assistant ON audit_log(assistant_id);

-- Full-text search virtual table for memory content
CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
    content,
    tags,
    content='memory_entries',
    content_rowid='id'
);

-- Triggers to keep FTS table in sync
CREATE TRIGGER IF NOT EXISTS memory_fts_insert AFTER INSERT ON memory_entries
BEGIN
    INSERT INTO memory_fts(rowid, content, tags) VALUES (NEW.id, NEW.content, NEW.tags);
END;

CREATE TRIGGER IF NOT EXISTS memory_fts_delete AFTER DELETE ON memory_entries
BEGIN
    DELETE FROM memory_fts WHERE rowid = OLD.id;
END;

CREATE TRIGGER IF NOT EXISTS memory_fts_update AFTER UPDATE ON memory_entries
BEGIN
    DELETE FROM memory_fts WHERE rowid = OLD.id;
    INSERT INTO memory_fts(rowid, content, tags) VALUES (NEW.id, NEW.content, NEW.tags);
END;

-- Update timestamp triggers
CREATE TRIGGER IF NOT EXISTS update_memory_timestamp AFTER UPDATE ON memory_entries
BEGIN
    UPDATE memory_entries SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;