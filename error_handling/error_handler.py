"""Centralized error handling system for the Discord bot."""

import logging
import traceback
import asyncio
from functools import wraps
from typing import Any, Callable, Optional, Union
import sys

import discord
from discord.ext import commands

from .exceptions import (
    BotBaseException,
    CriticalBotException,
    ServiceException,
    VoiceException,
    PermissionException,
    RateLimitException,
    UserInputException
)

log = logging.getLogger(__name__)


class ErrorHandler:
    """Centralized error handler for the bot."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.error_count = 0
        self.critical_error_count = 0
        self.max_critical_errors = 5  # Bot will attempt graceful shutdown after this many critical errors
        
    async def log_error(self, error: Exception, context: Optional[str] = None, **kwargs):
        """Log an error with appropriate level and context."""
        self.error_count += 1
        
        if isinstance(error, BotBaseException):
            if error.severity == "CRITICAL":
                self.critical_error_count += 1
                log.critical(f"Critical error #{self.critical_error_count}: {error.message}")
                if context:
                    log.critical(f"Context: {context}")
                log.critical(f"Stack trace: {traceback.format_exc()}")
                
                # Check if we've hit the critical error threshold
                if self.critical_error_count >= self.max_critical_errors:
                    log.critical(f"Maximum critical errors ({self.max_critical_errors}) reached. Initiating graceful shutdown.")
                    await self._graceful_shutdown()
                    
            elif error.severity == "ERROR":
                log.error(f"Error: {error.message}")
                if context:
                    log.error(f"Context: {context}")
                    
            elif error.severity == "WARNING":
                log.warning(f"Warning: {error.message}")
                if context:
                    log.warning(f"Context: {context}")
                    
            else:  # INFO
                log.info(f"Info: {error.message}")
                if context:
                    log.info(f"Context: {context}")
        else:
            # Handle non-custom exceptions
            log.error(f"Unhandled exception: {str(error)}")
            if context:
                log.error(f"Context: {context}")
            log.error(f"Stack trace: {traceback.format_exc()}")
    
    async def _graceful_shutdown(self):
        """Attempt a graceful shutdown when too many critical errors occur."""
        try:
            log.critical("Attempting graceful shutdown...")
            
            # Disconnect from all voice channels
            for voice_client in self.bot.voice_clients:
                try:
                    await voice_client.disconnect(force=True)
                except Exception as e:
                    log.error(f"Error disconnecting from voice channel: {e}")
            
            # Close the bot connection
            await self.bot.close()
            
        except Exception as e:
            log.critical(f"Error during graceful shutdown: {e}")
            # Force exit if graceful shutdown fails
            sys.exit(1)
    
    async def handle_interaction_error(self, interaction: discord.Interaction, error: Exception):
        """Handle errors that occur during interaction responses."""
        await self.log_error(error, f"Interaction: {interaction.command.name if interaction.command else 'Unknown'}")
        
        # Create appropriate user response
        if isinstance(error, BotBaseException):
            embed = error.get_embed()
        else:
            # Handle standard Discord.py errors
            embed = self._handle_standard_error(error)
        
        try:
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)
        except discord.HTTPException as e:
            log.error(f"Failed to send error message to user: {e}")
    
    async def handle_command_error(self, ctx: commands.Context, error: Exception):
        """Handle errors that occur during command execution."""
        await self.log_error(error, f"Command: {ctx.command.name if ctx.command else 'Unknown'}")
        
        if isinstance(error, BotBaseException):
            embed = error.get_embed()
        else:
            embed = self._handle_standard_error(error)
        
        try:
            await ctx.send(embed=embed)
        except discord.HTTPException as e:
            log.error(f"Failed to send error message to user: {e}")
    
    def _handle_standard_error(self, error: Exception) -> discord.Embed:
        """Convert standard exceptions to user-friendly embeds."""
        match error:
            case commands.CommandNotFound():
                return discord.Embed(
                    title="Command Not Found",
                    description="That command doesn't exist. Use `/help` to see available commands.",
                    color=discord.Color.orange()
                )
            
            case commands.MissingPermissions():
                return discord.Embed(
                    title="Missing Permissions",
                    description="You don't have permission to use this command.",
                    color=discord.Color.red()
                )
            
            case commands.BotMissingPermissions():
                missing_perms = ", ".join(error.missing_permissions)
                return discord.Embed(
                    title="Bot Missing Permissions",
                    description=f"I need the following permissions: {missing_perms}",
                    color=discord.Color.red()
                )
            
            case commands.CommandOnCooldown():
                return discord.Embed(
                    title="Command On Cooldown",
                    description=f"Please wait {error.retry_after:.1f} seconds before using this command again.",
                    color=discord.Color.orange()
                )
            
            case discord.Forbidden():
                return discord.Embed(
                    title="Access Denied",
                    description="I don't have permission to perform this action.",
                    color=discord.Color.red()
                )
            
            case discord.NotFound():
                return discord.Embed(
                    title="Not Found",
                    description="The requested resource was not found.",
                    color=discord.Color.orange()
                )
            
            case discord.HTTPException():
                return discord.Embed(
                    title="Discord API Error",
                    description="An error occurred while communicating with Discord. Please try again.",
                    color=discord.Color.red()
                )
            
            case _:
                return discord.Embed(
                    title="Unexpected Error",
                    description="An unexpected error occurred. Please try again later.",
                    color=discord.Color.red()
                )


def handle_errors(fallback_message: str = "An error occurred while executing this function."):
    """
    Decorator to handle errors in async functions.
    
    Args:
        fallback_message: Message to log if error handling fails
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except BotBaseException as e:
                # Custom exceptions are already properly formatted
                log.error(f"Bot exception in {func.__name__}: {e.message}")
                raise
            except Exception as e:
                # Convert unknown exceptions to BotBaseException
                log.exception(f"Unhandled exception in {func.__name__}: {str(e)}")
                raise BotBaseException(
                    message=f"Error in {func.__name__}: {str(e)}",
                    user_message=fallback_message
                )
        return wrapper
    return decorator


