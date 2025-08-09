import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import delete, desc, func, select

from config.database import DatabaseManager
from core.dependency_injection import DIContainer
from domain.entities.track import Track, TrackSource
from domain.entities.user_settings import UserSettings
from infrastructure.database.models import (
    GuildFilters,
    GuildSettings,
    TelegramChatLink,
    TelegramChatMember,
    User,
    UserHistory,
)
from infrastructure.database.models import (
    UserSettings as UserSettingsModel,
)

logger = logging.getLogger(__name__)


class UserRepository:
    """Repository for user-related database operations."""

    def __init__(self, container: DIContainer):
        self.container = container
        self.db_manager: DatabaseManager = container.get(DatabaseManager)

    async def get_user_settings(self, user_id: int) -> Optional[UserSettings]:
        """Get user settings from database."""
        session = await self.db_manager.get_session()
        async with session:
            stmt = select(UserSettingsModel).where(UserSettingsModel.user_id == user_id)
            result = await session.execute(stmt)
            db_settings = result.scalar_one_or_none()

            if not db_settings:
                return None

            return UserSettings(
                user_id=db_settings.user_id,
                default_volume=db_settings.default_volume,
                preferred_filters=db_settings.preferred_filters or [],
                auto_play=db_settings.auto_play,
                repeat_mode=db_settings.repeat_mode,
                bass_boost_level=db_settings.bass_boost_level,
                custom_settings=db_settings.custom_settings or {},
                created_at=db_settings.created_at,
                updated_at=db_settings.updated_at,
            )

    async def save_user_settings(self, settings: UserSettings) -> bool:
        """Save user settings to database."""
        try:
            session = await self.db_manager.get_session()
            async with session:
                # First ensure user exists
                user_stmt = select(User).where(User.id == settings.user_id)
                user_result = await session.execute(user_stmt)
                user = user_result.scalar_one_or_none()

                if not user:
                    user = User(id=settings.user_id)
                    session.add(user)

                # Check if settings exist
                settings_stmt = select(UserSettingsModel).where(
                    UserSettingsModel.user_id == settings.user_id
                )
                settings_result = await session.execute(settings_stmt)
                db_settings = settings_result.scalar_one_or_none()

                if db_settings:
                    # Update existing settings
                    db_settings.default_volume = settings.default_volume
                    db_settings.preferred_filters = settings.preferred_filters
                    db_settings.auto_play = settings.auto_play
                    db_settings.repeat_mode = settings.repeat_mode
                    db_settings.bass_boost_level = settings.bass_boost_level
                    db_settings.custom_settings = settings.custom_settings
                    db_settings.updated_at = datetime.utcnow()
                else:
                    # Create new settings
                    db_settings = UserSettingsModel(
                        user_id=settings.user_id,
                        default_volume=settings.default_volume,
                        preferred_filters=settings.preferred_filters,
                        auto_play=settings.auto_play,
                        repeat_mode=settings.repeat_mode,
                        bass_boost_level=settings.bass_boost_level,
                        custom_settings=settings.custom_settings,
                    )
                    session.add(db_settings)

                await session.commit()
                return True

        except Exception as e:
            logger.error(f"Error saving user settings for {settings.user_id}: {e}")
            return False

    async def add_to_history(self, user_id: int, track: Track) -> bool:
        """Add a track to user's history."""
        try:
            session = await self.db_manager.get_session()
            async with session:
                # First ensure user exists
                user_stmt = select(User).where(User.id == user_id)
                user_result = await session.execute(user_stmt)
                user = user_result.scalar_one_or_none()

                if not user:
                    user = User(id=user_id)
                    session.add(user)

                # Add to history
                history_entry = UserHistory(
                    user_id=user_id,
                    track_title=track.title,
                    track_url=track.url,
                    track_duration=track.duration,
                    artist=track.artist,
                    album=track.album,
                    source=track.source.value,
                    thumbnail_url=track.thumbnail_url,
                    track_metadata=track.metadata or {},
                )
                session.add(history_entry)

                # Clean up old history (keep last 100 entries per user)
                cleanup_stmt = (
                    select(UserHistory.id)
                    .where(UserHistory.user_id == user_id)
                    .order_by(desc(UserHistory.played_at))
                    .offset(100)
                )

                old_entries_result = await session.execute(cleanup_stmt)
                old_entry_ids = [row[0] for row in old_entries_result]

                if old_entry_ids:
                    delete_stmt = delete(UserHistory).where(
                        UserHistory.id.in_(old_entry_ids)
                    )
                    await session.execute(delete_stmt)

                await session.commit()
                return True

        except Exception as e:
            logger.error(f"Error adding track to history for user {user_id}: {e}")
            return False

    async def get_user_history(self, user_id: int, limit: int = 10) -> List[Track]:
        """Get user's listening history."""
        try:
            session = await self.db_manager.get_session()
            async with session:
                stmt = (
                    select(UserHistory)
                    .where(UserHistory.user_id == user_id)
                    .order_by(desc(UserHistory.played_at))
                    .limit(limit)
                )

                result = await session.execute(stmt)
                history_entries = result.scalars().all()

                tracks = []
                for entry in history_entries:
                    track = Track(
                        title=entry.track_title,
                        url=entry.track_url or "",
                        duration=entry.track_duration or 0,
                        source=TrackSource(entry.source),
                        requester_id=user_id,
                        thumbnail_url=entry.thumbnail_url,
                        artist=entry.artist,
                        album=entry.album,
                        created_at=entry.played_at,
                        metadata=entry.track_metadata or {},
                    )
                    tracks.append(track)

                return tracks

        except Exception as e:
            logger.error(f"Error getting user history for {user_id}: {e}")
            return []

    async def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        """Get user statistics."""
        try:
            session = await self.db_manager.get_session()
            async with session:
                # Total tracks played
                total_stmt = select(func.count(UserHistory.id)).where(
                    UserHistory.user_id == user_id
                )
                total_result = await session.execute(total_stmt)
                total_tracks = total_result.scalar() or 0

                # Most played track
                most_played_stmt = (
                    select(
                        UserHistory.track_title,
                        UserHistory.artist,
                        func.count(UserHistory.id).label("play_count"),
                    )
                    .where(UserHistory.user_id == user_id)
                    .group_by(UserHistory.track_title, UserHistory.artist)
                    .order_by(desc("play_count"))
                    .limit(1)
                )

                most_played_result = await session.execute(most_played_stmt)
                most_played_row = most_played_result.first()

                most_played_track = None
                if most_played_row:
                    title, artist, count = most_played_row
                    most_played_track = {
                        "title": title,
                        "artist": artist,
                        "play_count": count,
                    }

                # Total listening time (approximate)
                duration_stmt = select(func.sum(UserHistory.track_duration)).where(
                    UserHistory.user_id == user_id,
                    UserHistory.track_duration.isnot(None),
                )
                duration_result = await session.execute(duration_stmt)
                total_duration = duration_result.scalar() or 0

                # Recent activity (last 30 days)
                recent_date = datetime.utcnow() - timedelta(days=30)
                recent_stmt = select(func.count(UserHistory.id)).where(
                    UserHistory.user_id == user_id, UserHistory.played_at >= recent_date
                )
                recent_result = await session.execute(recent_stmt)
                recent_tracks = recent_result.scalar() or 0

                return {
                    "total_tracks_played": total_tracks,
                    "most_played_track": most_played_track,
                    "listening_time_minutes": total_duration // 60
                    if total_duration
                    else 0,
                    "recent_activity_30_days": recent_tracks,
                }

        except Exception as e:
            logger.error(f"Error getting user stats for {user_id}: {e}")
            return {
                "total_tracks_played": 0,
                "most_played_track": None,
                "listening_time_minutes": 0,
                "recent_activity_30_days": 0,
            }


