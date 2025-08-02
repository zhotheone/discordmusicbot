"""User settings management for Discord bot - saves and loads user preferences."""
import json
import os
import logging
from typing import Dict, Any, Optional
from services.music_service import RepeatMode

log = logging.getLogger(__name__)

class UserSettingsManager:
    """Manages user-specific settings like preferred filters, volume, etc."""
    
    def __init__(self, settings_file: str = "user_settings.json"):
        """Initialize the user settings manager."""
        self.settings_file = settings_file
        self.settings_dir = "configs"
        self.full_path = os.path.join(self.settings_dir, self.settings_file)
        
        # Ensure configs directory exists
        if not os.path.exists(self.settings_dir):
            os.makedirs(self.settings_dir)
            log.info(f"Created settings directory: {self.settings_dir}")
        
        # Load existing settings or create new file
        self.settings = self._load_settings()
    
    def _load_settings(self) -> Dict[str, Dict[str, Any]]:
        """Load settings from JSON file, create if doesn't exist."""
        if not os.path.exists(self.full_path):
            log.info(f"Settings file {self.full_path} doesn't exist, creating new one")
            default_settings = {}
            self._save_settings(default_settings)
            return default_settings
        
        try:
            with open(self.full_path, 'r', encoding='utf-8') as f:
                settings = json.load(f)
                log.info(f"Loaded user settings from {self.full_path}")
                return settings
        except (json.JSONDecodeError, FileNotFoundError) as e:
            log.warning(f"Failed to load settings file: {e}. Creating new one.")
            default_settings = {}
            self._save_settings(default_settings)
            return default_settings
    
    def _save_settings(self, settings: Dict[str, Dict[str, Any]]):
        """Save settings to JSON file."""
        try:
            with open(self.full_path, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=4, ensure_ascii=False)
            log.debug(f"Saved user settings to {self.full_path}")
        except Exception as e:
            log.error(f"Failed to save settings: {e}")
    
    def get_user_settings(self, user_id: int) -> Dict[str, Any]:
        """Get settings for a specific user."""
        user_key = str(user_id)
        if user_key not in self.settings:
            # Create default settings for new user
            self.settings[user_key] = {
                "volume": 75,
                "repeat_mode": "off",
                "filters": {},
                "last_used": None  # Timestamp of last use
            }
            self._save_settings(self.settings)
            log.info(f"Created default settings for user {user_id}")
        
        return self.settings[user_key].copy()
    
    def save_user_volume(self, user_id: int, volume: int):
        """Save user's preferred volume."""
        user_key = str(user_id)
        user_settings = self.get_user_settings(user_id)
        user_settings["volume"] = volume
        user_settings["last_used"] = self._get_timestamp()
        
        self.settings[user_key] = user_settings
        self._save_settings(self.settings)
        log.info(f"Saved volume {volume} for user {user_id}")
    
    def save_user_repeat_mode(self, user_id: int, repeat_mode: RepeatMode):
        """Save user's preferred repeat mode."""
        user_key = str(user_id)
        user_settings = self.get_user_settings(user_id)
        user_settings["repeat_mode"] = repeat_mode.value
        user_settings["last_used"] = self._get_timestamp()
        
        self.settings[user_key] = user_settings
        self._save_settings(self.settings)
        log.info(f"Saved repeat mode {repeat_mode.value} for user {user_id}")
    
    def save_user_filters(self, user_id: int, filter_states: Dict[str, Dict[str, Any]]):
        """Save user's filter preferences.
        
        Args:
            user_id: Discord user ID
            filter_states: Dict with filter names as keys and their state/parameters as values
                          Format: {"bassboost": {"enabled": True, "parameters": {...}}}
        """
        user_key = str(user_id)
        user_settings = self.get_user_settings(user_id)
        user_settings["filters"] = filter_states
        user_settings["last_used"] = self._get_timestamp()
        
        self.settings[user_key] = user_settings
        self._save_settings(self.settings)
        log.info(f"Saved filter preferences for user {user_id}: {list(filter_states.keys())}")
    
    def get_user_volume(self, user_id: int) -> int:
        """Get user's preferred volume."""
        return self.get_user_settings(user_id).get("volume", 75)
    
    def get_user_repeat_mode(self, user_id: int) -> RepeatMode:
        """Get user's preferred repeat mode."""
        mode_str = self.get_user_settings(user_id).get("repeat_mode", "off")
        try:
            return RepeatMode(mode_str)
        except ValueError:
            return RepeatMode.OFF
    
    def get_user_filters(self, user_id: int) -> Dict[str, Dict[str, Any]]:
        """Get user's filter preferences."""
        return self.get_user_settings(user_id).get("filters", {})
    
    def apply_user_preferences(self, user_id: int, guild_id: int, music_service, filter_manager=None):
        """Apply user's saved preferences to the current session.
        
        Args:
            user_id: Discord user ID
            guild_id: Discord guild ID
            music_service: MusicService instance
            filter_manager: AdvancedFilterManager instance (optional)
        """
        user_settings = self.get_user_settings(user_id)
        
        # Apply volume
        volume = user_settings.get("volume", 75)
        music_service.set_volume(guild_id, volume)
        log.info(f"Applied saved volume {volume} for user {user_id} in guild {guild_id}")
        
        # Apply repeat mode
        repeat_mode = self.get_user_repeat_mode(user_id)
        music_service.set_repeat_mode(guild_id, repeat_mode)
        log.info(f"Applied saved repeat mode {repeat_mode.value} for user {user_id} in guild {guild_id}")
        
        # Apply filters if filter manager is provided
        if filter_manager:
            saved_filters = user_settings.get("filters", {})
            for filter_name, filter_data in saved_filters.items():
                if filter_data.get("enabled", False):
                    # Enable the filter
                    filter_manager.enable_filter(filter_name)
                    
                    # Apply saved parameters if available
                    if "parameters" in filter_data:
                        for param_name, param_value in filter_data["parameters"].items():
                            filter_manager.set_filter_parameter(filter_name, param_name, param_value)
                    
                    log.info(f"Applied saved filter {filter_name} for user {user_id}")
                else:
                    filter_manager.disable_filter(filter_name)
    
    def get_user_filter_defaults(self, user_id: int) -> Dict[str, bool]:
        """Get which filters should be enabled by default for this user."""
        saved_filters = self.get_user_filters(user_id)
        return {
            filter_name: filter_data.get("enabled", False)
            for filter_name, filter_data in saved_filters.items()
        }
    
    def clear_user_settings(self, user_id: int):
        """Clear all settings for a user."""
        user_key = str(user_id)
        if user_key in self.settings:
            del self.settings[user_key]
            self._save_settings(self.settings)
            log.info(f"Cleared all settings for user {user_id}")
    
    def get_all_users_with_settings(self) -> list:
        """Get list of all user IDs that have saved settings."""
        return [int(user_id) for user_id in self.settings.keys()]
    
    def _get_timestamp(self) -> str:
        """Get current timestamp as ISO string."""
        from datetime import datetime
        return datetime.now().isoformat()
    
    def cleanup_old_settings(self, days_old: int = 90):
        """Remove settings for users who haven't used the bot in X days."""
        from datetime import datetime, timedelta
        
        cutoff_date = datetime.now() - timedelta(days=days_old)
        users_to_remove = []
        
        for user_id, settings in self.settings.items():
            last_used = settings.get("last_used")
            if last_used:
                try:
                    last_used_date = datetime.fromisoformat(last_used)
                    if last_used_date < cutoff_date:
                        users_to_remove.append(user_id)
                except ValueError:
                    # Invalid timestamp, mark for removal
                    users_to_remove.append(user_id)
            else:
                # No timestamp, mark for removal
                users_to_remove.append(user_id)
        
        for user_id in users_to_remove:
            del self.settings[user_id]
        
        if users_to_remove:
            self._save_settings(self.settings)
            log.info(f"Cleaned up settings for {len(users_to_remove)} inactive users")
        
        return len(users_to_remove)


# Global instance
user_settings_manager = UserSettingsManager() 