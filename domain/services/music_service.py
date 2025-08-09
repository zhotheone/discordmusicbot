import logging
from typing import Optional, Dict, List

import discord

from config.settings import Settings
from core.dependency_injection import DIContainer
from core.events import EventBus, Events
from domain.entities.track import Track
from domain.entities.playlist import Playlist, RepeatMode
from infrastructure.audio.player import AudioPlayer

logger = logging.getLogger(__name__)


class MusicService:
    """Core music service handling playback logic."""
    
    def __init__(self, container: DIContainer, event_bus: EventBus, settings: Settings):
        self.container = container
        self.event_bus = event_bus
        self.settings = settings
        self.playlists: Dict[int, Playlist] = {}  # guild_id -> Playlist
        self.audio_players: Dict[int, AudioPlayer] = {}  # guild_id -> AudioPlayer
        
        # Subscribe to events
        self.event_bus.subscribe(Events.TRACK_ENDED, self._on_track_ended)
        self.event_bus.subscribe("guild_left", self._on_guild_left)
    
    async def play(self, guild_id: int, track: Track, voice_client: Optional[discord.VoiceClient] = None) -> bool:
        """Play a track in the specified guild."""
        try:
            playlist = self._get_or_create_playlist(guild_id)
            
            # Add track to queue
            playlist.add_track(track)
            
            # If nothing is playing, start playback
            if not playlist.get_current_track():
                playlist.current_index = len(playlist.tracks) - 1
                await self._start_playback(guild_id, voice_client)
            
            await self.event_bus.publish(Events.QUEUE_UPDATED, guild_id=guild_id, playlist=playlist)
            return True
            
        except Exception as e:
            logger.error(f"Error playing track in guild {guild_id}: {e}")
            return False
    
    async def stop(self, guild_id: int) -> bool:
        """Stop playback in the specified guild."""
        try:
            if guild_id in self.audio_players:
                await self.audio_players[guild_id].stop()
                del self.audio_players[guild_id]
            
            if guild_id in self.playlists:
                self.playlists[guild_id].clear()
            
            await self.event_bus.publish("playback_stopped", guild_id=guild_id)
            return True
            
        except Exception as e:
            logger.error(f"Error stopping playback in guild {guild_id}: {e}")
            return False
    
    async def skip(self, guild_id: int) -> Optional[Track]:
        """Skip to the next track."""
        try:
            playlist = self.playlists.get(guild_id)
            if not playlist:
                return None
            
            current_track = playlist.get_current_track()
            next_track = playlist.next_track()
            
            if current_track:
                await self.event_bus.publish(Events.TRACK_SKIPPED, guild_id=guild_id, track=current_track)
            
            if next_track:
                await self._start_playback(guild_id)
            else:
                await self.stop(guild_id)
            
            return next_track
            
        except Exception as e:
            logger.error(f"Error skipping track in guild {guild_id}: {e}")
            return None
    
    async def set_repeat_mode(self, guild_id: int, mode: RepeatMode) -> bool:
        """Set the repeat mode for a guild."""
        try:
            playlist = self._get_or_create_playlist(guild_id)
            playlist.repeat_mode = mode
            
            await self.event_bus.publish("repeat_mode_changed", guild_id=guild_id, mode=mode)
            return True
            
        except Exception as e:
            logger.error(f"Error setting repeat mode in guild {guild_id}: {e}")
            return False
    
    async def pause(self, guild_id: int) -> bool:
        """Pause playback."""
        try:
            if guild_id in self.audio_players:
                await self.audio_players[guild_id].pause()
                await self.event_bus.publish("playback_paused", guild_id=guild_id)
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error pausing playback in guild {guild_id}: {e}")
            return False
    
    async def resume(self, guild_id: int) -> bool:
        """Resume playback."""
        try:
            if guild_id in self.audio_players:
                await self.audio_players[guild_id].resume()
                await self.event_bus.publish("playback_resumed", guild_id=guild_id)
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error resuming playback in guild {guild_id}: {e}")
            return False
    
    async def set_volume(self, guild_id: int, volume: float) -> bool:
        """Set playback volume."""
        try:
            if not 0.0 <= volume <= 1.0:
                raise ValueError("Volume must be between 0.0 and 1.0")
            
            if guild_id in self.audio_players:
                await self.audio_players[guild_id].set_volume(volume)
                await self.event_bus.publish("volume_changed", guild_id=guild_id, volume=volume)
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error setting volume in guild {guild_id}: {e}")
            return False
    
    def get_playlist(self, guild_id: int) -> Optional[Playlist]:
        """Get the playlist for a guild."""
        return self.playlists.get(guild_id)
    
    def get_current_track(self, guild_id: int) -> Optional[Track]:
        """Get the currently playing track for a guild."""
        playlist = self.playlists.get(guild_id)
        return playlist.get_current_track() if playlist else None
    
    def is_playing(self, guild_id: int) -> bool:
        """Check if music is currently playing in a guild."""
        player = self.audio_players.get(guild_id)
        return player.is_playing() if player else False
    
    def _get_or_create_playlist(self, guild_id: int) -> Playlist:
        """Get or create a playlist for a guild."""
        if guild_id not in self.playlists:
            self.playlists[guild_id] = Playlist(
                guild_id=guild_id,
                max_size=self.settings.max_queue_size
            )
        return self.playlists[guild_id]
    
    async def _start_playback(self, guild_id: int, voice_client: Optional[discord.VoiceClient] = None) -> None:
        """Start playback for the current track."""
        playlist = self.playlists.get(guild_id)
        if not playlist:
            return
        
        current_track = playlist.get_current_track()
        if not current_track:
            return
        
        # Create or get audio player
        if guild_id not in self.audio_players:
            self.audio_players[guild_id] = AudioPlayer(
                guild_id=guild_id,
                container=self.container,
                event_bus=self.event_bus,
                voice_client=voice_client
            )
        else:
            # Update voice client if provided
            if voice_client:
                self.audio_players[guild_id].set_voice_client(voice_client)
        
        player = self.audio_players[guild_id]
        await player.play(current_track)
        
        await self.event_bus.publish(Events.TRACK_STARTED, guild_id=guild_id, track=current_track)
    
    async def _on_track_ended(self, guild_id: int, track: Track) -> None:
        """Handle track ended event."""
        try:
            playlist = self.playlists.get(guild_id)
            if not playlist:
                return
            
            # Auto-advance to next track
            next_track = playlist.next_track()
            if next_track:
                await self._start_playback(guild_id)
            else:
                # End of queue - clean up playlist and player
                playlist.clear()  # Clear the playlist to remove the last track
                if guild_id in self.audio_players:
                    del self.audio_players[guild_id]
                await self.event_bus.publish("queue_finished", guild_id=guild_id)
                
        except Exception as e:
            logger.error(f"Error handling track ended in guild {guild_id}: {e}")
    
    async def _on_guild_left(self, guild: object) -> None:
        """Clean up when bot leaves a guild."""
        guild_id = guild.id
        
        if guild_id in self.playlists:
            del self.playlists[guild_id]
        
        if guild_id in self.audio_players:
            await self.audio_players[guild_id].stop()
            del self.audio_players[guild_id]
        
        logger.info(f"Cleaned up music data for guild {guild_id}")