class GuildRepository:
    """Repository for guild-related database operations."""

    def __init__(self, container: DIContainer):
        self.container = container
        self.db_manager: DatabaseManager = container.get(DatabaseManager)

    async def get_guild_settings(self, guild_id: int) -> Optional[Dict[str, Any]]:
        """Get guild settings."""
        try:
            session = await self.db_manager.get_session()
            async with session:
                stmt = select(GuildSettings).where(GuildSettings.guild_id == guild_id)
                result = await session.execute(stmt)
                settings = result.scalar_one_or_none()

                if not settings:
                    return None

                return {
                    "guild_id": settings.guild_id,
                    "max_queue_size": settings.max_queue_size,
                    "default_volume": settings.default_volume,
                    "allowed_filters": settings.allowed_filters,
                    "command_prefix": settings.command_prefix,
                    "auto_disconnect_timeout": settings.auto_disconnect_timeout,
                    "max_track_duration": settings.max_track_duration,
                    "settings": settings.settings,
                }

        except Exception as e:
            logger.error(f"Error getting guild settings for {guild_id}: {e}")
            return None

    async def save_guild_settings(
        self, guild_id: int, settings: Dict[str, Any]
    ) -> bool:
        """Save guild settings."""
        try:
            session = await self.db_manager.get_session()
            async with session:
                stmt = select(GuildSettings).where(GuildSettings.guild_id == guild_id)
                result = await session.execute(stmt)
                db_settings = result.scalar_one_or_none()

                if db_settings:
                    # Update existing
                    for key, value in settings.items():
                        if hasattr(db_settings, key):
                            setattr(db_settings, key, value)
                    db_settings.updated_at = datetime.utcnow()
                else:
                    # Create new
                    db_settings = GuildSettings(guild_id=guild_id, **settings)
                    session.add(db_settings)

                await session.commit()
                return True

        except Exception as e:
            logger.error(f"Error saving guild settings for {guild_id}: {e}")
            return False


