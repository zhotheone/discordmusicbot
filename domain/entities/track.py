from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum


class TrackSource(Enum):
    YOUTUBE = "youtube"
    SPOTIFY = "spotify"
    SOUNDCLOUD = "soundcloud"
    LOCAL = "local"


@dataclass
class Track:
    """Represents a music track."""
    
    title: str
    url: str
    duration: int  # Duration in seconds
    source: TrackSource
    requester_id: int
    thumbnail_url: Optional[str] = None
    artist: Optional[str] = None
    album: Optional[str] = None
    track_id: Optional[str] = None
    created_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
    
    @property
    def display_title(self) -> str:
        """Get formatted display title."""
        if self.artist:
            return f"{self.artist} - {self.title}"
        return self.title
    
    @property
    def duration_formatted(self) -> str:
        """Get formatted duration string."""
        hours, remainder = divmod(self.duration, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert track to dictionary."""
        return {
            "title": self.title,
            "url": self.url,
            "duration": self.duration,
            "source": self.source.value,
            "requester_id": self.requester_id,
            "thumbnail_url": self.thumbnail_url,
            "artist": self.artist,
            "album": self.album,
            "track_id": self.track_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Track":
        """Create track from dictionary."""
        created_at = None
        if data.get("created_at"):
            created_at = datetime.fromisoformat(data["created_at"])
        
        return cls(
            title=data["title"],
            url=data["url"],
            duration=data["duration"],
            source=TrackSource(data["source"]),
            requester_id=data["requester_id"],
            thumbnail_url=data.get("thumbnail_url"),
            artist=data.get("artist"),
            album=data.get("album"),
            track_id=data.get("track_id"),
            created_at=created_at,
            metadata=data.get("metadata", {})
        )