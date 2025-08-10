#!/bin/bash

# Activate virtual environment and run Archie with auto-reload
echo "🚀 Starting Archie Memory Vault in development mode..."
echo "📍 URL: http://localhost:8090"
echo "🔑 Login: admin / admin"
echo ""

# Activate virtual environment
source .venv/bin/activate

# Start server with auto-reload
uvicorn api.main:app --host 0.0.0.0 --port 8090 --reload