class TelegramChatLinkRepository:
    """Repository for Discord<->Telegram chat links."""

    def __init__(self, container: DIContainer):
        self.container = container
        self.db_manager: DatabaseManager = container.get(DatabaseManager)

    async def get_link_by_guild(self, guild_id: int) -> Optional[TelegramChatLink]:
        session = await self.db_manager.get_session()
        async with session:
            stmt = select(TelegramChatLink).where(TelegramChatLink.guild_id == guild_id)
            res = await session.execute(stmt)
            return res.scalar_one_or_none()

    async def get_link_by_chat(self, chat_id: int) -> Optional[TelegramChatLink]:
        session = await self.db_manager.get_session()
        async with session:
            stmt = select(TelegramChatLink).where(
                TelegramChatLink.telegram_chat_id == chat_id
            )
            res = await session.execute(stmt)
            return res.scalar_one_or_none()

    async def upsert_link(self, guild_id: int, chat_id: int) -> TelegramChatLink:
        session = await self.db_manager.get_session()
        async with session:
            stmt = select(TelegramChatLink).where(TelegramChatLink.guild_id == guild_id)
            res = await session.execute(stmt)
            link = res.scalar_one_or_none()
            if link:
                link.telegram_chat_id = chat_id
            else:
                link = TelegramChatLink(guild_id=guild_id, telegram_chat_id=chat_id)
                session.add(link)
            await session.commit()
            await session.refresh(link)
            return link

    async def remove_link(self, guild_id: int) -> bool:
        session = await self.db_manager.get_session()
        async with session:
            stmt = select(TelegramChatLink).where(TelegramChatLink.guild_id == guild_id)
            res = await session.execute(stmt)
            link = res.scalar_one_or_none()
            if not link:
                return False
            await session.delete(link)
            await session.commit()
            return True


