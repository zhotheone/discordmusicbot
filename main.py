import asyncio
import logging
import os
from typing import Optional

import discord
from discord.ext import commands

from config.settings import Settings
from config.database import DatabaseManager
from core.bot import MusicBot
from core.dependency_injection import DIContainer
from infrastructure.cache.redis_cache import RedisCache
from infrastructure.cache.memory_cache import MemoryCache
from utils.exceptions import BotInitializationError


async def setup_logging() -> None:
    """Configure logging for the application."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('bot.log'),
            logging.StreamHandler()
        ]
    )


async def create_bot() -> MusicBot:
    """Create and configure the bot instance."""
    try:
        # Load configuration
        settings = Settings()
        
        # Setup dependency injection container
        container = DIContainer()
        
        # Setup database
        db_manager = DatabaseManager(settings.database_url)
        await db_manager.initialize()
        container.register(DatabaseManager, db_manager)
        
        # Setup cache
        if settings.redis_url:
            cache = RedisCache(settings.redis_url)
            await cache.connect()
        else:
            cache = MemoryCache()
            
        container.register("Cache", cache)
        
        # Create bot with intents
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        intents.guilds = True
        
        # Initialize bot
        bot = MusicBot(
            command_prefix=settings.command_prefix,
            intents=intents,
            container=container,
            settings=settings
        )
        
        return bot
        
    except Exception as e:
        logging.error(f"Failed to create bot: {e}")
        raise BotInitializationError(f"Bot initialization failed: {e}")


async def main() -> None:
    """Main application entry point."""
    try:
        # Setup logging
        await setup_logging()
        logging.info("Starting Discord Music Bot...")
        
        # Create bot instance
        bot = await create_bot()
        
        # Start the bot
        token = os.getenv("DISCORD_TOKEN")
        if not token:
            raise ValueError("DISCORD_TOKEN environment variable is required")
            
        await bot.start(token)
        
    except KeyboardInterrupt:
        logging.info("Shutting down bot...")
    except Exception as e:
        logging.error(f"Critical error: {e}")
        raise
    finally:
        # Cleanup resources
        if 'bot' in locals():
            await bot.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot stopped by user")
    except Exception as e:
        print(f"Fatal error: {e}")
        exit(1)