import os
import json

class ConfigManager:
    """Manages JSON configuration files for each guild."""
    def __init__(self):
        self.config_dir = "configs"
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir)

    def _get_path(self, guild_id: int) -> str:
        return os.path.join(self.config_dir, f"{guild_id}.json")

    def get_config(self, guild_id: int) -> dict:
        config_path = self._get_path(guild_id)
        if not os.path.exists(config_path):
            default_config = {
                "volume": 75,
                "active_filter": "none",
                "queue": []
            }
            self.save_config(guild_id, default_config)
            return default_config
        
        with open(config_path, 'r') as f:
            # Check if old config needs updating
            config = json.load(f)
            if "active_filter" not in config:
                config["active_filter"] = "none"
                self.save_config(guild_id, config)
            return config

    def save_config(self, guild_id: int, data: dict):
        with open(self._get_path(guild_id), 'w') as f:
            json.dump(data, f, indent=4)
