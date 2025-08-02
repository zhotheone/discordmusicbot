"""Shared manager instances for consistent state across all cogs."""

from typing import Dict
from utils.config_manager import ConfigManager
from utils.advanced_filters import AdvancedFilterManager


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
            
            # Mark as initialized to prevent re-initialization
            SharedManagers._initialized = True
    
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