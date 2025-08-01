"""Configuration management for Discord bot guilds."""
import json
import os

class ConfigManager:
    """Manages JSON configuration files for each guild."""
    
    def __init__(self):
        """Initialize the configuration manager."""
        self.config_dir = "configs"
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir)

    def _get_path(self, guild_id: int) -> str:
        """Get the file path for a guild's configuration."""
        return os.path.join(self.config_dir, f"{guild_id}.json")

    def get_config(self, guild_id: int) -> dict:
        """Get the configuration for a guild."""
        config_path = self._get_path(guild_id)
        if not os.path.exists(config_path):
            default_config = {
                "volume": 75,
                "active_filter": "none",  # Keep for backward compatibility
                "queue": [],
                "repeat_mode": "off",  # "off", "song", "queue"
                "advanced_filters": {}  # Store advanced filter manager state
            }
            self.save_config(guild_id, default_config)
            return default_config
        
        with open(config_path, 'r', encoding='utf-8') as f:
            # Check if old config needs updating
            config = json.load(f)
            if "active_filter" not in config:
                config["active_filter"] = "none"
                self.save_config(guild_id, config)
            if "repeat_mode" not in config:
                config["repeat_mode"] = "off"
                self.save_config(guild_id, config)
            if "advanced_filters" not in config:
                config["advanced_filters"] = {}
                self.save_config(guild_id, config)
            return config

    def save_config(self, guild_id: int, data: dict):
        """Save the configuration for a guild."""
        with open(self._get_path(guild_id), 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
