"""Filter service for handling audio filter operations independent of Discord commands."""

import logging
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

log = logging.getLogger(__name__)

class FilterToggleResult(Enum):
    ENABLED = "enabled"
    DISABLED = "disabled" 
    ERROR = "error"

@dataclass
class FilterState:
    """Data class for filter state information."""
    name: str
    is_active: bool
    display_name: str
    
class FilterService:
    """Service for handling audio filter operations."""
    
    def __init__(self, shared_managers=None):
        """Initialize the filter service."""
        self.shared_managers = shared_managers
        self.config_manager = shared_managers.config_manager if shared_managers else None
    
    def toggle_legacy_filter(self, guild_id: int, filter_name: str) -> Tuple[FilterToggleResult, str]:
        """
        Toggle a legacy filter on or off.
        Returns (result, status_message).
        """
        try:
            config = self.config_manager.get_config(guild_id)
            current_filter = config.get("active_filter", "none")
            display_name = filter_name.capitalize()
            
            if current_filter == filter_name:
                # Filter is active, turn it off
                config["active_filter"] = "none"
                self.config_manager.save_config(guild_id, config)
                
                log.info(f"Disabled '{filter_name}' filter in guild {guild_id}")
                return FilterToggleResult.DISABLED, f"**{display_name}** filter turned **OFF**!"
            else:
                # Filter is not active, turn it on
                config["active_filter"] = filter_name
                self.config_manager.save_config(guild_id, config)
                
                log.info(f"Enabled '{filter_name}' filter in guild {guild_id}")
                return FilterToggleResult.ENABLED, f"**{display_name}** filter turned **ON**!"
                
        except Exception as e:
            log.exception(f"Failed to toggle filter '{filter_name}' in guild {guild_id}")
            return FilterToggleResult.ERROR, f"Failed to toggle {filter_name} filter."
    
    def get_active_legacy_filter(self, guild_id: int) -> str:
        """Get the currently active legacy filter."""
        config = self.config_manager.get_config(guild_id)
        return config.get("active_filter", "none")
    
    def set_volume(self, guild_id: int, volume: int) -> Tuple[bool, str]:
        """
        Set the volume level.
        Returns (success, message).
        """
        if not 0 <= volume <= 150:
            return False, "Volume must be between 0 and 150."
        
        try:
            config = self.config_manager.get_config(guild_id)
            config["volume"] = volume
            self.config_manager.save_config(guild_id, config)
            
            log.info(f"Set volume to {volume} in guild {guild_id}")
            return True, f"Volume set to **{volume}%**"
            
        except Exception as e:
            log.exception(f"Failed to set volume in guild {guild_id}")
            return False, "Failed to set volume."
    
    def get_volume(self, guild_id: int) -> int:
        """Get the current volume level."""
        config = self.config_manager.get_config(guild_id)
        return config.get("volume", 75)
    
    def get_advanced_filter_manager(self, guild_id: int):
        """Get the advanced filter manager for a guild."""
        return self.shared_managers.get_filter_manager(guild_id)
    
    def save_advanced_filter_state(self, guild_id: int):
        """Save advanced filter state."""
        self.shared_managers.save_filter_state(guild_id)
    
    def get_combined_ffmpeg_filter(self, guild_id: int) -> Optional[str]:
        """
        Get the combined FFmpeg filter string for a guild.
        Prioritizes advanced filters over legacy filters.
        """
        # Check for advanced filters first
        filter_manager = self.get_advanced_filter_manager(guild_id)
        advanced_filter = filter_manager.get_combined_ffmpeg_filter()
        
        if advanced_filter:
            return advanced_filter
        
        # Fallback to legacy filter system
        legacy_filter = self.get_active_legacy_filter(guild_id)
        if legacy_filter and legacy_filter != "none":
            # Import here to avoid circular imports
            try:
                from utils.filters import FFMPEG_FILTER_CHAINS
                return FFMPEG_FILTER_CHAINS.get(legacy_filter)
            except ImportError:
                log.warning("Could not import FFMPEG_FILTER_CHAINS")
                return None
        
        return None
    
    def get_filter_status(self, guild_id: int) -> Dict[str, any]:
        """
        Get comprehensive filter status for a guild.
        Returns information about both legacy and advanced filters.
        """
        try:
            legacy_filter = self.get_active_legacy_filter(guild_id)
            volume = self.get_volume(guild_id)
            
            filter_manager = self.get_advanced_filter_manager(guild_id)
            enabled_advanced_filters = filter_manager.get_enabled_filters()
            
            return {
                "legacy_filter": legacy_filter,
                "volume": volume,
                "advanced_filters": enabled_advanced_filters,
                "has_active_filters": (
                    legacy_filter != "none" or 
                    len(enabled_advanced_filters) > 0
                )
            }
        except Exception as e:
            log.exception(f"Failed to get filter status for guild {guild_id}")
            return {
                "legacy_filter": "none",
                "volume": 75,
                "advanced_filters": [],
                "has_active_filters": False
            } 