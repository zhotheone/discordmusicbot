import asyncio
import logging
from typing import Optional

import discord
from discord import FFmpegPCMAudio, FFmpegOpusAudio, PCMVolumeTransformer
import yt_dlp

from core.dependency_injection import DIContainer
from core.events import EventBus
from domain.entities.track import Track
from domain.services.user_service import UserService

logger = logging.getLogger(__name__)


class AudioPlayer:
    """Audio player for Discord voice connections."""
    
    def __init__(self, guild_id: int, container: DIContainer, event_bus: EventBus, voice_client: Optional[discord.VoiceClient] = None):
        self.guild_id = guild_id
        self.container = container
        self.event_bus = event_bus
        self.voice_client = voice_client
        self.user_service: UserService = container.get(UserService)
        self.current_track: Optional[Track] = None
        self.is_playing_flag = False
        self.current_source: Optional[discord.AudioSource] = None
        self.volume_transformer: Optional[PCMVolumeTransformer] = None
        self.current_volume: float = 0.5  # Default volume (will be overridden by user settings)
    
    async def play(self, track: Track) -> None:
        """Play a track."""
        if not self.voice_client or not self.voice_client.is_connected():
            logger.error(f"Cannot play track - no voice connection for guild {self.guild_id}")
            return
            
        self.current_track = track
        logger.info(f"Playing track: {track.title}")
        
        try:
            # Load user's volume settings before playing
            await self._load_user_volume_settings(track.requester_id)
            # Stop any currently playing audio
            if self.voice_client.is_playing():
                self.voice_client.stop()
            
            # Get the YouTube URL and extract the actual audio stream URL
            youtube_url = track.url
            if not youtube_url:
                logger.error(f"No YouTube URL found for track: {track.title}")
                return
            
            # Extract the actual audio stream URL using yt-dlp
            audio_stream_url = await self._get_audio_stream_url(youtube_url)
            if not audio_stream_url:
                logger.error(f"Could not extract audio stream URL for: {track.title}")
                return
            
            # Configure FFmpeg options for better audio quality and streaming
            # Remove volume filter from FFmpeg since we'll handle it with PCMVolumeTransformer
            ffmpeg_options = {
                'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -nostdin',
                'options': '-vn'  # -vn removes video
            }
            
            # Create base audio source with the extracted stream URL
            base_source = FFmpegPCMAudio(audio_stream_url, **ffmpeg_options)
            
            # Wrap with volume transformer for real-time volume control
            self.volume_transformer = PCMVolumeTransformer(base_source, volume=self.current_volume)
            self.current_source = self.volume_transformer
            
            # Play the audio
            self.voice_client.play(
                self.current_source,
                after=lambda error: self._on_playback_finished_sync(error)
            )
            
            self.is_playing_flag = True
            
        except Exception as e:
            logger.error(f"Error playing track {track.title}: {e}")
            await self.event_bus.publish("track_ended", guild_id=self.guild_id, track=track)
    
    async def stop(self) -> None:
        """Stop playback."""
        if self.voice_client and self.voice_client.is_playing():
            self.voice_client.stop()
        
        self.is_playing_flag = False
        self.current_track = None
        self.current_source = None
        self.volume_transformer = None
        logger.info(f"Stopped playback for guild {self.guild_id}")
    
    async def pause(self) -> None:
        """Pause playback."""
        if self.voice_client and self.voice_client.is_playing():
            self.voice_client.pause()
            logger.info(f"Paused playback for guild {self.guild_id}")
    
    async def resume(self) -> None:
        """Resume playback."""
        if self.voice_client and self.voice_client.is_paused():
            self.voice_client.resume()
            logger.info(f"Resumed playback for guild {self.guild_id}")
    
    async def set_volume(self, volume: float) -> None:
        """Set playback volume."""
        # Clamp volume between 0.0 and 2.0 (Discord.py allows up to 2.0 for amplification)
        volume = max(0.0, min(2.0, volume))
        self.current_volume = volume
        
        # Apply volume to currently playing audio if available
        if self.volume_transformer:
            self.volume_transformer.volume = volume
            logger.info(f"Volume changed to {volume:.1f} for guild {self.guild_id}")
        else:
            logger.info(f"Volume set to {volume:.1f} for guild {self.guild_id} (will apply to next track)")
    
    def is_playing(self) -> bool:
        """Check if currently playing."""
        if self.voice_client:
            return self.voice_client.is_playing()
        return False
    
    def set_voice_client(self, voice_client: discord.VoiceClient) -> None:
        """Set the voice client for this player."""
        self.voice_client = voice_client
    
    async def _load_user_volume_settings(self, user_id: int) -> None:
        """Load user's volume settings from database."""
        try:
            user_settings = await self.user_service.get_user_settings(user_id)
            if user_settings and user_settings.default_volume is not None:
                self.current_volume = user_settings.default_volume
                logger.info(f"Loaded user {user_id}'s volume setting: {self.current_volume:.2f}")
            else:
                # Use default volume if no settings found
                self.current_volume = 0.5
                logger.info(f"Using default volume for user {user_id}: {self.current_volume:.2f}")
        except Exception as e:
            logger.error(f"Error loading user settings for {user_id}: {e}")
            self.current_volume = 0.5  # Fallback to default
    
    async def _get_audio_stream_url(self, url: str) -> Optional[str]:
        """Extract the actual audio stream URL from a YouTube URL."""
        ydl_opts = {
            'format': 'bestaudio/best',
            'noplaylist': True,
            'quiet': True,
            'extractaudio': True,
            'audioformat': 'opus',
            'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
            'restrictfilenames': True,
            'no_warnings': True,
            'ignoreerrors': False,
            'logtostderr': False,
            'default_search': 'ytsearch',
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Extract info without downloading
                info = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: ydl.extract_info(url, download=False)
                )
                
                if info and 'url' in info:
                    return info['url']
                elif info and 'entries' in info and len(info['entries']) > 0:
                    # Handle playlists - get first entry
                    return info['entries'][0]['url']
                    
        except Exception as e:
            logger.error(f"Error extracting audio stream from {url}: {e}")
            
        return None
    
    def _on_playback_finished_sync(self, error) -> None:
        """Handle playback finished callback (synchronous)."""
        if error:
            logger.error(f"Playback error in guild {self.guild_id}: {error}")
        
        # Mark as not playing
        self.is_playing_flag = False
        current_track = self.current_track
        
        # Clean up
        self.current_source = None
        self.volume_transformer = None
        
        # Schedule async event publishing
        if current_track:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._on_playback_finished_async(current_track))
            except RuntimeError:
                logger.error("No running event loop to publish track ended event")
    
    async def _on_playback_finished_async(self, track) -> None:
        """Handle async part of playback finished callback."""
        await self.event_bus.publish("track_ended", guild_id=self.guild_id, track=track)