# Discord Music Bot Architecture

## Overview
This document outlines a scalable, maintainable, and robust architecture for a Discord music bot with advanced features including audio filters, user configuration persistence, and comprehensive playback controls.

## Core Architecture Principles

### 1. Layered Architecture
- **Presentation Layer**: Discord commands and interactions
- **Application Layer**: Business logic and orchestration
- **Domain Layer**: Core entities and business rules
- **Infrastructure Layer**: Database, external APIs, audio processing

### 2. Dependency Injection
- Use dependency injection container for loose coupling
- Facilitate testing and modularity
- Enable easy swapping of implementations

### 3. Event-Driven Design
- Decouple components using event system
- Enable reactive programming patterns
- Support for extensibility and monitoring

## Directory Structure

```
discordmusicbot/
├── main.py                    # Application entry point
├── config/
│   ├── __init__.py
│   ├── settings.py            # Configuration management
│   └── database.py            # Database configuration
├── core/
│   ├── __init__.py
│   ├── bot.py                 # Main bot class
│   ├── events.py              # Event system
│   └── dependency_injection.py
├── domain/
│   ├── __init__.py
│   ├── entities/
│   │   ├── __init__.py
│   │   ├── track.py           # Track entity
│   │   ├── playlist.py        # Playlist entity
│   │   ├── user_settings.py   # User configuration entity
│   │   └── guild_settings.py  # Server-specific settings
│   ├── interfaces/
│   │   ├── __init__.py
│   │   ├── audio_source.py    # Audio source interface
│   │   ├── filter_processor.py # Filter processing interface
│   │   ├── repository.py      # Repository pattern interfaces
│   │   └── cache.py           # Cache interface
│   └── services/
│       ├── __init__.py
│       ├── music_service.py   # Core music business logic
│       ├── filter_service.py  # Audio filter management
│       ├── playlist_service.py # Playlist management
│       └── user_service.py    # User configuration management
├── infrastructure/
│   ├── __init__.py
│   ├── database/
│   │   ├── __init__.py
│   │   ├── models.py          # SQLAlchemy models
│   │   ├── repositories.py    # Database repositories
│   │   └── migrations/        # Database migrations
│   ├── audio/
│   │   ├── __init__.py
│   │   ├── sources/
│   │   │   ├── __init__.py
│   │   │   ├── youtube.py     # YouTube audio source
│   │   │   ├── spotify.py     # Spotify integration
│   │   │   └── local_files.py # Local file support
│   │   ├── filters/
│   │   │   ├── __init__.py
│   │   │   ├── bass_boost.py  # Bass boost filter
│   │   │   ├── reverb.py      # Reverb filter
│   │   │   ├── slow_filter.py # Speed adjustment
│   │   │   └── spatial_audio.py # 8D audio filter
│   │   └── player.py          # Audio player implementation
│   ├── cache/
│   │   ├── __init__.py
│   │   ├── redis_cache.py     # Redis cache implementation
│   │   └── memory_cache.py    # In-memory cache fallback
│   └── external/
│       ├── __init__.py
│       └── youtube_api.py     # YouTube API integration
├── application/
│   ├── __init__.py
│   ├── commands/
│   │   ├── __init__.py
│   │   ├── music_commands.py  # Play, stop, skip commands
│   │   ├── filter_commands.py # Filter application commands
│   │   ├── playlist_commands.py # Playlist management
│   │   └── settings_commands.py # User settings
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── error_handler.py   # Global error handling
│   │   ├── voice_handler.py   # Voice connection management
│   │   └── event_handler.py   # Discord event handling
│   └── middleware/
│       ├── __init__.py
│       ├── rate_limiting.py   # Rate limiting middleware
│       ├── logging.py         # Request/response logging
│       └── validation.py      # Input validation
├── presentation/
│   ├── __init__.py
│   ├── cogs/
│   │   ├── __init__.py
│   │   ├── music_cog.py       # Music-related commands
│   │   ├── filters_cog.py     # Filter commands
│   │   ├── playlist_cog.py    # Playlist commands
│   │   └── admin_cog.py       # Administrative commands
│   └── views/
│       ├── __init__.py
│       ├── music_controls.py  # Interactive music controls
│       ├── filter_panel.py    # Filter selection UI
│       └── playlist_manager.py # Playlist management UI
├── utils/
│   ├── __init__.py
│   ├── decorators.py          # Custom decorators
│   ├── validators.py          # Input validation utilities
│   ├── formatters.py          # Output formatting
│   └── exceptions.py          # Custom exceptions
└── tests/
    ├── __init__.py
    ├── unit/
    ├── integration/
    └── fixtures/
```

## Key Components

### 1. Core Bot (core/bot.py)
```python
class MusicBot:
    """Main bot class orchestrating all components"""
    
    def __init__(self, container: DIContainer):
        self.container = container
        self.music_service = container.get(MusicService)
        self.user_service = container.get(UserService)
        
    async def setup_hook(self):
        """Initialize bot components"""
        await self.load_cogs()
        await self.setup_database()
        await self.setup_cache()
```

