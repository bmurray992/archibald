#!/usr/bin/env python3
import sys
import os
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

# Set default environment variables if not present
os.environ.setdefault('ARCHIE_API_PORT', '8090')
os.environ.setdefault('ARCHIE_DATABASE_PATH', 'database/memory.db')

# Import uvicorn and app at top level
import uvicorn
from api.main import app

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get('ARCHIE_API_PORT', 8090)))