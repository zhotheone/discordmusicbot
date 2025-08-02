"""Music service for handling music operations independent of Discord commands."""

import logging
import yt_dlp
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

log = logging.getLogger(__name__)

# YTDL Configuration
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'outtmpl': 'downloads/%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': False,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'
}

class RepeatMode(Enum):
    OFF = "off"
    SONG = "song" 
    QUEUE = "queue"

@dataclass
class SongInfo:
    """Data class for song information."""
    title: str
    url: str
    duration: Optional[int] = None
    thumbnail: Optional[str] = None
    uploader: Optional[str] = None
    webpage_url: Optional[str] = None

@dataclass
class PlaybackState:
    """Data class for current playback state."""
    current_song: Optional[SongInfo] = None
    queue: List[SongInfo] = None
    repeat_mode: RepeatMode = RepeatMode.OFF
    volume: int = 75
    is_playing: bool = False
    is_paused: bool = False
    
    def __post_init__(self):
        if self.queue is None:
            self.queue = []

class MusicService:
    """Service for handling music operations."""
    
    def __init__(self, shared_managers=None):
        """Initialize the music service."""
        self.shared_managers = shared_managers
        self.config_manager = shared_managers.config_manager if shared_managers else None
        self._playback_states: Dict[int, PlaybackState] = {}
        self._original_queues: Dict[int, List[SongInfo]] = {}
        
        # Suppress yt_dlp bug reports
        yt_dlp.utils.bug_reports_message = lambda *args, **kwargs: ''
    
    def get_playback_state(self, guild_id: int) -> PlaybackState:
        """Get or create playback state for a guild."""
        if guild_id not in self._playback_states:
            # Load from config
            config = self.config_manager.get_config(guild_id)
            self._playback_states[guild_id] = PlaybackState(
                queue=[SongInfo(**song) for song in config.get("queue", [])],
                repeat_mode=RepeatMode(config.get("repeat_mode", "off")),
                volume=config.get("volume", 75)
            )
        return self._playback_states[guild_id]
    
    def save_playback_state(self, guild_id: int):
        """Save current playback state to config."""
        if guild_id in self._playback_states:
            state = self._playback_states[guild_id]
            config = self.config_manager.get_config(guild_id)
            
            # Convert SongInfo objects to dicts for JSON serialization
            config["queue"] = [
                {
                    "title": song.title,
                    "url": song.url,
                    "duration": song.duration,
                    "thumbnail": song.thumbnail,
                    "uploader": song.uploader,
                    "webpage_url": song.webpage_url
                }
                for song in state.queue
            ]
            config["repeat_mode"] = state.repeat_mode.value
            config["volume"] = state.volume
            
            self.config_manager.save_config(guild_id, config)
    
    async def search_music(self, query: str) -> Optional[SongInfo]:
        """Search for music using yt-dlp."""
        try:
            with yt_dlp.YoutubeDL(YTDL_OPTIONS) as ydl:
                search_query = f"ytsearch:{query}" if not query.startswith('http') else query
                info = ydl.extract_info(search_query, download=False)
                
                if 'entries' in info and info['entries']:
                    entry = info['entries'][0]
                else:
                    entry = info
                
                return SongInfo(
                    title=entry.get('title', 'Unknown Title'),
                    url=entry.get('url', ''),
                    duration=entry.get('duration'),
                    thumbnail=entry.get('thumbnail'),
                    uploader=entry.get('uploader'),
                    webpage_url=entry.get('webpage_url')
                )
        except Exception as e:
            log.exception(f"Failed to search music for query: '{query}'")
            return None
    
    def add_to_queue(self, guild_id: int, song: SongInfo) -> bool:
        """Add a song to the queue."""
        try:
            state = self.get_playback_state(guild_id)
            state.queue.append(song)
            self.save_playback_state(guild_id)
            log.info(f"Added '{song.title}' to queue in guild {guild_id}")
            return True
        except Exception as e:
            log.exception(f"Failed to add song to queue in guild {guild_id}")
            return False
    
    def get_next_song(self, guild_id: int) -> Optional[SongInfo]:
        """Get the next song to play based on queue and repeat mode."""
        state = self.get_playback_state(guild_id)
        
        if state.repeat_mode == RepeatMode.SONG and state.current_song:
            return state.current_song
        
        if state.queue:
            next_song = state.queue.pop(0)
            
            # Handle queue repeat mode
            if state.repeat_mode == RepeatMode.QUEUE:
                # Store original queue on first iteration
                if guild_id not in self._original_queues and state.current_song:
                    self._original_queues[guild_id] = [state.current_song] + state.queue.copy()
                
                # If queue is empty after popping, restore it
                if not state.queue:
                    if guild_id in self._original_queues:
                        state.queue = self._original_queues[guild_id].copy()[1:]  # Exclude current song
            
            self.save_playback_state(guild_id)
            return next_song
        
        return None
    
    def set_current_song(self, guild_id: int, song: SongInfo):
        """Set the currently playing song."""
        state = self.get_playback_state(guild_id)
        state.current_song = song
        state.is_playing = True
        state.is_paused = False
    
    def set_playback_state(self, guild_id: int, is_playing: bool, is_paused: bool):
        """Update playback state."""
        state = self.get_playback_state(guild_id)
        state.is_playing = is_playing
        state.is_paused = is_paused
    
    def clear_current_song(self, guild_id: int):
        """Clear the current song."""
        state = self.get_playback_state(guild_id)
        state.current_song = None
        state.is_playing = False
        state.is_paused = False
    
    def clear_queue(self, guild_id: int):
        """Clear the entire queue."""
        state = self.get_playback_state(guild_id)
        state.queue.clear()
        if guild_id in self._original_queues:
            del self._original_queues[guild_id]
        self.save_playback_state(guild_id)
    
    def set_repeat_mode(self, guild_id: int, mode: RepeatMode):
        """Set the repeat mode."""
        state = self.get_playback_state(guild_id)
        state.repeat_mode = mode
        self.save_playback_state(guild_id)
    
    def set_volume(self, guild_id: int, volume: int) -> bool:
        """Set the volume (0-150)."""
        if not 0 <= volume <= 150:
            return False
        
        state = self.get_playback_state(guild_id)
        state.volume = volume
        self.save_playback_state(guild_id)
        return True
    
    def get_queue_info(self, guild_id: int) -> Dict[str, Any]:
        """Get queue information for display."""
        state = self.get_playback_state(guild_id)
        return {
            "current_song": state.current_song,
            "queue": state.queue,
            "queue_length": len(state.queue),
            "repeat_mode": state.repeat_mode,
            "volume": state.volume,
            "is_playing": state.is_playing,
            "is_paused": state.is_paused
        } 