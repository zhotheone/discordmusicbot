import logging
from typing import Dict, List, Optional

from core.dependency_injection import DIContainer
from core.events import EventBus, Events
from infrastructure.audio.filters.bass_boost import BassBoostFilter
from infrastructure.audio.filters.reverb import ReverbFilter
from infrastructure.audio.filters.slow_filter import SlowFilter
from infrastructure.audio.filters.spatial_audio import SpatialAudioFilter
from infrastructure.database.repositories import GuildFiltersRepository

logger = logging.getLogger(__name__)


class FilterService:
    """Service for managing audio filters."""
    
    def __init__(self, container: DIContainer, event_bus: EventBus):
        self.container = container
        self.event_bus = event_bus
        self.active_filters: Dict[int, Dict[str, object]] = {}  # guild_id -> {filter_name: filter_instance}
        self.filters_repository = GuildFiltersRepository(container)
        self._loaded_guilds: set = set()  # Track which guilds have loaded filters
        
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
            
            # Save filter configuration to database
            filter_config = self._serialize_filter_instance(filter_instance)
            await self.filters_repository.add_guild_filter(guild_id, filter_name, filter_config)
            
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
            
            # Remove from database
            await self.filters_repository.remove_guild_filter(guild_id, filter_name)
            
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
    
    async def clear_filters(self, guild_id: int) -> bool:
        """Remove all filters from the guild's audio."""
        return await self.clear_all_filters(guild_id)
    
    async def clear_all_filters(self, guild_id: int) -> bool:
        """Remove all filters from the guild's audio."""
        try:
            if guild_id in self.active_filters:
                filter_names = list(self.active_filters[guild_id].keys())
                del self.active_filters[guild_id]
                
                # Clear from database
                await self.filters_repository.clear_guild_filters(guild_id)
                
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
    
    async def load_guild_filters(self, guild_id: int) -> bool:
        """Load and apply saved filters for a guild."""
        try:
            # Skip if already loaded
            if guild_id in self._loaded_guilds:
                return True
                
            saved_filters = await self.filters_repository.get_guild_filters(guild_id)
            
            if not saved_filters:
                logger.info(f"No saved filters found for guild {guild_id}")
                self._loaded_guilds.add(guild_id)
                return True
            
            # Initialize guild filters if not exists
            if guild_id not in self.active_filters:
                self.active_filters[guild_id] = {}
            
            success_count = 0
            for filter_name, filter_config in saved_filters.items():
                try:
                    # Recreate filter instance from saved config
                    filter_instance = self._deserialize_filter_instance(filter_name, filter_config)
                    if filter_instance:
                        self.active_filters[guild_id][filter_name] = filter_instance
                        success_count += 1
                        logger.debug(f"Loaded filter '{filter_name}' for guild {guild_id}")
                    
                except Exception as e:
                    logger.error(f"Error loading filter '{filter_name}' for guild {guild_id}: {e}")
            
            logger.info(f"Loaded {success_count}/{len(saved_filters)} filters for guild {guild_id}")
            self._loaded_guilds.add(guild_id)
            return success_count > 0
            
        except Exception as e:
            logger.error(f"Error loading guild filters for guild {guild_id}: {e}")
            return False
    
    def _serialize_filter_instance(self, filter_instance: object) -> dict:
        """Serialize filter instance to dictionary for database storage."""
        try:
            filter_config = {"type": type(filter_instance).__name__}
            
            # Extract parameters from different filter types
            if isinstance(filter_instance, BassBoostFilter):
                filter_config["level"] = filter_instance.level
            elif isinstance(filter_instance, ReverbFilter):
                filter_config["room_size"] = filter_instance.room_size
                filter_config["damping"] = filter_instance.damping
            elif isinstance(filter_instance, SlowFilter):
                filter_config["speed"] = filter_instance.speed
                filter_config["pitch"] = filter_instance.pitch
            elif isinstance(filter_instance, SpatialAudioFilter):
                filter_config["intensity"] = getattr(filter_instance, 'intensity', 0.5)
            
            return filter_config
            
        except Exception as e:
            logger.error(f"Error serializing filter instance: {e}")
            return {"type": "unknown"}
    
    def _deserialize_filter_instance(self, filter_name: str, filter_config: dict) -> Optional[object]:
        """Deserialize filter instance from database configuration."""
        try:
            if filter_name not in self.available_filters:
                logger.warning(f"Unknown filter name in database: {filter_name}")
                return None
            
            filter_class = self.available_filters[filter_name]
            
            # Handle lambda functions (nightcore, vaporwave)
            if callable(filter_class) and not isinstance(filter_class, type):
                return filter_class()
            
            # Create instance with saved parameters
            if filter_name == "bass_boost":
                level = filter_config.get("level", 5)
                return BassBoostFilter(level=level)
            elif filter_name == "reverb":
                room_size = filter_config.get("room_size", 0.5)
                damping = filter_config.get("damping", 0.5)
                return ReverbFilter(room_size=room_size, damping=damping)
            elif filter_name == "slow":
                speed = filter_config.get("speed", 0.8)
                pitch = filter_config.get("pitch", 1.0)
                return SlowFilter(speed=speed, pitch=pitch)
            elif filter_name == "8d":
                intensity = filter_config.get("intensity", 0.5)
                return SpatialAudioFilter(intensity=intensity)
            else:
                # Default instantiation
                return filter_class()
                
        except Exception as e:
            logger.error(f"Error deserializing filter '{filter_name}': {e}")
            return None