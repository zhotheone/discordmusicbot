import logging
from typing import Optional

import discord
from discord.ext import commands
from discord import app_commands

from core.dependency_injection import DIContainer
from domain.services.music_service import MusicService
from domain.services.user_service import UserService
from domain.entities.playlist import RepeatMode
from infrastructure.audio.sources.youtube import YouTubeSource
from infrastructure.audio.sources.spotify import SpotifySource
from utils.validators import validate_volume

logger = logging.getLogger(__name__)


class MusicCog(commands.Cog):
    """Music playback commands."""
    
    def __init__(self, container: DIContainer):
        self.container = container
        self.music_service: MusicService = container.get(MusicService)
        self.user_service: UserService = container.get(UserService)
        self.youtube_source = YouTubeSource()
        self.spotify_source = SpotifySource()
    
    async def cog_before_invoke(self, ctx: commands.Context) -> None:
        """Pre-command checks."""
        if not ctx.author.voice:
            await ctx.send("❌ You need to be in a voice channel to use music commands!")
            raise commands.CommandError("User not in voice channel")
    
    @app_commands.command(name="play", description="Play a song from YouTube or Spotify")
    async def play(self, interaction: discord.Interaction, query: str) -> None:
        """Play a track from search query or URL."""
        await interaction.response.defer()
        
        try:
            # Check if user is in voice channel
            if not interaction.user.voice:
                await interaction.followup.send("❌ You need to be in a voice channel!")
                return
            
            # Join voice channel if not connected
            voice_channel = interaction.user.voice.channel
            if not interaction.guild.voice_client:
                await voice_channel.connect()
            elif interaction.guild.voice_client.channel != voice_channel:
                await interaction.guild.voice_client.move_to(voice_channel)
            
            # Determine if it's a URL or search query
            track = None
            
            # Try Spotify first if it looks like a Spotify URL
            if self.spotify_source.is_supported_url(query):
                track = await self.spotify_source.get_track_info(query, interaction.user.id)
            # Try YouTube if it looks like a YouTube URL
            elif self.youtube_source.is_supported_url(query):
                track = await self.youtube_source.get_track_info(query, interaction.user.id)
            # Otherwise search YouTube
            else:
                search_results = await self.youtube_source.search(query, max_results=1)
                if search_results:
                    track = search_results[0]
                    track.requester_id = interaction.user.id
            
            if not track:
                await interaction.followup.send(f"❌ Could not find: `{query}`")
                return
            
            # Add track to queue
            success = await self.music_service.play(interaction.guild.id, track, interaction.guild.voice_client)
            
            if success:
                # Add to user history
                await self.user_service.add_to_history(interaction.user.id, track)
                
                embed = discord.Embed(
                    title="🎵 Added to Queue",
                    description=f"**{track.display_title}**",
                    color=discord.Color.green()
                )
                
                if track.thumbnail_url:
                    embed.set_thumbnail(url=track.thumbnail_url)
                
                embed.add_field(
                    name="Duration",
                    value=track.duration_formatted,
                    inline=True
                )
                embed.add_field(
                    name="Requested by",
                    value=interaction.user.mention,
                    inline=True
                )
                embed.add_field(
                    name="Source",
                    value=track.source.value.title(),
                    inline=True
                )
                
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send("❌ Failed to add track to queue!")
                
        except Exception as e:
            logger.error(f"Error in play command: {e}")
            await interaction.followup.send("❌ An error occurred while trying to play the track!")
    
    @app_commands.command(name="stop", description="Stop playback and clear the queue")
    async def stop(self, interaction: discord.Interaction) -> None:
        """Stop playback and disconnect."""
        await interaction.response.defer()
        
        try:
            success = await self.music_service.stop(interaction.guild.id)
            
            if interaction.guild.voice_client:
                await interaction.guild.voice_client.disconnect()
            
            if success:
                await interaction.followup.send("⏹️ Stopped playback and cleared queue!")
            else:
                await interaction.followup.send("❌ Nothing was playing!")
                
        except Exception as e:
            logger.error(f"Error in stop command: {e}")
            await interaction.followup.send("❌ An error occurred while stopping playback!")
    
    @app_commands.command(name="skip", description="Skip to the next track")
    async def skip(self, interaction: discord.Interaction) -> None:
        """Skip to the next track."""
        await interaction.response.defer()
        
        try:
            next_track = await self.music_service.skip(interaction.guild.id)
            
            if next_track:
                embed = discord.Embed(
                    title="⏭️ Skipped",
                    description=f"Now playing: **{next_track.display_title}**",
                    color=discord.Color.blue()
                )
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send("⏭️ Skipped! No more tracks in queue.")
                
        except Exception as e:
            logger.error(f"Error in skip command: {e}")
            await interaction.followup.send("❌ An error occurred while skipping!")
    
    @app_commands.command(name="pause", description="Pause playback")
    async def pause(self, interaction: discord.Interaction) -> None:
        """Pause playback."""
        await interaction.response.defer()
        
        try:
            success = await self.music_service.pause(interaction.guild.id)
            
            if success:
                await interaction.followup.send("⏸️ Paused playback!")
            else:
                await interaction.followup.send("❌ Nothing is currently playing!")
                
        except Exception as e:
            logger.error(f"Error in pause command: {e}")
            await interaction.followup.send("❌ An error occurred while pausing!")
    
    @app_commands.command(name="resume", description="Resume playback")
    async def resume(self, interaction: discord.Interaction) -> None:
        """Resume playback."""
        await interaction.response.defer()
        
        try:
            success = await self.music_service.resume(interaction.guild.id)
            
            if success:
                await interaction.followup.send("▶️ Resumed playback!")
            else:
                await interaction.followup.send("❌ Nothing is paused!")
                
        except Exception as e:
            logger.error(f"Error in resume command: {e}")
            await interaction.followup.send("❌ An error occurred while resuming!")
    
    @app_commands.command(name="queue", description="Show the current queue")
    async def queue(self, interaction: discord.Interaction) -> None:
        """Display the current queue."""
        await interaction.response.defer()
        
        try:
            playlist = self.music_service.get_playlist(interaction.guild.id)
            
            if not playlist or not playlist:
                await interaction.followup.send("📭 Queue is empty!")
                return
            
            queue_display = playlist.get_queue_display(max_tracks=10)
            
            embed = discord.Embed(
                title="🎵 Current Queue",
                description="\n".join(queue_display),
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="Tracks",
                value=str(len(playlist)),
                inline=True
            )
            embed.add_field(
                name="Repeat Mode",
                value=playlist.repeat_mode.value.title(),
                inline=True
            )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in queue command: {e}")
            await interaction.followup.send("❌ An error occurred while fetching the queue!")
    
    @app_commands.command(name="repeat", description="Set repeat mode")
    @app_commands.describe(mode="Repeat mode: off, track, or queue")
    @app_commands.choices(mode=[
        app_commands.Choice(name="Off", value="off"),
        app_commands.Choice(name="Track", value="track"),
        app_commands.Choice(name="Queue", value="queue")
    ])
    async def repeat(self, interaction: discord.Interaction, mode: str) -> None:
        """Set repeat mode."""
        await interaction.response.defer()
        
        try:
            repeat_mode = RepeatMode(mode)
            success = await self.music_service.set_repeat_mode(interaction.guild.id, repeat_mode)
            
            if success:
                emoji = {"off": "🔁", "track": "🔂", "queue": "🔁"}[mode]
                await interaction.followup.send(f"{emoji} Repeat mode set to: **{mode.title()}**")
            else:
                await interaction.followup.send("❌ Failed to set repeat mode!")
                
        except ValueError:
            await interaction.followup.send("❌ Invalid repeat mode! Use: off, track, or queue")
        except Exception as e:
            logger.error(f"Error in repeat command: {e}")
            await interaction.followup.send("❌ An error occurred while setting repeat mode!")
    
    @app_commands.command(name="volume", description="Set playback volume (0-100)")
    @app_commands.describe(level="Volume level from 0 to 100")
    async def volume(self, interaction: discord.Interaction, level: int) -> None:
        """Set playback volume."""
        await interaction.response.defer()
        
        try:
            if not validate_volume(level):
                await interaction.followup.send("❌ Volume must be between 0 and 100!")
                return
            
            volume = level / 100.0
            success = await self.music_service.set_volume(interaction.guild.id, volume)
            
            if success:
                # Also update user's default volume
                await self.user_service.update_volume(interaction.user.id, volume)
                
                await interaction.followup.send(f"🔊 Volume set to: **{level}%**")
            else:
                await interaction.followup.send("❌ Nothing is currently playing!")
                
        except Exception as e:
            logger.error(f"Error in volume command: {e}")
            await interaction.followup.send("❌ An error occurred while setting volume!")
    
    @app_commands.command(name="nowplaying", description="Show currently playing track")
    async def nowplaying(self, interaction: discord.Interaction) -> None:
        """Show currently playing track."""
        await interaction.response.defer()
        
        try:
            current_track = self.music_service.get_current_track(interaction.guild.id)
            
            if not current_track:
                await interaction.followup.send("❌ Nothing is currently playing!")
                return
            
            embed = discord.Embed(
                title="🎵 Now Playing",
                description=f"**{current_track.display_title}**",
                color=discord.Color.green()
            )
            
            if current_track.thumbnail_url:
                embed.set_thumbnail(url=current_track.thumbnail_url)
            
            embed.add_field(
                name="Duration",
                value=current_track.duration_formatted,
                inline=True
            )
            embed.add_field(
                name="Source",
                value=current_track.source.value.title(),
                inline=True
            )
            embed.add_field(
                name="Requested by",
                value=f"<@{current_track.requester_id}>",
                inline=True
            )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in nowplaying command: {e}")
            await interaction.followup.send("❌ An error occurred while fetching current track!")


async def setup(bot):
    """Setup function for the cog."""
    container = bot.container
    await bot.add_cog(MusicCog(container))