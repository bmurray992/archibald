#!/usr/bin/env python3
"""
Archie Runner - Simple script to start Archie with proper configuration
"""
import sys
import logging
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import get_settings
from api.main import app
import uvicorn

def setup_logging():
    """Configure logging based on settings"""
    settings = get_settings()
    
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        filename=settings.log_file if settings.log_file else None
    )
    
    # Also log to console if we're writing to a file
    if settings.log_file:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(console_formatter)
        logging.getLogger().addHandler(console_handler)

def main():
    """Main entry point for Archie"""
    print("🧠 Starting Archie - Memory Archivist...")
    
    setup_logging()
    settings = get_settings()
    
    print(f"📡 API will be available at http://{settings.api_host}:{settings.api_port}")
    print(f"🎭 Personality mode: {settings.personality_mode}")
    print(f"📚 Database path: {settings.database_path or 'default (database/memory.db)'}")
    
    try:
        uvicorn.run(
            app,
            host=settings.api_host,
            port=settings.api_port,
            log_level=settings.log_level.lower(),
            access_log=True
        )
    except KeyboardInterrupt:
        print("\n🏁 Archie shutting down gracefully...")
    except Exception as e:
        print(f"❌ Failed to start Archie: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()