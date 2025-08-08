class BotError(Exception):
    """Base exception class for bot errors."""
    pass


class BotInitializationError(BotError):
    """Raised when bot initialization fails."""
    pass


class AudioError(BotError):
    """Base class for audio-related errors."""
    pass


class AudioSourceError(AudioError):
    """Raised when audio source operations fail."""
    pass


class PlaybackError(AudioError):
    """Raised when playback operations fail."""
    pass


class FilterError(AudioError):
    """Raised when filter operations fail."""
    pass


class DatabaseError(BotError):
    """Raised when database operations fail."""
    pass


class ValidationError(BotError):
    """Raised when input validation fails."""
    pass


class RateLimitError(BotError):
    """Raised when rate limits are exceeded."""
    pass


class PermissionError(BotError):
    """Raised when user lacks required permissions."""
    pass


class VoiceConnectionError(AudioError):
    """Raised when voice connection operations fail."""
    pass


class QueueError(BotError):
    """Raised when queue operations fail."""
    pass


class UserError(BotError):
    """Raised when user operations fail."""
    pass


class ConfigurationError(BotError):
    """Raised when configuration is invalid."""
    pass