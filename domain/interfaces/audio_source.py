from abc import ABC, abstractmethod
from typing import List, Optional

from domain.entities.track import Track


class AudioSource(ABC):
    """Interface for audio source providers (YouTube, Spotify, etc.)."""
    
    @abstractmethod
    async def search(self, query: str, max_results: int = 5) -> List[Track]:
        """Search for tracks using the given query."""
        pass
    
    @abstractmethod
    async def get_track_info(self, url: str, requester_id: int) -> Optional[Track]:
        """Get track information from a URL."""
        pass
    
    @abstractmethod
    async def get_stream_url(self, track: Track) -> Optional[str]:
        """Get the streaming URL for a track."""
        pass
    
    @abstractmethod
    def is_supported_url(self, url: str) -> bool:
        """Check if the given URL is supported by this source."""
        pass