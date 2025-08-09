import os
from dataclasses import dataclass, field
from typing import List, Optional

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    """Application configuration settings."""

    # Discord Configuration
    discord_token: str = os.getenv("DISCORD_TOKEN", "")
    command_prefix: str = os.getenv("COMMAND_PREFIX", "/")
    # Telegram Configuration
    telegram_token: str = os.getenv("TELEGRAM_TOKEN", "")
    enable_telegram: bool = os.getenv("ENABLE_TELEGRAM", "false").lower() == "true"

    # Database Configuration
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///musicbot.db")

    # Cache Configuration
    redis_url: Optional[str] = os.getenv("REDIS_URL")
    cache_ttl: int = int(os.getenv("CACHE_TTL", "3600"))  # 1 hour

    # Audio Configuration
    max_queue_size: int = int(os.getenv("MAX_QUEUE_SIZE", "100"))
    default_volume: float = float(os.getenv("DEFAULT_VOLUME", "0.5"))
    max_track_duration: int = int(os.getenv("MAX_TRACK_DURATION", "3600"))  # 1 hour

    # Filter Configuration
    available_filters: List[str] = field(
        default_factory=lambda: [
            "bass_boost",
            "reverb",
            "slow",
            "8d",
            "nightcore",
            "vaporwave",
        ]
    )

    # Rate Limiting
    commands_per_minute: int = int(os.getenv("COMMANDS_PER_MINUTE", "30"))

    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    # Feature Flags
    enable_spotify: bool = os.getenv("ENABLE_SPOTIFY", "false").lower() == "true"
    enable_soundcloud: bool = os.getenv("ENABLE_SOUNDCLOUD", "false").lower() == "true"

    def __post_init__(self):
        """Validate configuration after initialization."""
        if not self.discord_token:
            raise ValueError("DISCORD_TOKEN is required")

        if self.default_volume < 0 or self.default_volume > 1:
            raise ValueError("DEFAULT_VOLUME must be between 0 and 1")

        if self.max_queue_size < 1:
            raise ValueError("MAX_QUEUE_SIZE must be greater than 0")
