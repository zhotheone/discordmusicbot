import logging
from typing import Dict, List, Optional

from core.dependency_injection import DIContainer
from core.events import EventBus, Events
from infrastructure.audio.filters.bass_boost import BassBoostFilter
from infrastructure.audio.filters.reverb import ReverbFilter
from infrastructure.audio.filters.slow_filter import SlowFilter
from infrastructure.audio.filters.spatial_audio import SpatialAudioFilter

logger = logging.getLogger(__name__)


class FilterService:
    """Service for managing audio filters."""
    
    def __init__(self, container: DIContainer, event_bus: EventBus):
        self.container = container
        self.event_bus = event_bus
        self.active_filters: Dict[int, Dict[str, object]] = {}  # guild_id -> {filter_name: filter_instance}
        
        # Available filters registry
        self.available_filters = {
            "bass_boost": BassBoostFilter,
            "reverb": ReverbFilter,
            "slow": SlowFilter,
            "8d": SpatialAudioFilter,
            "nightcore": lambda: SlowFilter(speed=1.3, pitch=1.2),
            "vaporwave": lambda: SlowFilter(speed=0.8, pitch=0.9)
        }
    
    async def apply_filter(self, guild_id: int, filter_name: str, **kwargs) -> bool:
        """Apply a filter to the guild's audio."""
        try:
            if filter_name not in self.available_filters:
                logger.warning(f"Unknown filter requested: {filter_name}")
                return False
            
            # Initialize guild filters if not exists
            if guild_id not in self.active_filters:
                self.active_filters[guild_id] = {}
            
            # Create filter instance
            filter_class = self.available_filters[filter_name]
            if callable(filter_class) and not isinstance(filter_class, type):
                # For lambda functions (nightcore, vaporwave)
                filter_instance = filter_class()
            else:
                # For regular filter classes
                filter_instance = filter_class(**kwargs)
            
            # Apply filter
            self.active_filters[guild_id][filter_name] = filter_instance
            
            # Notify audio player to update filter chain
            await self.event_bus.publish(
                Events.FILTER_APPLIED,
                guild_id=guild_id,
                filter_name=filter_name,
                filter_instance=filter_instance
            )
            
            logger.info(f"Applied filter '{filter_name}' to guild {guild_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error applying filter '{filter_name}' to guild {guild_id}: {e}")
            return False
    
    async def remove_filter(self, guild_id: int, filter_name: str) -> bool:
        """Remove a filter from the guild's audio."""
        try:
            if guild_id not in self.active_filters:
                return False
            
            if filter_name not in self.active_filters[guild_id]:
                return False
            
            # Remove filter
            del self.active_filters[guild_id][filter_name]
            
            # Clean up empty guild entries
            if not self.active_filters[guild_id]:
                del self.active_filters[guild_id]
            
            # Notify audio player to update filter chain
            await self.event_bus.publish(
                Events.FILTER_REMOVED,
                guild_id=guild_id,
                filter_name=filter_name
            )
            
            logger.info(f"Removed filter '{filter_name}' from guild {guild_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error removing filter '{filter_name}' from guild {guild_id}: {e}")
            return False
    
    async def clear_all_filters(self, guild_id: int) -> bool:
        """Remove all filters from the guild's audio."""
        try:
            if guild_id in self.active_filters:
                filter_names = list(self.active_filters[guild_id].keys())
                del self.active_filters[guild_id]
                
                # Notify audio player
                await self.event_bus.publish(
                    "filters_cleared",
                    guild_id=guild_id,
                    removed_filters=filter_names
                )
                
                logger.info(f"Cleared all filters from guild {guild_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error clearing filters from guild {guild_id}: {e}")
            return False
    
    def get_active_filters(self, guild_id: int) -> List[str]:
        """Get list of active filter names for a guild."""
        if guild_id not in self.active_filters:
            return []
        return list(self.active_filters[guild_id].keys())
    
    def get_available_filters(self) -> List[str]:
        """Get list of all available filter names."""
        return list(self.available_filters.keys())
    
    def get_filter_info(self, filter_name: str) -> Optional[dict]:
        """Get information about a specific filter."""
        filter_info = {
            "bass_boost": {
                "name": "Bass Boost",
                "description": "Enhances low-frequency audio for deeper bass",
                "parameters": ["level (0-10)"]
            },
            "reverb": {
                "name": "Reverb",
                "description": "Adds echo/reverb effect to create spatial depth",
                "parameters": ["room_size (0.0-1.0)", "damping (0.0-1.0)"]
            },
            "slow": {
                "name": "Slow/Speed",
                "description": "Adjusts playback speed and pitch",
                "parameters": ["speed (0.5-2.0)", "pitch (0.5-2.0)"]
            },
            "8d": {
                "name": "8D Audio",
                "description": "Creates immersive spatial audio effect",
                "parameters": ["intensity (0.0-1.0)"]
            },
            "nightcore": {
                "name": "Nightcore",
                "description": "High-speed, high-pitch anime-style effect",
                "parameters": []
            },
            "vaporwave": {
                "name": "Vaporwave",
                "description": "Slow, dreamy aesthetic with lowered pitch",
                "parameters": []
            }
        }
        
        return filter_info.get(filter_name)
    
    async def apply_user_filters(self, guild_id: int, user_id: int) -> bool:
        """Apply a user's preferred filters to the guild."""
        try:
            # Get user service to fetch preferences
            from domain.services.user_service import UserService
            user_service = self.container.get(UserService)
            
            user_settings = await user_service.get_user_settings(user_id)
            
            success_count = 0
            for filter_name in user_settings.preferred_filters:
                if await self.apply_filter(guild_id, filter_name):
                    success_count += 1
            
            logger.info(f"Applied {success_count}/{len(user_settings.preferred_filters)} user filters for guild {guild_id}")
            return success_count > 0
            
        except Exception as e:
            logger.error(f"Error applying user filters for guild {guild_id}: {e}")
            return False