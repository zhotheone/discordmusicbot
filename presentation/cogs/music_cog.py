import logging

import discord
from discord import app_commands
from discord.ext import commands

from core.dependency_injection import DIContainer
from core.events import EventBus
from domain.entities.playlist import RepeatMode
from domain.services.music_service import MusicService
from domain.services.playlist_loader import PlaylistLoaderService
from domain.services.user_service import UserService
from infrastructure.audio.sources.spotify import SpotifySource
from infrastructure.audio.sources.youtube import YouTubeSource
from utils.validators import validate_volume
from presentation.views.music_controls import MusicControlView

logger = logging.getLogger(__name__)


class MusicCog(commands.Cog):
    """Music playback commands."""

    def __init__(self, container: DIContainer):
        self.container = container
        self.music_service: MusicService = container.get(MusicService)
        self.user_service: UserService = container.get(UserService)
        self.playlist_loader: PlaylistLoaderService = container.get(
            PlaylistLoaderService
        )
        self.event_bus: EventBus = container.get(EventBus)
        self.youtube_source = YouTubeSource()
        self.spotify_source = SpotifySource()

        # Subscribe to events
        self.event_bus.subscribe("queue_finished", self._on_queue_finished)

    async def cog_before_invoke(self, ctx: commands.Context) -> None:
        """Pre-command checks."""
        if not ctx.author.voice:
            await ctx.send(
                "❌ You need to be in a voice channel to use music commands!"
            )
            raise commands.CommandError("User not in voice channel")

    @app_commands.command(
        name="play", description="Play a song from YouTube or Spotify"
    )
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
            tracks = []

            # Try Spotify first if it looks like a Spotify URL
            if self.spotify_source.is_supported_url(query):
                track = await self.spotify_source.get_track_info(
                    query, interaction.user.id
                )
                if track:
                    tracks.append(track)
            # Check if it's a YouTube playlist
            elif self.youtube_source.is_supported_url(
                query
            ) and self.youtube_source.is_playlist_url(query):
                # Use progressive playlist loading
                loading_embed = discord.Embed(
                    title="📋 Loading Playlist...",
                    description="Loading first 5 tracks, more will be added in background...",
                    color=discord.Color.orange(),
                )
                loading_msg = await interaction.followup.send(embed=loading_embed)

                # Create progress callback to update the message
                async def progress_callback(progress):
                    try:
                        embed = discord.Embed(
                            title="📋 Loading Playlist...",
                            description=f"Loaded {progress['loaded']} of ~{progress['total']} tracks ({progress['percentage']:.1f}%)",
                            color=discord.Color.blue(),
                        )
                        await loading_msg.edit(embed=embed)
                    except Exception as e:
                        logger.error(f"Error updating progress: {e}")

                try:
                    # Start progressive loading
                    task = await self.playlist_loader.start_playlist_loading(
                        guild_id=interaction.guild.id,
                        playlist_url=query,
                        requester_id=interaction.user.id,
                        voice_client=interaction.guild.voice_client,
                        max_tracks=50,
                        progress_callback=progress_callback,
                    )

                    if task.status.value == "failed" or not task.loaded_tracks:
                        embed = discord.Embed(
                            title="❌ Playlist Error",
                            description="Could not load tracks from playlist\n💡 **Tip:** YouTube Mix/Radio playlists are dynamic. Try using the individual video URL instead.",
                            color=discord.Color.red(),
                        )
                        await loading_msg.edit(embed=embed)
                        return

                    # Show initial success message
                    if "start_radio=1" in query or "rdmm" in query.lower():
                        embed = discord.Embed(
                            title="📻 YouTube Mix Started",
                            description=f"🎵 Playing first {len(task.loaded_tracks)} tracks\n⏳ Loading more in background...",
                            color=discord.Color.orange(),
                        )
                    else:
                        embed = discord.Embed(
                            title="📋 Playlist Started",
                            description=f"🎵 Playing first {len(task.loaded_tracks)} tracks\n⏳ Loading {task.total_entries - len(task.loaded_tracks)} more in background...",
                            color=discord.Color.blue(),
                        )

                    embed.add_field(
                        name="Requested by", value=interaction.user.mention, inline=True
                    )
                    embed.add_field(
                        name="Total Found",
                        value=f"~{task.total_entries} tracks",
                        inline=True,
                    )
                    
                    # Add control panel for playlist playback
                    if task.loaded_tracks:
                        control_view = MusicControlView(self.container, interaction.guild.id, task.loaded_tracks[0])
                        await loading_msg.edit(embed=embed, view=control_view)
                    else:
                        await loading_msg.edit(embed=embed)
                    
                    # Skip the normal track adding logic since progressive loader handles it
                    return

                except Exception as e:
                    logger.error(f"Error with progressive playlist loading: {e}")
                    embed = discord.Embed(
                        title="❌ Playlist Loading Error",
                        description="An error occurred while loading the playlist. Falling back to standard loading...",
                        color=discord.Color.red(),
                    )
                    await loading_msg.edit(embed=embed)

                    # Fallback to old method
                    playlist_tracks = await self.youtube_source.get_playlist_info(
                        query, interaction.user.id, max_tracks=50
                    )
                    if playlist_tracks:
                        tracks.extend(playlist_tracks)
                    else:
                        await interaction.followup.send(
                            f"❌ Could not extract tracks from playlist: `{query}`"
                        )
                        return
            # Try YouTube if it looks like a YouTube URL
            elif self.youtube_source.is_supported_url(query):
                track = await self.youtube_source.get_track_info(
                    query, interaction.user.id
                )
                if track:
                    tracks.append(track)
            # Otherwise search YouTube
            else:
                search_results = await self.youtube_source.search(query, max_results=1)
                if search_results:
                    track = search_results[0]
                    track.requester_id = interaction.user.id
                    tracks.append(track)

            if not tracks:
                await interaction.followup.send(f"❌ Could not find: `{query}`")
                return

            # Add tracks to queue
            successful_tracks = []
            failed_count = 0

            for track in tracks:
                try:
                    success = await self.music_service.play(
                        interaction.guild.id, track, interaction.guild.voice_client
                    )
                    if success:
                        # Add to user history
                        await self.user_service.add_to_history(
                            interaction.user.id, track
                        )
                        successful_tracks.append(track)
                    else:
                        failed_count += 1
                except Exception as e:
                    logger.error(f"Error adding track {track.title} to queue: {e}")
                    failed_count += 1

            # Send response based on results
            if successful_tracks:
                if len(tracks) == 1:
                    # Single track - show detailed embed
                    track = successful_tracks[0]
                    embed = discord.Embed(
                        title="🎵 Added to Queue",
                        description=f"**{track.display_title}**",
                        color=discord.Color.green(),
                    )

                    if track.thumbnail_url:
                        embed.set_thumbnail(url=track.thumbnail_url)

                    embed.add_field(
                        name="Duration", value=track.duration_formatted, inline=True
                    )
                    embed.add_field(
                        name="Requested by", value=interaction.user.mention, inline=True
                    )
                    embed.add_field(
                        name="Source", value=track.source.value.title(), inline=True
                    )

                    # Only send this if we haven't already sent the playlist message
                    if not (self.youtube_source.is_supported_url(query) and self.youtube_source.is_playlist_url(query)):
                        # Create and send the control panel view
                        control_view = MusicControlView(self.container, interaction.guild.id, track)
                        await interaction.followup.send(embed=embed, view=control_view)
                else:
                    # Multiple tracks - show summary (if not already sent playlist message)
                    if not (
                        self.youtube_source.is_supported_url(query)
                        and self.youtube_source.is_playlist_url(query)
                    ):
                        message = (
                            f"✅ Added **{len(successful_tracks)}** tracks to queue"
                        )
                        if failed_count > 0:
                            message += f" ({failed_count} failed)"
                        await interaction.followup.send(message)

                if failed_count > 0:
                    await interaction.followup.send(
                        f"⚠️ {failed_count} tracks failed to add to queue"
                    )
            else:
                await interaction.followup.send("❌ Failed to add any tracks to queue!")

        except Exception as e:
            logger.error(f"Error in play command: {e}")
            await interaction.followup.send(
                "❌ An error occurred while trying to play the track!"
            )

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
            await interaction.followup.send(
                "❌ An error occurred while stopping playback!"
            )

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
                    color=discord.Color.blue(),
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
                color=discord.Color.blue(),
            )

            embed.add_field(name="Tracks", value=str(len(playlist)), inline=True)
            embed.add_field(
                name="Repeat Mode",
                value=playlist.repeat_mode.value.title(),
                inline=True,
            )

            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"Error in queue command: {e}")
            await interaction.followup.send(
                "❌ An error occurred while fetching the queue!"
            )

    @app_commands.command(name="repeat", description="Set repeat mode")
    @app_commands.describe(mode="Repeat mode: off, track, or queue")
    @app_commands.choices(
        mode=[
            app_commands.Choice(name="Off", value="off"),
            app_commands.Choice(name="Track", value="track"),
            app_commands.Choice(name="Queue", value="queue"),
        ]
    )
    async def repeat(self, interaction: discord.Interaction, mode: str) -> None:
        """Set repeat mode."""
        await interaction.response.defer()

        try:
            repeat_mode = RepeatMode(mode)
            success = await self.music_service.set_repeat_mode(
                interaction.guild.id, repeat_mode
            )

            if success:
                emoji = {"off": "🔁", "track": "🔂", "queue": "🔁"}[mode]
                await interaction.followup.send(
                    f"{emoji} Repeat mode set to: **{mode.title()}**"
                )
            else:
                await interaction.followup.send("❌ Failed to set repeat mode!")

        except ValueError:
            await interaction.followup.send(
                "❌ Invalid repeat mode! Use: off, track, or queue"
            )
        except Exception as e:
            logger.error(f"Error in repeat command: {e}")
            await interaction.followup.send(
                "❌ An error occurred while setting repeat mode!"
            )

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
            await interaction.followup.send(
                "❌ An error occurred while setting volume!"
            )

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
                color=discord.Color.green(),
            )

            if current_track.thumbnail_url:
                embed.set_thumbnail(url=current_track.thumbnail_url)

            embed.add_field(
                name="Duration", value=current_track.duration_formatted, inline=True
            )
            embed.add_field(
                name="Source", value=current_track.source.value.title(), inline=True
            )
            embed.add_field(
                name="Requested by",
                value=f"<@{current_track.requester_id}>",
                inline=True,
            )
            
            # Add control panel
            control_view = MusicControlView(self.container, interaction.guild.id, current_track)
            await interaction.followup.send(embed=embed, view=control_view)
            
        except Exception as e:
            logger.error(f"Error in nowplaying command: {e}")
            await interaction.followup.send(
                "❌ An error occurred while fetching current track!"
            )

    @app_commands.command(
        name="playlist", description="Add a YouTube playlist to the queue"
    )
    @app_commands.describe(
        url="YouTube playlist URL",
        limit="Maximum number of tracks to add (default: 50, max: 100)",
    )
    async def playlist(
        self, interaction: discord.Interaction, url: str, limit: int = 50
    ) -> None:
        """Add a YouTube playlist to the queue."""
        await interaction.response.defer()

        try:
            # Check if user is in voice channel
            if not interaction.user.voice:
                await interaction.followup.send("❌ You need to be in a voice channel!")
                return

            # Validate limit
            limit = max(1, min(limit, 100))  # Clamp between 1-100

            # Join voice channel if not connected
            voice_channel = interaction.user.voice.channel
            if not interaction.guild.voice_client:
                await voice_channel.connect()
            elif interaction.guild.voice_client.channel != voice_channel:
                await interaction.guild.voice_client.move_to(voice_channel)

            # Check if it's a supported YouTube URL
            if not self.youtube_source.is_supported_url(url):
                await interaction.followup.send(
                    "❌ Please provide a valid YouTube URL!"
                )
                return

            # Check if it's a playlist
            if not self.youtube_source.is_playlist_url(url):
                await interaction.followup.send(
                    "❌ Please provide a YouTube playlist URL!"
                )
                return

            # Send initial message
            embed = discord.Embed(
                title="📋 Processing Playlist...",
                description=f"Loading first 5 tracks, remaining {limit - 5} will be added progressively...",
                color=discord.Color.orange(),
            )
            initial_msg = await interaction.followup.send(embed=embed)

            # Create progress callback
            async def progress_callback(progress):
                try:
                    embed = discord.Embed(
                        title="📋 Loading Playlist...",
                        description=f"Loaded {progress['loaded']} of ~{progress['total']} tracks ({progress['percentage']:.1f}%)",
                        color=discord.Color.blue(),
                    )
                    await initial_msg.edit(embed=embed)
                except Exception as e:
                    logger.error(f"Error updating playlist progress: {e}")

            try:
                # Use progressive playlist loading
                task = await self.playlist_loader.start_playlist_loading(
                    guild_id=interaction.guild.id,
                    playlist_url=url,
                    requester_id=interaction.user.id,
                    voice_client=interaction.guild.voice_client,
                    max_tracks=limit,
                    progress_callback=progress_callback,
                )

                if task.status.value == "failed" or not task.loaded_tracks:
                    embed.title = "❌ Playlist Error"
                    embed.description = (
                        "Could not extract any tracks from the playlist."
                    )
                    embed.color = discord.Color.red()
                    await initial_msg.edit(embed=embed)
                    return

                # Send success message
                embed.title = "✅ Playlist Started"
                embed.color = discord.Color.green()
                embed.description = f"🎵 Started playback with first {len(task.loaded_tracks)} tracks\n⏳ Loading remaining ~{task.total_entries - len(task.loaded_tracks)} tracks in background"

                embed.add_field(
                    name="Requested by", value=interaction.user.mention, inline=True
                )
                embed.add_field(
                    name="Total Found",
                    value=f"~{task.total_entries} tracks",
                    inline=True,
                )
                embed.add_field(
                    name="Initial Batch",
                    value=f"{len(task.loaded_tracks)} tracks",
                    inline=True,
                )

                await initial_msg.edit(embed=embed)

            except Exception as e:
                logger.error(f"Error with progressive playlist loading: {e}")

                # Fallback to old method
                embed.title = "📋 Fallback Loading..."
                embed.description = (
                    "Progressive loading failed, using standard method..."
                )
                embed.color = discord.Color.orange()
                await initial_msg.edit(embed=embed)

                playlist_tracks = await self.youtube_source.get_playlist_info(
                    url, interaction.user.id, max_tracks=limit
                )

                if not playlist_tracks:
                    embed.title = "❌ Playlist Error"
                    embed.description = (
                        "Could not extract any tracks from the playlist."
                    )
                    embed.color = discord.Color.red()
                    await initial_msg.edit(embed=embed)
                    return

                # Add tracks using old method
                successful_tracks = []
                failed_count = 0

                for track in playlist_tracks:
                    try:
                        success = await self.music_service.play(
                            interaction.guild.id, track, interaction.guild.voice_client
                        )
                        if success:
                            await self.user_service.add_to_history(
                                interaction.user.id, track
                            )
                            successful_tracks.append(track)
                        else:
                            failed_count += 1
                    except Exception as e:
                        logger.error(f"Error adding playlist track: {e}")
                        failed_count += 1

                # Final result
                embed.title = "✅ Playlist Added (Fallback)"
                embed.color = discord.Color.green()
                embed.description = (
                    f"Successfully added **{len(successful_tracks)}** tracks"
                )

                if failed_count > 0:
                    embed.add_field(
                        name="Failed", value=f"{failed_count} tracks", inline=True
                    )

                await initial_msg.edit(embed=embed)

        except Exception as e:
            logger.error(f"Error in playlist command: {e}")
            await interaction.followup.send(
                "❌ An error occurred while processing the playlist!"
            )

    async def _on_queue_finished(self, guild_id: int) -> None:
        """Handle queue finished event - disconnect from voice."""
        try:
            # Get the guild and disconnect from voice
            bot = self.container.get("Bot")
            guild = bot.get_guild(guild_id)
            if guild and guild.voice_client:
                await guild.voice_client.disconnect()
                logger.info(
                    f"Disconnected from voice channel in guild {guild_id} - queue finished"
                )
            else:
                logger.debug(f"No voice client to disconnect in guild {guild_id}")
        except Exception as e:
            logger.error(f"Error disconnecting from voice in guild {guild_id}: {e}")


async def setup(bot):
    """Setup function for the cog."""
    container = bot.container
    await bot.add_cog(MusicCog(container))