### 2. Music Service (domain/services/music_service.py)
```python
class MusicService:
    """Core music business logic"""
    
    async def play(self, guild_id: int, query: str, user_id: int) -> Track
    async def skip(self, guild_id: int) -> Optional[Track]
    async def stop(self, guild_id: int) -> None
    async def set_repeat_mode(self, guild_id: int, mode: RepeatMode) -> None
    async def apply_filters(self, guild_id: int, filters: List[str]) -> None
```

### 3. Filter Service (domain/services/filter_service.py)
```python
class FilterService:
    """Audio filter management"""
    
    async def apply_filter(self, audio_source: AudioSource, filter_type: FilterType) -> AudioSource
    async def remove_filter(self, audio_source: AudioSource, filter_type: FilterType) -> AudioSource
    async def get_available_filters(self) -> List[FilterType]
```

### 4. User Service (domain/services/user_service.py)
```python
class UserService:
    """User configuration management"""
    
    async def get_user_settings(self, user_id: int) -> UserSettings
    async def update_filters(self, user_id: int, filters: List[str]) -> None
    async def update_volume(self, user_id: int, volume: float) -> None
    async def add_to_history(self, user_id: int, track: Track) -> None
    async def get_history(self, user_id: int, limit: int = 10) -> List[Track]
```

## Database Schema (NeonDB)

### Tables

