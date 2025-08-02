"""Playback service for coordinating Discord voice playback with business logic."""

import discord
import logging
import asyncio
from typing import Dict, Any

log = logging.getLogger(__name__)

# FFMPEG Base Options
FFMPEG_OPTIONS_BASE = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

class PlaybackService:
    """Service for coordinating Discord voice playback."""
    
    def __init__(self, shared_managers=None):
        """Initialize the playback service."""
        self.shared_managers = shared_managers
        self._current_songs: Dict[int, Any] = {}  # Store current song info per guild
    
    def _get_music_service(self):
        """Get music service from shared managers, avoiding circular references."""
        if not self.shared_managers:
            return None
        # Access the private attribute directly to avoid triggering circular property access
        if self.shared_managers._music_service is None:
            from services.music_service import MusicService
            self.shared_managers._music_service = MusicService(self.shared_managers)
        return self.shared_managers._music_service
    
    def _get_filter_service(self):
        """Get filter service from shared managers, avoiding circular references."""
        if not self.shared_managers:
            return None
        # Access the private attribute directly to avoid triggering circular property access
        if self.shared_managers._filter_service is None:
            from services.filter_service import FilterService
            self.shared_managers._filter_service = FilterService(self.shared_managers)
        return self.shared_managers._filter_service
    
    async def play_song(self, guild_id: int, voice_client, after_callback=None) -> bool:
        """
        Play the next song in queue for a guild.
        Returns True if a song was played, False if queue is empty.
        """
        try:
            # Get next song from music service
            song = self._get_music_service().get_next_song(guild_id)
            if not song:
                # No more songs in queue
                self._get_music_service().clear_current_song(guild_id)
                return False
            
            # Set as current song
            self._get_music_service().set_current_song(guild_id, song)
            self._current_songs[guild_id] = song
            
            # Get audio source with filters applied
            audio_source = await self._create_audio_source(guild_id, song)
            if not audio_source:
                return False
            
            # Start playback
            voice_client.play(audio_source, after=after_callback)
            
            log.info(f"Started playing '{song.title}' in guild {guild_id}")
            return True
            
        except Exception as e:
            log.exception(f"Failed to play song in guild {guild_id}")
            return False
    
    async def _create_audio_source(self, guild_id: int, song):
        """Create Discord audio source with filters and volume applied."""
        try:
            # Get base FFmpeg options
            ffmpeg_options = FFMPEG_OPTIONS_BASE.copy()
            
            # Apply filters
            filter_string = self._get_filter_service().get_combined_ffmpeg_filter(guild_id)
            if filter_string:
                ffmpeg_options['options'] += f' -af "{filter_string}"'
                log.info(f"Guild {guild_id} - Applied filters: {filter_string}")
            
            # Create audio source
            player = discord.FFmpegPCMAudio(song.url, **ffmpeg_options)
            
            # Apply volume
            volume = self._get_filter_service().get_volume(guild_id)
            source = discord.PCMVolumeTransformer(player, volume=volume / 100.0)
            
            log.info(f"Guild {guild_id} - Created audio source with volume {volume}%")
            return source
            
        except Exception as e:
            log.exception(f"Failed to create audio source for guild {guild_id}")
            return None
    
    def get_current_song(self, guild_id: int):
        """Get the currently playing song for a guild."""
        return self._current_songs.get(guild_id)
    
    def set_playback_state(self, guild_id: int, is_playing: bool, is_paused: bool):
        """Update playback state in music service."""
        self._get_music_service().set_playback_state(guild_id, is_playing, is_paused)
    
    def clear_current_song(self, guild_id: int):
        """Clear current song info."""
        if guild_id in self._current_songs:
            del self._current_songs[guild_id]
        self._get_music_service().clear_current_song(guild_id)
    
    async def apply_filters_to_current_song(self, guild_id: int, voice_client) -> bool:
        """
        Apply current filter settings to the currently playing song by restarting playback.
        Returns True if filters were applied successfully.
        """
        try:
            if not voice_client or not voice_client.is_connected():
                return False
            
            # Check if something is currently playing or paused
            if not (voice_client.is_playing() or voice_client.is_paused()):
                return False
            
            # Get current song
            current_song = self.get_current_song(guild_id)
            if not current_song:
                return False
            
            # Remember if we were paused
            was_paused = voice_client.is_paused()
            
            # Stop current playback
            voice_client.stop()
            
            # Wait a moment for the stop to take effect
            await asyncio.sleep(0.1)
            
            # Create new audio source with updated filters
            audio_source = await self._create_audio_source(guild_id, current_song)
            if not audio_source:
                return False
            
            # Start playback with new filters
            voice_client.play(audio_source)
            
            # Restore paused state if needed
            if was_paused:
                voice_client.pause()
            
            log.info(f"Applied filters to current song in guild {guild_id}")
            return True
            
        except Exception as e:
            log.exception(f"Failed to apply filters to current song in guild {guild_id}")
            return False
    
    def update_volume(self, guild_id: int, voice_client, volume: int) -> bool:
        """Update volume of currently playing audio."""
        try:
            # Update volume in filter service
            success, message = self._get_filter_service().set_volume(guild_id, volume)
            if not success:
                return False
            
            # Apply to current voice client if playing
            if voice_client and voice_client.source:
                voice_client.source.volume = volume / 100.0
                log.info(f"Updated voice client volume to {volume}% in guild {guild_id}")
            
            return True
            
        except Exception as e:
            log.exception(f"Failed to update volume in guild {guild_id}")
            return False
    
    def get_playback_info(self, guild_id: int) -> Dict[str, Any]:
        """Get comprehensive playback information for a guild."""
        music_info = self._get_music_service().get_queue_info(guild_id)
        filter_info = self._get_filter_service().get_filter_status(guild_id)
        
        return {
            **music_info,
            **filter_info,
            "current_song_cached": self.get_current_song(guild_id)
        } 