def setup_bot_error_handlers(bot: commands.Bot) -> ErrorHandler:
    """Set up global error handlers for the bot."""
    error_handler = ErrorHandler(bot)
    
    @bot.event
    async def on_command_error(ctx: commands.Context, error: commands.CommandError):
        """Global command error handler."""
        # Ignore if the command has its own error handler
        if hasattr(ctx.command, 'on_error'):
            return
        
        await error_handler.handle_command_error(ctx, error)
    
    @bot.tree.error
    async def on_app_command_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
        """Global application command error handler."""
        await error_handler.handle_interaction_error(interaction, error)
    
    @bot.event
    async def on_error(event: str, *args, **kwargs):
        """Global event error handler."""
        exc_type, exc_value, exc_traceback = sys.exc_info()
        if exc_value:
            await error_handler.log_error(
                exc_value, 
                f"Event: {event}",
                args=args,
                kwargs=kwargs
            )
    
    # Voice client error handling
    async def voice_client_error_handler(error: Exception):
        """Handle voice client errors."""
        await error_handler.log_error(
            VoiceException(f"Voice client error: {str(error)}")
        )
    
    # Add voice error handler to existing voice clients
    for voice_client in bot.voice_clients:
        voice_client.source = discord.PCMVolumeTransformer(
            voice_client.source,
            after=voice_client_error_handler
        )
    
    log.info("Global error handlers set up successfully")
    return error_handler


# Utility functions for specific error types
def raise_if_not_in_voice(interaction: discord.Interaction):
    """Raise VoiceException if user is not in a voice channel."""
    if not interaction.user.voice or not interaction.user.voice.channel:
        raise VoiceException(
            "User not in voice channel",
            "You need to be in a voice channel to use this command."
        )


def raise_if_bot_not_connected(interaction: discord.Interaction):
    """Raise VoiceException if bot is not connected to voice."""
    if not interaction.guild.voice_client:
        raise VoiceException(
            "Bot not connected to voice",
            "I'm not connected to a voice channel."
        )


def raise_if_different_channel(interaction: discord.Interaction):
    """Raise VoiceException if user and bot are in different voice channels."""
    if (interaction.guild.voice_client and 
        interaction.user.voice and 
        interaction.user.voice.channel != interaction.guild.voice_client.channel):
        raise VoiceException(
            "User and bot in different voice channels",
            "You need to be in the same voice channel as me to use this command."
        ) 