"""Custom exception classes for the Discord bot."""

import logging
from typing import Optional
import discord


class BotBaseException(Exception):
    """Base exception class for all bot-related errors."""
    
    def __init__(self, message: str, user_message: Optional[str] = None, severity: str = "ERROR"):
        """
        Initialize base exception.
        
        Args:
            message: Technical error message for logging
            user_message: User-friendly message to display in Discord
            severity: Error severity level (INFO, WARNING, ERROR, CRITICAL)
        """
        super().__init__(message)
        self.message = message
        self.user_message = user_message or "An unexpected error occurred. Please try again later."
        self.severity = severity
        
    def get_embed(self) -> discord.Embed:
        """Create a Discord embed for this exception."""
        color_map = {
            "INFO": discord.Color.blue(),
            "WARNING": discord.Color.orange(),
            "ERROR": discord.Color.red(),
            "CRITICAL": discord.Color.dark_red()
        }
        
        return discord.Embed(
            title=f"{self.__class__.__name__.replace('Exception', ' Error')}",
            description=self.user_message,
            color=color_map.get(self.severity, discord.Color.red())
        )


class MusicException(BotBaseException):
    """Exception for music-related errors."""
    
    def __init__(self, message: str, user_message: Optional[str] = None):
        super().__init__(
            message, 
            user_message or "Music playback error occurred.",
            "ERROR"
        )


class PlaybackException(MusicException):
    """Exception for playback-specific errors."""
    
    def __init__(self, message: str, user_message: Optional[str] = None):
        super().__init__(
            message,
            user_message or "Unable to play the requested content. Please try a different song.",
            "ERROR"
        )


class QueueException(MusicException):
    """Exception for queue-related errors."""
    
    def __init__(self, message: str, user_message: Optional[str] = None):
        super().__init__(
            message,
            user_message or "Queue operation failed.",
            "WARNING"
        )


class VoiceException(BotBaseException):
    """Exception for voice connection issues."""
    
    def __init__(self, message: str, user_message: Optional[str] = None):
        super().__init__(
            message,
            user_message or "Voice connection error. Please check if I have permission to join your voice channel.",
            "ERROR"
        )


class ConfigurationException(BotBaseException):
    """Exception for configuration-related errors."""
    
    def __init__(self, message: str, user_message: Optional[str] = None):
        super().__init__(
            message,
            user_message or "Configuration error occurred.",
            "WARNING"
        )


class UserInputException(BotBaseException):
    """Exception for invalid user input."""
    
    def __init__(self, message: str, user_message: Optional[str] = None):
        super().__init__(
            message,
            user_message or "Invalid input provided. Please check your command and try again.",
            "INFO"
        )


class ServiceException(BotBaseException):
    """Exception for external service failures."""
    
    def __init__(self, message: str, user_message: Optional[str] = None, service_name: str = "External Service"):
        super().__init__(
            message,
            user_message or f"{service_name} is currently unavailable. Please try again later.",
            "ERROR"
        )
        self.service_name = service_name


class PermissionException(BotBaseException):
    """Exception for permission-related errors."""
    
    def __init__(self, message: str, user_message: Optional[str] = None):
        super().__init__(
            message,
            user_message or "I don't have the necessary permissions to perform this action.",
            "WARNING"
        )


class RateLimitException(BotBaseException):
    """Exception for rate limiting."""
    
    def __init__(self, message: str, user_message: Optional[str] = None, retry_after: Optional[int] = None):
        super().__init__(
            message,
            user_message or f"Rate limited. Please wait {'a few seconds' if not retry_after else f'{retry_after} seconds'} before trying again.",
            "WARNING"
        )
        self.retry_after = retry_after


class CriticalBotException(BotBaseException):
    """Exception for critical bot errors that require immediate attention."""
    
    def __init__(self, message: str, user_message: Optional[str] = None):
        super().__init__(
            message,
            user_message or "A critical error occurred. The bot administrators have been notified.",
            "CRITICAL"
        ) 