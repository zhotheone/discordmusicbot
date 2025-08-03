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
    setup_bot_error_handlers,
    raise_if_not_in_voice,
    raise_if_bot_not_connected,
    raise_if_different_channel
)

from .voice_connection_handler import (
    safe_voice_connect,
    safe_voice_disconnect,
    handle_voice_error,
    voice_handler
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
    'setup_bot_error_handlers',
    'raise_if_not_in_voice',
    'raise_if_bot_not_connected',
    'raise_if_different_channel',
    'safe_voice_connect',
    'safe_voice_disconnect',
    'handle_voice_error',
    'voice_handler'
] 