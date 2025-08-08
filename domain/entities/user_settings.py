from dataclasses import dataclass, field
from typing import List, Dict, Any
from datetime import datetime


@dataclass
class UserSettings:
    """User configuration and preferences."""
    
    user_id: int
    default_volume: float = 0.5
    preferred_filters: List[str] = field(default_factory=list)
    auto_play: bool = False
    repeat_mode: str = "off"  # "off", "track", "queue"
    bass_boost_level: int = 0  # 0-10
    custom_settings: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def update_volume(self, volume: float) -> None:
        """Update user volume preference."""
        if not 0.0 <= volume <= 1.0:
            raise ValueError("Volume must be between 0.0 and 1.0")
        self.default_volume = volume
        self.updated_at = datetime.utcnow()
    
    def add_filter(self, filter_name: str) -> None:
        """Add a filter to user preferences."""
        if filter_name not in self.preferred_filters:
            self.preferred_filters.append(filter_name)
            self.updated_at = datetime.utcnow()
    
    def remove_filter(self, filter_name: str) -> None:
        """Remove a filter from user preferences."""
        if filter_name in self.preferred_filters:
            self.preferred_filters.remove(filter_name)
            self.updated_at = datetime.utcnow()
    
    def set_repeat_mode(self, mode: str) -> None:
        """Set repeat mode."""
        if mode not in ["off", "track", "queue"]:
            raise ValueError("Invalid repeat mode")
        self.repeat_mode = mode
        self.updated_at = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "user_id": self.user_id,
            "default_volume": self.default_volume,
            "preferred_filters": self.preferred_filters,
            "auto_play": self.auto_play,
            "repeat_mode": self.repeat_mode,
            "bass_boost_level": self.bass_boost_level,
            "custom_settings": self.custom_settings,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserSettings":
        """Create from dictionary."""
        return cls(
            user_id=data["user_id"],
            default_volume=data.get("default_volume", 0.5),
            preferred_filters=data.get("preferred_filters", []),
            auto_play=data.get("auto_play", False),
            repeat_mode=data.get("repeat_mode", "off"),
            bass_boost_level=data.get("bass_boost_level", 0),
            custom_settings=data.get("custom_settings", {}),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.utcnow(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else datetime.utcnow()
        )