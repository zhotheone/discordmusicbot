#!/usr/bin/env python3
"""
Setup script for Discord Music Bot
"""

import asyncio
import os
import shutil
import sys
from pathlib import Path


async def main():
    """Main setup function."""
    print("🎵 Discord Music Bot Setup")
    print("=" * 40)
    
    # Check Python version
    if sys.version_info < (3, 9):
        print("❌ Python 3.9+ is required")
        sys.exit(1)
    
    print("✅ Python version check passed")
    
    # Create .env file if it doesn't exist
    if not os.path.exists('.env'):
        if os.path.exists('.env.example'):
            shutil.copy('.env.example', '.env')
            print("✅ Created .env file from example")
            print("⚠️  Please edit .env file with your configuration")
        else:
            print("❌ .env.example not found")
    else:
        print("✅ .env file already exists")
    
    # Install dependencies
    print("\n📦 Installing dependencies...")
    os.system("pip install -r requirements.txt")
    
    # Initialize database
    print("\n🗄️  Setting up database...")
    try:
        # Import here to avoid import errors during setup
        from config.database import DatabaseManager
        from config.settings import Settings
        
        settings = Settings()
        db_manager = DatabaseManager(settings.database_url)
        await db_manager.initialize()
        print("✅ Database initialized successfully")
        await db_manager.close()
        
    except Exception as e:
        print(f"❌ Database setup failed: {e}")
        print("Make sure your DATABASE_URL is configured correctly in .env")
    
    print("\n🎉 Setup complete!")
    print("\nNext steps:")
    print("1. Edit .env file with your Discord bot token and other settings")
    print("2. Run the bot: python main.py")
    print("\nFor more information, check the Architecture.md file")


if __name__ == "__main__":
    asyncio.run(main())