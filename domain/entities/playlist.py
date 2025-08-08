from dataclasses import dataclass, field
from typing import List, Optional, Iterator
from collections import deque
from enum import Enum

from domain.entities.track import Track


class RepeatMode(Enum):
    OFF = "off"
    TRACK = "track"
    QUEUE = "queue"


@dataclass
class Playlist:
    """Represents a music playlist/queue."""
    
    guild_id: int
    tracks: deque = field(default_factory=deque)
    current_index: int = -1
    repeat_mode: RepeatMode = RepeatMode.OFF
    shuffle: bool = False
    history: List[Track] = field(default_factory=list)
    max_size: int = 100
    
    def add_track(self, track: Track, position: Optional[int] = None) -> None:
        """Add a track to the playlist."""
        if len(self.tracks) >= self.max_size:
            raise ValueError(f"Playlist is full (max {self.max_size} tracks)")
        
        if position is None:
            self.tracks.append(track)
        else:
            # Convert deque to list, insert, then back to deque
            track_list = list(self.tracks)
            track_list.insert(position, track)
            self.tracks = deque(track_list)
    
    def remove_track(self, index: int) -> Optional[Track]:
        """Remove a track by index."""
        if not 0 <= index < len(self.tracks):
            return None
        
        track_list = list(self.tracks)
        removed_track = track_list.pop(index)
        self.tracks = deque(track_list)
        
        # Adjust current index if necessary
        if index <= self.current_index:
            self.current_index -= 1
        
        return removed_track
    
    def get_current_track(self) -> Optional[Track]:
        """Get the currently playing track."""
        if self.current_index == -1 or not self.tracks:
            return None
        
        try:
            return list(self.tracks)[self.current_index]
        except IndexError:
            return None
    
    def next_track(self) -> Optional[Track]:
        """Move to and return the next track."""
        if not self.tracks:
            return None
        
        current_track = self.get_current_track()
        
        # Handle repeat modes
        if self.repeat_mode == RepeatMode.TRACK:
            return current_track
        
        # Move to next track
        if self.current_index + 1 < len(self.tracks):
            self.current_index += 1
        elif self.repeat_mode == RepeatMode.QUEUE:
            self.current_index = 0
        else:
            # End of queue
            return None
        
        # Add to history
        if current_track and current_track not in self.history[-5:]:
            self.history.append(current_track)
            if len(self.history) > 50:  # Keep last 50 tracks
                self.history.pop(0)
        
        return self.get_current_track()
    
    def previous_track(self) -> Optional[Track]:
        """Move to and return the previous track."""
        if not self.tracks or self.current_index <= 0:
            return None
        
        self.current_index -= 1
        return self.get_current_track()
    
    def skip_to(self, index: int) -> Optional[Track]:
        """Skip to a specific track by index."""
        if not 0 <= index < len(self.tracks):
            return None
        
        self.current_index = index
        return self.get_current_track()
    
    def clear(self) -> None:
        """Clear all tracks from the playlist."""
        self.tracks.clear()
        self.current_index = -1
    
    def shuffle_tracks(self) -> None:
        """Shuffle the remaining tracks in the queue."""
        if len(self.tracks) <= 1:
            return
        
        import random
        track_list = list(self.tracks)
        
        # Keep current track at the beginning if playing
        if self.current_index >= 0:
            current_track = track_list.pop(self.current_index)
            random.shuffle(track_list)
            track_list.insert(0, current_track)
            self.current_index = 0
        else:
            random.shuffle(track_list)
        
        self.tracks = deque(track_list)
        self.shuffle = True
    
    def get_queue_display(self, max_tracks: int = 10) -> List[str]:
        """Get formatted queue display."""
        if not self.tracks:
            return ["Queue is empty"]
        
        queue_display = []
        track_list = list(self.tracks)
        
        for i, track in enumerate(track_list[:max_tracks]):
            prefix = "▶️" if i == self.current_index else f"{i + 1}."
            queue_display.append(f"{prefix} {track.display_title} [{track.duration_formatted}]")
        
        if len(track_list) > max_tracks:
            queue_display.append(f"... and {len(track_list) - max_tracks} more tracks")
        
        return queue_display
    
    def __len__(self) -> int:
        """Return the number of tracks in the playlist."""
        return len(self.tracks)
    
    def __bool__(self) -> bool:
        """Return True if playlist has tracks."""
        return bool(self.tracks)
    
    def __iter__(self) -> Iterator[Track]:
        """Iterate over tracks in the playlist."""
        return iter(self.tracks)