class TelegramChatMemberRepository:
    """Repository for caching Telegram chat members."""

    def __init__(self, container: DIContainer):
        self.container = container
        self.db_manager: DatabaseManager = container.get(DatabaseManager)

    async def upsert_member(
        self,
        chat_id: int,
        user_id: int,
        is_bot: bool,
        username: Optional[str],
        first_name: Optional[str],
        last_name: Optional[str],
    ) -> None:
        session = await self.db_manager.get_session()
        async with session:
            stmt = select(TelegramChatMember).where(
                TelegramChatMember.chat_id == chat_id,
                TelegramChatMember.user_id == user_id,
            )
            res = await session.execute(stmt)
            row = res.scalar_one_or_none()
            if row:
                row.is_bot = is_bot
                row.username = username
                row.first_name = first_name
                row.last_name = last_name
            else:
                row = TelegramChatMember(
                    chat_id=chat_id,
                    user_id=user_id,
                    is_bot=is_bot,
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                )
                session.add(row)
            await session.commit()

    async def list_humans(self, chat_id: int) -> list[TelegramChatMember]:
        session = await self.db_manager.get_session()
        async with session:
            stmt = select(TelegramChatMember).where(
                TelegramChatMember.chat_id == chat_id,
                TelegramChatMember.is_bot.is_(False),
            )
            res = await session.execute(stmt)
            return list(res.scalars().all())


class GuildFiltersRepository:
    """Repository for managing guild filter settings."""

    def __init__(self, container: DIContainer):
        self.container = container
        self.db_manager: DatabaseManager = container.get(DatabaseManager)

    async def get_guild_filters(self, guild_id: int) -> Optional[Dict[str, dict]]:
        """Get active filters for a guild."""
        try:
            session = await self.db_manager.get_session()
            async with session:
                stmt = select(GuildFilters).where(GuildFilters.guild_id == guild_id)
                result = await session.execute(stmt)
                guild_filters = result.scalar_one_or_none()
                
                if guild_filters:
                    return guild_filters.active_filters
                return {}
                
        except Exception as e:
            logger.error(f"Error getting guild filters for {guild_id}: {e}")
            return {}

    async def set_guild_filters(self, guild_id: int, filters: Dict[str, dict]) -> bool:
        """Set active filters for a guild."""
        try:
            session = await self.db_manager.get_session()
            async with session:
                # Try to get existing record
                stmt = select(GuildFilters).where(GuildFilters.guild_id == guild_id)
                result = await session.execute(stmt)
                guild_filters = result.scalar_one_or_none()
                
                if guild_filters:
                    # Update existing record
                    guild_filters.active_filters = filters
                else:
                    # Create new record
                    guild_filters = GuildFilters(
                        guild_id=guild_id,
                        active_filters=filters
                    )
                    session.add(guild_filters)
                
                await session.commit()
                logger.info(f"Updated guild filters for {guild_id}: {list(filters.keys())}")
                return True
                
        except Exception as e:
            logger.error(f"Error setting guild filters for {guild_id}: {e}")
            return False

    async def add_guild_filter(self, guild_id: int, filter_name: str, filter_config: dict) -> bool:
        """Add a single filter to guild settings."""
        try:
            current_filters = await self.get_guild_filters(guild_id)
            current_filters[filter_name] = filter_config
            return await self.set_guild_filters(guild_id, current_filters)
            
        except Exception as e:
            logger.error(f"Error adding guild filter {filter_name} for {guild_id}: {e}")
            return False

    async def remove_guild_filter(self, guild_id: int, filter_name: str) -> bool:
        """Remove a single filter from guild settings."""
        try:
            current_filters = await self.get_guild_filters(guild_id)
            if filter_name in current_filters:
                del current_filters[filter_name]
                return await self.set_guild_filters(guild_id, current_filters)
            return True  # Filter wasn't there anyway
            
        except Exception as e:
            logger.error(f"Error removing guild filter {filter_name} for {guild_id}: {e}")
            return False

    async def clear_guild_filters(self, guild_id: int) -> bool:
        """Clear all filters for a guild."""
        try:
            return await self.set_guild_filters(guild_id, {})
            
        except Exception as e:
            logger.error(f"Error clearing guild filters for {guild_id}: {e}")
            return False
