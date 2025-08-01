"""Playback Cog for Discord Bot - Handles music playback controls."""
import asyncio
import logging

import discord
import yt_dlp
from discord.ext import commands

from utils.config_manager import ConfigManager
from utils.filters import FFMPEG_FILTER_CHAINS
from utils.views import MusicControlsView
from utils.advanced_views import EnhancedMusicControlsView
from utils.advanced_filters import AdvancedFilterManager

log = logging.getLogger(__name__)

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
FFMPEG_OPTIONS_BASE = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}
yt_dlp.utils.bug_reports_message = lambda *args, **kwargs: ''

class PlaybackCog(commands.Cog, name="Playback Controls"):
    """Commands to play, stop, and manage the music queue."""
    
    def __init__(self, bot: commands.Bot):
        """Initialize the Playback cog."""
        self.bot = bot
        self.config_manager = ConfigManager()
        self.now_playing_messages = {}
        # Store advanced filter managers per guild
        self.guild_filter_managers = {}
    
    def get_filter_manager(self, guild_id: int) -> AdvancedFilterManager:
        """Get or create advanced filter manager for a guild."""
        if guild_id not in self.guild_filter_managers:
            self.guild_filter_managers[guild_id] = AdvancedFilterManager()
        return self.guild_filter_managers[guild_id]
    
    def save_filter_state(self, guild_id: int):
        """Save current filter state to config."""
        if guild_id in self.guild_filter_managers:
            config = self.config_manager.get_config(guild_id)
            config["advanced_filters"] = self.guild_filter_managers[guild_id].to_dict()
            self.config_manager.save_config(guild_id, config)
    
    async def apply_filters_to_current_song(self, guild_id: int, channel=None):
        """Apply current filter settings to the currently playing song."""
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return False
        
        vc = guild.voice_client
        if not vc or not vc.is_connected():
            return False
        
        # Check if something is currently playing or paused
        if not (vc.is_playing() or vc.is_paused()):
            return False
        
        # Get current song info
        current_song = getattr(self, '_current_song', None)
        if not current_song:
            return False
        
        # Remember if we were paused
        was_paused = vc.is_paused()
        
        # Stop current playback
        vc.stop()
        
        # Wait a moment for the stop to take effect
        await asyncio.sleep(0.1)
        
        # Get current filter settings
        config = self.config_manager.get_config(guild_id)
        ffmpeg_options = FFMPEG_OPTIONS_BASE.copy()
        
        # Check for advanced filters first
        filter_manager = self.get_filter_manager(guild_id)
        advanced_filter = filter_manager.get_combined_ffmpeg_filter()
        
        # Fallback to legacy filter system if no advanced filters are active
        if not advanced_filter:
            active_filter = config.get("active_filter", "none")
            if active_filter in FFMPEG_FILTER_CHAINS:
                advanced_filter = FFMPEG_FILTER_CHAINS[active_filter]
        
        # Apply filters if any are active
        if advanced_filter:
            ffmpeg_options['options'] += f' -af "{advanced_filter}"'
        
        log.info(f"Guild {guild_id} - Applying filters to current song: {advanced_filter}")
        
        try:
            # Create new audio source with updated filters
            player = discord.FFmpegPCMAudio(current_song['url'], **ffmpeg_options)
            source = discord.PCMVolumeTransformer(
                player, volume=config.get("volume", 75) / 100.0
            )
            
            # Start playing with new filters
            vc.play(
                source,
                after=lambda e: self.bot.loop.create_task(
                    self.after_playback_runtime_update(guild_id, channel, e)
                )
            )
            
            # Resume paused state if it was paused
            if was_paused:
                vc.pause()
            
            # Update the now playing message to show new filters
            await self._update_now_playing_message(guild_id, current_song, config)
            
            return True
            
        except Exception as e:
            log.exception(f"Failed to apply filters to current song in guild {guild_id}: {e}")
            
            # Try to restart without filters as fallback
            try:
                fallback_options = FFMPEG_OPTIONS_BASE.copy()
                player = discord.FFmpegPCMAudio(current_song['url'], **fallback_options)
                source = discord.PCMVolumeTransformer(
                    player, volume=config.get("volume", 75) / 100.0
                )
                vc.play(
                    source,
                    after=lambda e: self.bot.loop.create_task(
                        self.after_playback_runtime_update(guild_id, channel, e)
                    )
                )
                if was_paused:
                    vc.pause()
                    
            except Exception as fallback_error:
                log.exception(f"Fallback restart also failed in guild {guild_id}: {fallback_error}")
            
            return False
    
    async def after_playback_runtime_update(self, guild_id: int, channel, error):
        """Callback for runtime filter updates - just continue to next song normally."""
        if error:
            log.error(f"Error during runtime-updated playback in guild {guild_id}: {error}")
        else:
            log.info(f"Runtime-updated song finished in guild {guild_id}.")
        
        # Create a mock interaction for _play_next
        guild = self.bot.get_guild(guild_id)
        if guild and channel:
            class MockInteraction:
                def __init__(self, guild, channel):
                    self.guild = guild
                    self.channel = channel
                    self.user = guild.me  # Use bot as user
            
            mock_interaction = MockInteraction(guild, channel)
            await self._play_next(mock_interaction)
    
    async def _update_now_playing_message(self, guild_id: int, song_info: dict, config: dict):
        """Update the now playing message with current filter information."""
        if guild_id not in self.now_playing_messages:
            return
        
        try:
            message = self.now_playing_messages[guild_id]
            
            # Create updated embed
            embed = discord.Embed(
                title="Now Playing",
                description=f"[{song_info['title']}]({song_info['webpage_url']})",
                color=discord.Color.green()
            )
            
            if song_info.get('thumbnail'):
                embed.set_thumbnail(url=song_info['thumbnail'])
            
            # Show active filters (advanced or legacy)
            filter_manager = self.get_filter_manager(guild_id)
            enabled_filters = filter_manager.get_enabled_filters()
            if enabled_filters:
                filter_text = ", ".join(f.capitalize() for f in enabled_filters)
                embed.add_field(
                    name="🎛️ Active Filters (LIVE)",
                    value=filter_text,
                    inline=False
                )
            elif config.get("active_filter", "none") != "none":
                embed.add_field(
                    name="Active Filter (LIVE)",
                    value=f"`{config.get('active_filter').capitalize()}`",
                    inline=False
                )
            
            repeat_mode = config.get("repeat_mode", "off")
            if repeat_mode != "off":
                repeat_text = "🔂 Song" if repeat_mode == "song" else "🔁 Queue"
                embed.add_field(
                    name="Repeat Mode",
                    value=repeat_text,
                    inline=False
                )
            
            embed.set_footer(text="🔴 Filters applied to current song!")
            
            await message.edit(embed=embed)
            
        except Exception as e:
            log.warning(f"Failed to update now playing message for guild {guild_id}: {e}")

    async def stop_player(self, guild):
        """Helper function to fully stop playback and cleanup."""
        vc = guild.voice_client
        if vc:
            vc.stop()
        
        config = self.config_manager.get_config(guild.id)
        config["queue"].clear()
        config["repeat_mode"] = "off"  # Reset repeat mode when stopping
        self.config_manager.save_config(guild.id, config)
        await self._cleanup_now_playing(guild.id)
        
        # Clear repeat-related attributes
        if hasattr(self, '_original_queue'):
            delattr(self, '_original_queue')
        if hasattr(self, '_current_song'):
            delattr(self, '_current_song')
        
        if vc and vc.is_connected():
            await vc.disconnect()

    async def after_playback(self, interaction: discord.Interaction, error):
        """Callback function called after song playback ends."""
        if error:
            log.error(
                f"Error during playback in guild {interaction.guild.id}: {error}"
            )
        else:
            log.info(f"Finished playing song in guild {interaction.guild.id}.")
        await self._play_next(interaction)

    async def _cleanup_now_playing(self, guild_id: int):
        """Clean up the now playing message for a guild."""
        if guild_id in self.now_playing_messages:
            try:
                message = self.now_playing_messages[guild_id]
                view = MusicControlsView(self, timeout=1)
                for item in view.children:
                    item.disabled = True
                await message.edit(view=view)
            except (discord.NotFound, discord.Forbidden):
                pass
            except Exception as e:
                log.warning(f"Error cleaning up now playing message for guild {guild_id}: {e}")
            finally:
                # Always remove the message reference, even if editing failed
                self.now_playing_messages.pop(guild_id, None)

    async def _play_next(self, interaction: discord.Interaction):
        """Play the next song in the queue."""
        guild_id = interaction.guild.id
        await self._cleanup_now_playing(guild_id)
        config = self.config_manager.get_config(guild_id)
        vc = interaction.guild.voice_client

        if not vc or not vc.is_connected():
            return
        
        repeat_mode = config.get("repeat_mode", "off")
        current_song = getattr(self, '_current_song', None)
        
        if not config.get("queue") and repeat_mode != "song":
            # If queue is empty and not repeating current song
            if repeat_mode == "queue" and hasattr(self, '_original_queue'):
                # Restore the original queue for queue repeat
                config["queue"] = self._original_queue.copy()
                self.config_manager.save_config(guild_id, config)
            else:
                await interaction.channel.send(
                    embed=discord.Embed(
                        description="Queue finished.",
                        color=discord.Color.blue()
                    )
                )
                return
        
        if vc.is_playing() or vc.is_paused():
            return

        # Handle repeat modes
        if repeat_mode == "song" and current_song:
            # Repeat the current song
            song_info = current_song
        else:
            # Get next song from queue
            if not config.get("queue"):
                return
            song_info = config["queue"].pop(0)
            
            # Store original queue for queue repeat mode
            if repeat_mode == "queue" and not hasattr(self, '_original_queue'):
                self._original_queue = [song_info] + config["queue"].copy()
            
            # If repeating queue and this was the last song, restore the queue
            if repeat_mode == "queue" and not config["queue"]:
                config["queue"] = self._original_queue.copy()[1:]  # Exclude current song
        
        # Store current song for repeat functionality
        self._current_song = song_info
        self.config_manager.save_config(guild_id, config)
        log.info(f"Preparing to play '{song_info['title']}' in guild {guild_id}.")

        ffmpeg_options = FFMPEG_OPTIONS_BASE.copy()
        
        # Check for advanced filters first
        filter_manager = self.get_filter_manager(guild_id)
        advanced_filter = filter_manager.get_combined_ffmpeg_filter()
        
        # Fallback to legacy filter system if no advanced filters are active
        if not advanced_filter:
            active_filter = config.get("active_filter", "none")
            if active_filter in FFMPEG_FILTER_CHAINS:
                advanced_filter = FFMPEG_FILTER_CHAINS[active_filter]
        
        # Apply filters if any are active
        if advanced_filter:
            ffmpeg_options['options'] += f' -af "{advanced_filter}"'
        
        log.info(f"Guild {guild_id} - Generated FFMPEG options: {ffmpeg_options}")
        if advanced_filter:
            log.info(f"Guild {guild_id} - Active filters: {advanced_filter}")

        try:
            player = discord.FFmpegPCMAudio(song_info['url'], **ffmpeg_options)
            source = discord.PCMVolumeTransformer(
                player, volume=config.get("volume", 75) / 100.0
            )
            vc.play(
                source,
                after=lambda e: self.bot.loop.create_task(
                    self.after_playback(interaction, e)
                )
            )
        except Exception:
            log.exception(f"Failed to create FFmpeg player in guild {guild_id}.")
            await interaction.channel.send(
                embed=discord.Embed(
                    title="Playback Error",
                    color=discord.Color.red()
                )
            )
            return

        embed = discord.Embed(
            title="Now Playing",
            description=f"[{song_info['title']}]({song_info['webpage_url']})",
            color=discord.Color.green()
        )
        
        if song_info.get('thumbnail'):
            embed.set_thumbnail(url=song_info['thumbnail'])
        
        # Show active filters (advanced or legacy)
        enabled_filters = filter_manager.get_enabled_filters()
        if enabled_filters:
            filter_text = ", ".join(f.capitalize() for f in enabled_filters)
            embed.add_field(
                name="🎛️ Active Filters",
                value=filter_text,
                inline=False
            )
        elif config.get("active_filter", "none") != "none":
            # Show legacy filter if no advanced filters
            embed.add_field(
                name="Active Filter",
                value=f"`{config.get('active_filter').capitalize()}`",
                inline=False
            )
        
        if repeat_mode != "off":
            repeat_text = "🔂 Song" if repeat_mode == "song" else "🔁 Queue"
            embed.add_field(
                name="Repeat Mode",
                value=repeat_text,
                inline=False
            )
        
        embed.set_footer(text=f"Requested by {interaction.user.display_name}")
        
        view = EnhancedMusicControlsView(self)
        now_playing_message = await interaction.channel.send(embed=embed, view=view)
        self.now_playing_messages[guild_id] = now_playing_message

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Handle voice state updates, particularly bot disconnections."""
        if (member.id == self.bot.user.id and 
            before.channel is not None and 
            after.channel is None):
            await self._cleanup_now_playing(member.guild.id)

    @discord.app_commands.command(
        name="play", 
        description="Plays a song or adds it to the queue."
    )
    async def play(self, interaction: discord.Interaction, *, query: str):
        """Play a song or add it to the queue."""
        if not interaction.user.voice:
            await interaction.response.send_message(
                "You are not connected to a voice channel.", ephemeral=True
            )
            return
        
        vc = interaction.guild.voice_client
        if not vc:
            vc = await interaction.user.voice.channel.connect()
        elif vc.channel != interaction.user.voice.channel:
            await vc.move_to(interaction.user.voice.channel)

        await interaction.response.defer()

        try:
            with yt_dlp.YoutubeDL(YTDL_OPTIONS) as ydl:
                search_query = (
                    f"ytsearch:{query}" if not query.startswith('http') 
                    else query
                )
                info = ydl.extract_info(search_query, download=False)
        except Exception:
            log.exception(f"yt-dlp failed to process query: '{query}'")
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Error",
                    description="Could not process query.",
                    color=discord.Color.red()
                )
            )
            return

        config = self.config_manager.get_config(interaction.guild.id)
        embed = discord.Embed(color=discord.Color.blue())
        
        if 'entries' in info:
            for entry in info['entries']:
                if entry:
                    song_data = {
                        'url': entry['url'],
                        'title': entry.get('title', 'Unknown Title'),
                        'thumbnail': entry.get('thumbnail'),
                        'webpage_url': entry.get('webpage_url')
                    }
                    config["queue"].append(song_data)
            
            embed.title = "Playlist Added"
            embed.description = (
                f"Added **{len(info['entries'])} songs** from `{info['title']}`"
            )
        else:
            song_data = {
                'url': info['url'],
                'title': info.get('title', 'Unknown Title'),
                'thumbnail': info.get('thumbnail'),
                'webpage_url': info.get('webpage_url')
            }
            config["queue"].append(song_data)
            
            embed.title = "Added to Queue"
            embed.description = (
                f"[{info.get('title', 'Unknown Title')}]"
                f"({info.get('webpage_url')})"
            )
        
        await interaction.followup.send(embed=embed)
        self.config_manager.save_config(interaction.guild.id, config)

        if not vc.is_playing() and not vc.is_paused():
            await self._play_next(interaction)

    @discord.app_commands.command(
        name="pause", 
        description="Pauses the current song."
    )
    async def pause(self, interaction: discord.Interaction):
        """Pause the current song."""
        vc = interaction.guild.voice_client
        
        if vc and vc.is_playing():
            vc.pause()
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="Playback paused. ⏸️",
                    color=discord.Color.orange()
                )
            )
        else:
            await interaction.response.send_message(
                "Nothing is playing.", ephemeral=True
            )
            
    @discord.app_commands.command(
        name="resume", 
        description="Resumes the current song."
    )
    async def resume(self, interaction: discord.Interaction):
        """Resume the current song."""
        vc = interaction.guild.voice_client
        
        if vc and vc.is_paused():
            vc.resume()
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="Playback resumed. ▶️",
                    color=discord.Color.green()
                )
            )
        else:
            await interaction.response.send_message(
                "Playback is not paused.", ephemeral=True
            )
            
    @discord.app_commands.command(
        name="stop", 
        description="Stops playback, clears queue, and leaves."
    )
    async def stop(self, interaction: discord.Interaction):
        """Stop playback, clear queue, and disconnect."""
        if interaction.guild.voice_client:
            await self.stop_player(interaction.guild)
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="Playback stopped. Goodbye! 👋",
                    color=discord.Color.red()
                )
            )
        else:
            await interaction.response.send_message(
                "I'm not in a voice channel.", ephemeral=True
            )
    
    @discord.app_commands.command(
        name="skip", 
        description="Skips to the next song in the queue."
    )
    async def skip(self, interaction: discord.Interaction):
        """Skip to the next song in the queue."""
        vc = interaction.guild.voice_client
        
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop()
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="Skipped to the next song! ⏭️",
                    color=discord.Color.blue()
                )
            )
        else:
            await interaction.response.send_message(
                "I'm not playing anything.", ephemeral=True
            )

    @discord.app_commands.command(
        name="queue", 
        description="Shows the current song queue."
    )
    async def queue(self, interaction: discord.Interaction):
        """Show the current song queue."""
        config = self.config_manager.get_config(interaction.guild.id)
        queue = config.get("queue", [])
        
        if not queue:
            await interaction.response.send_message(
                "The queue is empty.", ephemeral=True
            )
            return
        
        embed = discord.Embed(title="Song Queue", color=discord.Color.purple())
        queue_list = [
            f"`{i+1}.` [{song['title']}]({song['webpage_url']})"
            for i, song in enumerate(queue[:10])
        ]
        embed.description = "\n".join(queue_list)
        
        if len(queue) > 10:
            embed.set_footer(text=f"...and {len(queue) - 10} more.")
        
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    """Set up the Playback cog."""
    await bot.add_cog(PlaybackCog(bot))
