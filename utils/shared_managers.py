"""Shared manager instances for consistent state across all cogs."""

from typing import Dict
from utils.config_manager import ConfigManager
from utils.advanced_filters import AdvancedFilterManager
from utils.user_settings_manager import user_settings_manager

class SharedManagers:
    """Singleton class to provide shared manager instances across all cogs."""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SharedManagers, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            # Shared ConfigManager instance
            self.config_manager = ConfigManager()
            
            # Shared AdvancedFilterManager instances per guild
            self.guild_filter_managers: Dict[int, AdvancedFilterManager] = {}
            
            # Initialize services with lazy loading to avoid circular imports
            self._music_service = None
            self._filter_service = None
            self._playback_service = None
            
            # User settings manager (global instance)
            self.user_settings_manager = user_settings_manager
            
            # Mark as initialized to prevent re-initialization
            SharedManagers._initialized = True
    
    @property
    def music_service(self):
        """Lazy load music service to avoid circular imports."""
        if self._music_service is None:
            from services.music_service import MusicService
            self._music_service = MusicService(self)
        return self._music_service
    
    @property
    def filter_service(self):
        """Lazy load filter service to avoid circular imports."""
        if self._filter_service is None:
            from services.filter_service import FilterService
            self._filter_service = FilterService(self)
        return self._filter_service
    
    @property 
    def playback_service(self):
        """Lazy load playback service to avoid circular imports."""
        if self._playback_service is None:
            from services.playback_service import PlaybackService
            self._playback_service = PlaybackService(self)
        return self._playback_service
    
    def get_filter_manager(self, guild_id: int) -> AdvancedFilterManager:
        """Get or create advanced filter manager for a guild."""
        if guild_id not in self.guild_filter_managers:
            self.guild_filter_managers[guild_id] = AdvancedFilterManager()
            # Load saved state if exists
            config = self.config_manager.get_config(guild_id)
            if config.get("advanced_filters"):
                # TODO: Implement state restoration from config
                pass
        return self.guild_filter_managers[guild_id]
    
    def save_filter_state(self, guild_id: int):
        """Save current filter state to config."""
        if guild_id in self.guild_filter_managers:
            config = self.config_manager.get_config(guild_id)
            config["advanced_filters"] = self.guild_filter_managers[guild_id].to_dict()
            self.config_manager.save_config(guild_id, config)


# Global shared managers instance
shared_managers = SharedManagers() 