"""Discord Music Bot - Main Entry Point."""
import asyncio
import logging
import os
from logging.handlers import RotatingFileHandler

import discord
from discord.ext import commands
from dotenv import load_dotenv

# A list of cogs to load at startup
COGS_TO_LOAD = [
    "cogs.playback_cog",
    "cogs.effects_cog",
    "cogs.advanced_effects_cog"
]

def setup_logging():
    """Configure logging for console and file output."""
    log = logging.getLogger()
    log.setLevel(logging.INFO)
    formatter = logging.Formatter(
        '[{asctime}] [{levelname:<8}] {name}: {message}',
        datefmt='%Y-%m-%d %H:%M:%S',
        style='{'
    )
    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    log.addHandler(console_handler)
    # File Handler
    file_handler = RotatingFileHandler(
        'discord_bot.log',
        maxBytes=5 * 1024 * 1024,
        backupCount=2,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    log.addHandler(file_handler)
    logging.info("Logging configured successfully.")

async def main():
    """Main function to initialize and run the Discord bot."""
    setup_logging()
    load_dotenv()
    TOKEN = os.getenv('DISCORD_TOKEN')

    if not TOKEN:
        logging.critical(
            "CRITICAL: DISCORD_TOKEN not found in .env file. "
            "Bot cannot start."
        )
        return

    intents = discord.Intents.default()
    intents.message_content = True
    intents.voice_states = True
    bot = commands.Bot(command_prefix="/", intents=intents)

    @bot.event
    async def on_ready():
        """Event handler for when the bot is ready."""
        logging.info(f"Logged in as {bot.user.name}")
        logging.info("Syncing commands to all guilds...")
        for guild in bot.guilds:
            try:
                bot.tree.copy_global_to(guild=guild)
                await bot.tree.sync(guild=guild)
            except Exception as e:
                logging.error(f"Failed to sync for guild {guild.name}: {e}")
        logging.info("Bot is ready to rock!")

    # Load cogs from our list
    for cog in COGS_TO_LOAD:
        try:
            await bot.load_extension(cog)
            logging.info(f"Successfully loaded cog: {cog}")
        except Exception:
            logging.exception(f"Failed to load cog {cog}")

    await bot.start(TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot shutting down by request.")
