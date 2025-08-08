import logging
from typing import List, Optional

from core.dependency_injection import DIContainer
from core.events import EventBus
from domain.entities.user_settings import UserSettings
from domain.entities.track import Track
from infrastructure.database.repositories import UserRepository

logger = logging.getLogger(__name__)


class UserService:
    """Service for managing user settings and preferences."""
    
    def __init__(self, container: DIContainer, event_bus: EventBus):
        self.container = container
        self.event_bus = event_bus
        self.user_repo = UserRepository(container)
    
    async def get_user_settings(self, user_id: int) -> UserSettings:
        """Get user settings, creating defaults if not found."""
        try:
            settings = await self.user_repo.get_user_settings(user_id)
            if not settings:
                # Create default settings
                settings = UserSettings(user_id=user_id)
                await self.user_repo.save_user_settings(settings)
                logger.info(f"Created default settings for user {user_id}")
            
            return settings
            
        except Exception as e:
            logger.error(f"Error getting user settings for {user_id}: {e}")
            # Return default settings on error
            return UserSettings(user_id=user_id)
    
    async def update_volume(self, user_id: int, volume: float) -> bool:
        """Update user's default volume preference."""
        try:
            settings = await self.get_user_settings(user_id)
            settings.update_volume(volume)
            
            await self.user_repo.save_user_settings(settings)
            await self.event_bus.publish("user_volume_updated", user_id=user_id, volume=volume)
            
            logger.info(f"Updated volume for user {user_id}: {volume}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating volume for user {user_id}: {e}")
            return False
    
    async def add_preferred_filter(self, user_id: int, filter_name: str) -> bool:
        """Add a filter to user's preferences."""
        try:
            settings = await self.get_user_settings(user_id)
            settings.add_filter(filter_name)
            
            await self.user_repo.save_user_settings(settings)
            await self.event_bus.publish("user_filter_added", user_id=user_id, filter=filter_name)
            
            logger.info(f"Added filter '{filter_name}' for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding filter for user {user_id}: {e}")
            return False
    
    async def remove_preferred_filter(self, user_id: int, filter_name: str) -> bool:
        """Remove a filter from user's preferences."""
        try:
            settings = await self.get_user_settings(user_id)
            settings.remove_filter(filter_name)
            
            await self.user_repo.save_user_settings(settings)
            await self.event_bus.publish("user_filter_removed", user_id=user_id, filter=filter_name)
            
            logger.info(f"Removed filter '{filter_name}' for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error removing filter for user {user_id}: {e}")
            return False
    
    async def set_repeat_mode(self, user_id: int, mode: str) -> bool:
        """Set user's preferred repeat mode."""
        try:
            settings = await self.get_user_settings(user_id)
            settings.set_repeat_mode(mode)
            
            await self.user_repo.save_user_settings(settings)
            await self.event_bus.publish("user_repeat_mode_updated", user_id=user_id, mode=mode)
            
            logger.info(f"Set repeat mode for user {user_id}: {mode}")
            return True
            
        except Exception as e:
            logger.error(f"Error setting repeat mode for user {user_id}: {e}")
            return False
    
    async def add_to_history(self, user_id: int, track: Track) -> bool:
        """Add a track to user's listening history."""
        try:
            await self.user_repo.add_to_history(user_id, track)
            await self.event_bus.publish("track_added_to_history", user_id=user_id, track=track)
            
            logger.debug(f"Added track to history for user {user_id}: {track.title}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding track to history for user {user_id}: {e}")
            return False
    
    async def get_history(self, user_id: int, limit: int = 10) -> List[Track]:
        """Get user's listening history."""
        try:
            history = await self.user_repo.get_user_history(user_id, limit)
            logger.debug(f"Retrieved {len(history)} history tracks for user {user_id}")
            return history
            
        except Exception as e:
            logger.error(f"Error getting history for user {user_id}: {e}")
            return []
    
    async def get_user_stats(self, user_id: int) -> dict:
        """Get user statistics."""
        try:
            stats = await self.user_repo.get_user_stats(user_id)
            return stats
            
        except Exception as e:
            logger.error(f"Error getting stats for user {user_id}: {e}")
            return {
                "total_tracks_played": 0,
                "most_played_track": None,
                "favorite_filters": [],
                "listening_time_minutes": 0
            }
    
    async def reset_user_settings(self, user_id: int) -> bool:
        """Reset user settings to defaults."""
        try:
            default_settings = UserSettings(user_id=user_id)
            await self.user_repo.save_user_settings(default_settings)
            await self.event_bus.publish("user_settings_reset", user_id=user_id)
            
            logger.info(f"Reset settings for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error resetting settings for user {user_id}: {e}")
            return False