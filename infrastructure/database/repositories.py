import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from sqlalchemy import select, delete, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependency_injection import DIContainer
from config.database import DatabaseManager
from domain.entities.user_settings import UserSettings
from domain.entities.track import Track, TrackSource
from infrastructure.database.models import User, UserSettings as UserSettingsModel, UserHistory, GuildSettings

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
                updated_at=db_settings.updated_at
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
                settings_stmt = select(UserSettingsModel).where(UserSettingsModel.user_id == settings.user_id)
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
                        custom_settings=settings.custom_settings
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
                    track_metadata=track.metadata or {}
                )
                session.add(history_entry)
                
                # Clean up old history (keep last 100 entries per user)
                cleanup_stmt = select(UserHistory.id).where(
                    UserHistory.user_id == user_id
                ).order_by(desc(UserHistory.played_at)).offset(100)
                
                old_entries_result = await session.execute(cleanup_stmt)
                old_entry_ids = [row[0] for row in old_entries_result]
                
                if old_entry_ids:
                    delete_stmt = delete(UserHistory).where(UserHistory.id.in_(old_entry_ids))
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
                stmt = select(UserHistory).where(
                    UserHistory.user_id == user_id
                ).order_by(desc(UserHistory.played_at)).limit(limit)
                
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
                        metadata=entry.track_metadata or {}
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
                total_stmt = select(func.count(UserHistory.id)).where(UserHistory.user_id == user_id)
                total_result = await session.execute(total_stmt)
                total_tracks = total_result.scalar() or 0
                
                # Most played track
                most_played_stmt = select(
                    UserHistory.track_title,
                    UserHistory.artist,
                    func.count(UserHistory.id).label('play_count')
                ).where(
                    UserHistory.user_id == user_id
                ).group_by(
                    UserHistory.track_title, UserHistory.artist
                ).order_by(desc('play_count')).limit(1)
                
                most_played_result = await session.execute(most_played_stmt)
                most_played_row = most_played_result.first()
                
                most_played_track = None
                if most_played_row:
                    title, artist, count = most_played_row
                    most_played_track = {
                        'title': title,
                        'artist': artist,
                        'play_count': count
                    }
                
                # Total listening time (approximate)
                duration_stmt = select(func.sum(UserHistory.track_duration)).where(
                    UserHistory.user_id == user_id,
                    UserHistory.track_duration.isnot(None)
                )
                duration_result = await session.execute(duration_stmt)
                total_duration = duration_result.scalar() or 0
                
                # Recent activity (last 30 days)
                recent_date = datetime.utcnow() - timedelta(days=30)
                recent_stmt = select(func.count(UserHistory.id)).where(
                    UserHistory.user_id == user_id,
                    UserHistory.played_at >= recent_date
                )
                recent_result = await session.execute(recent_stmt)
                recent_tracks = recent_result.scalar() or 0
                
                return {
                    'total_tracks_played': total_tracks,
                    'most_played_track': most_played_track,
                    'listening_time_minutes': total_duration // 60 if total_duration else 0,
                    'recent_activity_30_days': recent_tracks
                }
                
        except Exception as e:
            logger.error(f"Error getting user stats for {user_id}: {e}")
            return {
                'total_tracks_played': 0,
                'most_played_track': None,
                'listening_time_minutes': 0,
                'recent_activity_30_days': 0
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
                    'guild_id': settings.guild_id,
                    'max_queue_size': settings.max_queue_size,
                    'default_volume': settings.default_volume,
                    'allowed_filters': settings.allowed_filters,
                    'command_prefix': settings.command_prefix,
                    'auto_disconnect_timeout': settings.auto_disconnect_timeout,
                    'max_track_duration': settings.max_track_duration,
                    'settings': settings.settings
                }
                
        except Exception as e:
            logger.error(f"Error getting guild settings for {guild_id}: {e}")
            return None
    
    async def save_guild_settings(self, guild_id: int, settings: Dict[str, Any]) -> bool:
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