#### users
```sql
CREATE TABLE users (
    id BIGINT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### user_settings
```sql
CREATE TABLE user_settings (
    user_id BIGINT PRIMARY KEY REFERENCES users(id),
    default_volume DECIMAL(3,2) DEFAULT 0.50,
    preferred_filters JSONB DEFAULT '[]',
    auto_play BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### user_history
```sql
CREATE TABLE user_history (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id),
    track_title VARCHAR(500) NOT NULL,
    track_url VARCHAR(1000),
    track_duration INTEGER,
    played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_played (user_id, played_at DESC)
);
```

#### guild_settings
```sql
CREATE TABLE guild_settings (
    guild_id BIGINT PRIMARY KEY,
    max_queue_size INTEGER DEFAULT 100,
    default_volume DECIMAL(3,2) DEFAULT 0.50,
    allowed_filters JSONB DEFAULT '["bass_boost", "reverb", "slow", "8d"]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Audio Processing Architecture

### Filter Pipeline
```python
class FilterPipeline:
    """Audio filter processing pipeline"""
    
    def __init__(self):
        self.filters: List[AudioFilter] = []
        
    def add_filter(self, filter: AudioFilter) -> None
    def remove_filter(self, filter_type: FilterType) -> None
    def process(self, audio_data: bytes) -> bytes
```

### Available Filters
1. **Bass Boost**: Enhances low-frequency audio
2. **Reverb**: Adds echo/reverb effect
3. **Slow/Speed**: Adjusts playback speed
4. **8D Audio**: Creates spatial audio effect
5. **Nightcore**: High-speed, high-pitch effect
6. **Vaporwave**: Slow, low-pitch effect

## Caching Strategy

### Multi-Level Caching
1. **Redis Cache**: Distributed caching for user settings and track metadata
2. **Memory Cache**: Fast local caching for frequently accessed data
3. **File Cache**: Audio file caching for popular tracks

### Cache Keys
- `user_settings:{user_id}` - User configuration
- `track_metadata:{track_id}` - Track information
- `playlist:{guild_id}` - Current playlist
- `audio_cache:{track_hash}` - Cached audio files

## Error Handling & Resilience

### Error Categories
1. **Network Errors**: YouTube API failures, timeout issues
2. **Audio Errors**: Codec issues, invalid audio formats
3. **Discord Errors**: Voice connection issues, permission errors
4. **Database Errors**: Connection failures, constraint violations

### Resilience Patterns
- **Circuit Breaker**: Prevent cascade failures
- **Retry with Exponential Backoff**: Handle transient failures
- **Graceful Degradation**: Fallback to basic functionality
- **Health Checks**: Monitor component status

## Performance Considerations

### Optimization Strategies
1. **Connection Pooling**: Database and HTTP connections
2. **Lazy Loading**: Load resources on-demand
3. **Batch Operations**: Group database operations
4. **Async Processing**: Non-blocking I/O operations
5. **Resource Cleanup**: Proper disposal of audio resources

### Monitoring & Metrics
- Response times for commands
- Memory usage and garbage collection
- Database query performance
- Voice connection stability
- Error rates by component

## Security & Best Practices

### Security Measures
1. **Input Validation**: Sanitize all user inputs
2. **Rate Limiting**: Prevent abuse and spam
3. **Permission Checks**: Verify user permissions
4. **Secure Storage**: Encrypt sensitive configuration
5. **Audit Logging**: Track administrative actions

### Development Best Practices
1. **Type Hints**: Full type annotation coverage
2. **Unit Testing**: Comprehensive test coverage
3. **Integration Testing**: End-to-end testing
4. **Code Review**: Peer review process
5. **Documentation**: Inline and API documentation

## Deployment Architecture

### Container Strategy
```yaml
# docker-compose.yml
services:
  bot:
    build: .
    environment:
      - DATABASE_URL=${NEON_DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
    depends_on:
      - redis
      
  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
```

### Environment Configuration
- Development: Local SQLite + Memory cache
- Staging: NeonDB + Redis cluster
- Production: NeonDB + Redis cluster + Load balancer

## Migration Strategy

### From Current Architecture
1. **Phase 1**: Implement new domain layer alongside existing code
2. **Phase 2**: Migrate commands to new architecture one by one
3. **Phase 3**: Replace infrastructure components
4. **Phase 4**: Remove legacy code and optimize

### Database Migration
1. Create migration scripts for schema changes
2. Use Alembic for version control
3. Implement backward compatibility during transition
4. Plan rollback strategies

## Scalability Considerations

### Horizontal Scaling
- Stateless bot instances
- Shared Redis cache
- Database connection pooling
- Load balancing between instances

### Vertical Scaling
- Memory optimization for audio processing
- CPU optimization for filter processing
- I/O optimization for database operations

This architecture provides a solid foundation for a maintainable, scalable Discord music bot with all the requested features while following Python best practices and enterprise-grade patterns.

## Telegram Bridge (Discord ↔ Telegram)

### Overview
An optional Telegram bot (Aiogram 3) lets users control playback from Telegram and mirrors Discord playback updates to a linked Telegram chat. It’s disabled by default and can be enabled via environment flags.

### Components
- `presentation/telegram/bot.py` — TelegramService
    - Starts an Aiogram `Bot`, registers handlers: `/list`, `/play`, `/queue`, `/stop`, `/volume`, `/id`.
    - Uses `MusicService` and audio sources (`YouTubeSource`, `SpotifySource`) to queue/play.
    - Subscribes to `core.events.EventBus` to forward events (track started/skipped/ended, paused/resumed, volume, queue finished).
    - Implements `TelegramSender` interface (send_message, helpers).
- `application/handlers/telegram_bridge.py` — TelegramBridge
    - Mediates between Discord and Telegram. Discord code calls the bridge; the Telegram service registers itself as a sender.
    - Provides high-level actions like `send_mention_all(guild_id, text)` and `link_guild_to_chat(guild_id, chat_id)`.
    - Uses repositories to resolve guild↔chat links and cached Telegram members.
- `infrastructure/database/models.py` and `.../repositories.py`
    - `TelegramChatLink` table — maps Discord guild_id to Telegram `telegram_chat_id`.
    - `TelegramChatMember` table — caches chat members (humans) for building @all mentions.

### Startup & DI
- `main.py` calls `presentation.telegram.start_telegram(container, settings)` after the Discord bot is created.
- `start_telegram` checks `Settings.enable_telegram`; if enabled, it:
    1) Creates and registers `TelegramBridge` in the DI container.
    2) Instantiates `TelegramService`, registers it as the bridge sender, then starts polling.
- `Settings` loads `ENABLE_TELEGRAM` and `TELEGRAM_TOKEN` from env.

### Linking Flow (Discord Admin)
1) Add the Telegram bot to your target Telegram chat/group.
2) In Telegram, send `/id` to get the numeric `chat_id`.
3) In Discord (admin), run `/connect_telegram <chat_id>`.
4) The bridge verifies/records the link via `TelegramChatLinkRepository`.

After linking, Discord events and admin actions can target the linked chat.

### Commands and Events
- Telegram commands handled by `TelegramService`:
    - `/list` — show non-offline members of the linked Discord guild.
    - `/play <query|url>` — queue music (YouTube/Spotify links or search query).
    - `/queue`, `/stop`, `/volume <0-100>`, `/id`.
- Discord admin commands (in `presentation/cogs/admin_cog.py`):
    - `/connect_telegram <chat_id>` — link guild to Telegram chat.
    - `/all <reason>` — mention all known humans in the linked Telegram chat via the bridge.
- Events forwarded to Telegram (via EventBus): now playing, skipped, finished, paused/resumed, volume changes, queue finished.

### Data Model
- `telegram_chat_links(guild_id, telegram_chat_id)` — unique by `telegram_chat_id`.
- `telegram_chat_members(chat_id, user_id, username, first_name, last_name, is_bot)` — populated opportunistically from incoming Telegram messages to build @all mentions.

### Configuration
- Environment variables:
    - `ENABLE_TELEGRAM` — `true|false` (default false).
    - `TELEGRAM_TOKEN` — Bot token from @BotFather.
- When disabled or token is missing, Telegram service does not start and the rest of the bot runs normally.