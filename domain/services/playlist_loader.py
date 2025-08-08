import asyncio
import logging
from typing import List, Optional, Dict, Any, Callable
from dataclasses import dataclass
from enum import Enum

from core.dependency_injection import DIContainer
from core.events import EventBus
from domain.entities.track import Track
from domain.services.music_service import MusicService
from domain.services.user_service import UserService
from infrastructure.audio.sources.youtube import YouTubeSource

logger = logging.getLogger(__name__)


class LoadingStatus(Enum):
    PENDING = "pending"
    LOADING = "loading"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class PlaylistLoadingTask:
    """Represents a playlist loading task."""
    guild_id: int
    playlist_url: str
    requester_id: int
    max_tracks: int
    voice_client: Optional[Any]
    total_entries: int = 0
    loaded_tracks: List[Track] = None
    raw_entries: List[Dict[str, Any]] = None
    status: LoadingStatus = LoadingStatus.PENDING
    current_index: int = 0
    initial_batch_size: int = 5
    ahead_loading_size: int = 5
    
    def __post_init__(self):
        if self.loaded_tracks is None:
            self.loaded_tracks = []
        if self.raw_entries is None:
            self.raw_entries = []


class PlaylistLoaderService:
    """Service for progressive playlist loading."""
    
    def __init__(self, container: DIContainer, event_bus: EventBus):
        self.container = container
        self.event_bus = event_bus
        self.music_service: MusicService = container.get(MusicService)
        self.user_service: UserService = container.get(UserService)
        self.youtube_source = YouTubeSource()
        
        # Active loading tasks by guild_id
        self.loading_tasks: Dict[int, PlaylistLoadingTask] = {}
        
        # Subscribe to track events to trigger ahead-loading
        self.event_bus.subscribe("track_started", self._on_track_started)
        self.event_bus.subscribe("track_ended", self._on_track_ended)
    
    async def start_playlist_loading(
        self, 
        guild_id: int, 
        playlist_url: str, 
        requester_id: int, 
        voice_client: Optional[Any],
        max_tracks: int = 50,
        progress_callback: Optional[Callable] = None
    ) -> PlaylistLoadingTask:
        """Start progressive playlist loading."""
        try:
            logger.info(f"Starting progressive playlist loading for guild {guild_id}")
            
            # Create loading task
            task = PlaylistLoadingTask(
                guild_id=guild_id,
                playlist_url=playlist_url,
                requester_id=requester_id,
                max_tracks=max_tracks,
                voice_client=voice_client
            )
            
            self.loading_tasks[guild_id] = task
            task.status = LoadingStatus.LOADING
            
            # First, extract raw playlist entries (metadata only)
            await self._extract_playlist_entries(task)
            
            if not task.raw_entries:
                task.status = LoadingStatus.FAILED
                logger.error(f"No entries found in playlist for guild {guild_id}")
                return task
            
            logger.info(f"Found {len(task.raw_entries)} entries, loading initial batch of {task.initial_batch_size}")
            
            # Load initial batch (first 5 tracks)
            initial_tracks = await self._load_track_batch(task, 0, task.initial_batch_size)
            
            if not initial_tracks:
                task.status = LoadingStatus.FAILED
                logger.error(f"Failed to load initial batch for guild {guild_id}")
                return task
            
            # Add initial tracks to queue immediately
            for track in initial_tracks:
                success = await self.music_service.play(guild_id, track, voice_client)
                if success:
                    await self.user_service.add_to_history(requester_id, track)
                    task.loaded_tracks.append(track)
            
            # Start background loading for remaining tracks
            asyncio.create_task(self._background_loading_worker(task, progress_callback))
            
            logger.info(f"Started playback with {len(initial_tracks)} tracks, continuing background loading")
            return task
            
        except Exception as e:
            logger.error(f"Error starting playlist loading for guild {guild_id}: {e}")
            if guild_id in self.loading_tasks:
                self.loading_tasks[guild_id].status = LoadingStatus.FAILED
            raise
    
    async def _extract_playlist_entries(self, task: PlaylistLoadingTask) -> None:
        """Extract raw playlist entries (metadata only, fast)."""
        try:
            # Use extract_flat=True for fast metadata extraction
            playlist_options = self.youtube_source.ytdl_options.copy()
            playlist_options['noplaylist'] = False
            playlist_options['playlistend'] = task.max_tracks
            playlist_options['extract_flat'] = True  # Fast extraction, metadata only
            playlist_options['ignoreerrors'] = True
            
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(
                None,
                self.youtube_source._extract_playlist_sync,
                task.playlist_url,
                playlist_options
            )
            
            if info and 'entries' in info:
                # Filter out None entries
                task.raw_entries = [entry for entry in info['entries'] if entry is not None]
                task.total_entries = len(task.raw_entries)
                logger.info(f"Extracted {task.total_entries} playlist entries")
            else:
                logger.warning("No entries found in playlist info")
                
        except Exception as e:
            logger.error(f"Error extracting playlist entries: {e}")
    
    async def _load_track_batch(self, task: PlaylistLoadingTask, start_idx: int, batch_size: int) -> List[Track]:
        """Load a batch of tracks from raw entries."""
        try:
            end_idx = min(start_idx + batch_size, len(task.raw_entries))
            batch_entries = task.raw_entries[start_idx:end_idx]
            
            tracks = []
            for entry in batch_entries:
                try:
                    # Convert entry to full track info
                    if entry.get('url'):
                        # Entry has direct URL
                        track = await self.youtube_source._create_track_from_entry(entry, task.requester_id)
                    else:
                        # Entry needs full extraction
                        video_url = f"https://www.youtube.com/watch?v={entry['id']}"
                        track = await self.youtube_source.get_track_info(video_url, task.requester_id)
                    
                    if track:
                        tracks.append(track)
                        
                except Exception as e:
                    logger.warning(f"Failed to load track from entry: {e}")
                    continue
            
            logger.debug(f"Loaded {len(tracks)} tracks from batch {start_idx}-{end_idx}")
            return tracks
            
        except Exception as e:
            logger.error(f"Error loading track batch: {e}")
            return []
    
    async def _background_loading_worker(self, task: PlaylistLoadingTask, progress_callback: Optional[Callable] = None):
        """Background worker for loading remaining tracks."""
        try:
            current_idx = task.initial_batch_size
            
            while current_idx < len(task.raw_entries) and task.status == LoadingStatus.LOADING:
                # Load next batch
                batch_tracks = await self._load_track_batch(
                    task, 
                    current_idx, 
                    task.ahead_loading_size
                )
                
                # Add tracks to queue
                for track in batch_tracks:
                    try:
                        success = await self.music_service.play(task.guild_id, track, task.voice_client)
                        if success:
                            await self.user_service.add_to_history(task.requester_id, track)
                            task.loaded_tracks.append(track)
                    except Exception as e:
                        logger.warning(f"Failed to add background track to queue: {e}")
                
                current_idx += task.ahead_loading_size
                
                # Update progress
                if progress_callback:
                    progress = {
                        'loaded': len(task.loaded_tracks),
                        'total': len(task.raw_entries),
                        'percentage': (len(task.loaded_tracks) / len(task.raw_entries)) * 100
                    }
                    asyncio.create_task(progress_callback(progress))
                
                # Small delay to prevent overwhelming
                await asyncio.sleep(0.5)
            
            task.status = LoadingStatus.COMPLETED
            logger.info(f"Background loading completed for guild {task.guild_id}: {len(task.loaded_tracks)} tracks loaded")
            
        except Exception as e:
            logger.error(f"Error in background loading worker: {e}")
            task.status = LoadingStatus.FAILED
    
    async def _on_track_started(self, guild_id: int, track: Track) -> None:
        """Handle track started event - trigger ahead-loading if needed."""
        if guild_id not in self.loading_tasks:
            return
        
        task = self.loading_tasks[guild_id]
        if task.status != LoadingStatus.LOADING:
            return
        
        # Check if we need to load more tracks ahead
        playlist = self.music_service.get_playlist(guild_id)
        if playlist:
            remaining_tracks = len(playlist.tracks) - playlist.current_index
            
            # If we have less than 3 tracks remaining, trigger ahead-loading
            if remaining_tracks < 3:
                logger.debug(f"Low queue for guild {guild_id}, triggering ahead-loading")
    
    async def _on_track_ended(self, guild_id: int, track: Track) -> None:
        """Handle track ended event."""
        # Clean up completed tasks
        if guild_id in self.loading_tasks:
            task = self.loading_tasks[guild_id]
            if task.status == LoadingStatus.COMPLETED:
                playlist = self.music_service.get_playlist(guild_id)
                if not playlist or not playlist.tracks:
                    # Queue is empty, clean up
                    del self.loading_tasks[guild_id]
                    logger.debug(f"Cleaned up completed loading task for guild {guild_id}")
    
    def get_loading_status(self, guild_id: int) -> Optional[PlaylistLoadingTask]:
        """Get current loading status for a guild."""
        return self.loading_tasks.get(guild_id)
    
    def cancel_loading(self, guild_id: int) -> bool:
        """Cancel playlist loading for a guild."""
        if guild_id in self.loading_tasks:
            self.loading_tasks[guild_id].status = LoadingStatus.FAILED
            del self.loading_tasks[guild_id]
            logger.info(f"Cancelled playlist loading for guild {guild_id}")
            return True
        return False