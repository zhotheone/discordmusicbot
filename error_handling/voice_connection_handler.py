"""Voice connection error handling and retry logic."""

import asyncio
import logging
import discord
from typing import Optional

from .exceptions import VoiceException, CriticalBotException

log = logging.getLogger(__name__)


class VoiceConnectionHandler:
    """Handles voice connection errors and retries."""
    
    def __init__(self, max_retries: int = 3, retry_delay: float = 5.0):
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.connection_attempts = {}
    
    async def connect_with_retry(self, voice_channel: discord.VoiceChannel, guild_id: int) -> Optional[discord.VoiceClient]:
        """Attempt to connect to voice channel with retry logic."""
        attempt_key = f"{guild_id}_{voice_channel.id}"
        current_attempts = self.connection_attempts.get(attempt_key, 0)
        
        for attempt in range(current_attempts, self.max_retries):
            try:
                log.info(f"Attempting voice connection to {voice_channel.name} (attempt {attempt + 1}/{self.max_retries})")
                
                # Try to connect
                voice_client = await voice_channel.connect(timeout=30.0, reconnect=True)
                
                # Reset attempt counter on success
                self.connection_attempts[attempt_key] = 0
                log.info(f"Successfully connected to voice channel: {voice_channel.name}")
                
                return voice_client
                
            except discord.errors.ConnectionClosed as e:
                log.warning(f"Voice connection closed (code: {e.code}): {e}")
                
                if e.code == 4006:  # Session no longer valid
                    log.info("Session invalidated, will retry with fresh connection")
                elif e.code == 4014:  # Disconnected
                    log.info("Disconnected from voice, retrying...")
                elif e.code == 1000:  # Normal closure
                    log.info("Normal voice disconnection")
                    break
                else:
                    log.error(f"Unexpected voice connection close code: {e.code}")
                
            except discord.ClientException as e:
                log.error(f"Discord client error during voice connection: {e}")
                
            except asyncio.TimeoutError:
                log.warning(f"Voice connection timeout on attempt {attempt + 1}")
                
            except Exception as e:
                log.error(f"Unexpected error during voice connection: {e}")
            
            # Update attempt counter
            self.connection_attempts[attempt_key] = attempt + 1
            
            # Wait before retry (except on last attempt)
            if attempt < self.max_retries - 1:
                log.info(f"Retrying voice connection in {self.retry_delay} seconds...")
                await asyncio.sleep(self.retry_delay)
        
        # All attempts failed
        log.error(f"Failed to connect to voice channel after {self.max_retries} attempts")
        self.connection_attempts[attempt_key] = 0  # Reset for future attempts
        
        raise VoiceException(
            f"Failed to connect to voice channel after {self.max_retries} attempts",
            f"Unable to connect to voice channel '{voice_channel.name}'. The voice service may be temporarily unavailable."
        )
    
    async def handle_voice_disconnect(self, guild_id: int, voice_client: discord.VoiceClient):
        """Handle unexpected voice disconnections."""
        try:
            if voice_client.is_connected():
                await voice_client.disconnect(force=True)
                log.info(f"Forcefully disconnected from voice in guild {guild_id}")
        except Exception as e:
            log.error(f"Error during voice cleanup in guild {guild_id}: {e}")
    
    def reset_connection_attempts(self, guild_id: int, channel_id: int):
        """Reset connection attempt counter for a specific channel."""
        attempt_key = f"{guild_id}_{channel_id}"
        self.connection_attempts.pop(attempt_key, None)


# Global voice connection handler instance
voice_handler = VoiceConnectionHandler()


async def safe_voice_connect(voice_channel: discord.VoiceChannel) -> discord.VoiceClient:
    """Safely connect to a voice channel with error handling."""
    return await voice_handler.connect_with_retry(voice_channel, voice_channel.guild.id)


async def safe_voice_disconnect(voice_client: discord.VoiceClient):
    """Safely disconnect from voice channel."""
    if voice_client and voice_client.is_connected():
        try:
            await voice_client.disconnect(force=False)
            log.info("Successfully disconnected from voice")
        except Exception as e:
            log.warning(f"Error during voice disconnect: {e}")
            try:
                await voice_client.disconnect(force=True)
                log.info("Force disconnected from voice")
            except Exception as force_error:
                log.error(f"Failed to force disconnect: {force_error}")


def handle_voice_error(error: Exception) -> VoiceException:
    """Convert voice errors to appropriate VoiceException."""
    if isinstance(error, discord.errors.ConnectionClosed):
        match error.code:
            case 4006:
                return VoiceException(
                    f"Voice session invalid (code 4006): {error}",
                    "Voice connection session expired. Please try again."
                )
            case 4014:
                return VoiceException(
                    f"Disconnected from voice (code 4014): {error}",
                    "Disconnected from voice channel. Please try reconnecting."
                )
            case 1000:
                return VoiceException(
                    f"Normal voice closure (code 1000): {error}",
                    "Voice connection closed normally."
                )
            case _:
                return VoiceException(
                    f"Voice connection error (code {error.code}): {error}",
                    "Voice connection failed. Please try again."
                )
    
    elif isinstance(error, discord.ClientException):
        return VoiceException(
            f"Discord client error: {error}",
            "Voice service error. Please try again."
        )
    
    elif isinstance(error, asyncio.TimeoutError):
        return VoiceException(
            f"Voice connection timeout: {error}",
            "Voice connection timed out. Please try again."
        )
    
    else:
        return VoiceException(
            f"Unexpected voice error: {error}",
            "An unexpected voice error occurred. Please try again."
        ) 