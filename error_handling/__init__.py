"""Error handling package for the Discord bot."""

from .exceptions import (
    BotBaseException,
    MusicException,
    PlaybackException,
    QueueException,
    VoiceException,
    ConfigurationException,
    UserInputException,
    ServiceException,
    PermissionException,
    RateLimitException,
    CriticalBotException
)

from .error_handler import (
    ErrorHandler,
    handle_errors,
    setup_bot_error_handlers
)

__all__ = [
    'BotBaseException',
    'MusicException',
    'PlaybackException',
    'QueueException',
    'VoiceException',
    'ConfigurationException',
    'UserInputException',
    'ServiceException',
    'PermissionException',
    'RateLimitException',
    'CriticalBotException',
    'ErrorHandler',
    'handle_errors',
    'setup_bot_error_handlers'
] 