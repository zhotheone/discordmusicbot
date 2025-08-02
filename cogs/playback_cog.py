"""Playback Cog for Discord Bot - Handles music playback controls and filters."""

import discord
import logging
from discord.ext import commands

from utils.shared_managers import shared_managers
from utils.advanced_filters import AdvancedFilterManager
from utils.views import MusicControlsView
from utils.advanced_views import EnhancedMusicControlsView

log = logging.getLogger(__name__)

class PlaybackCog(commands.Cog, name="Playback Controls"):
    """Commands to play, stop, and manage the music queue."""
    
    def __init__(self, bot: commands.Bot):
        """Initialize the Playback cog."""
        self.bot = bot
        # Use shared services instead of handling business logic directly
        self.music_service = shared_managers.music_service
        self.filter_service = shared_managers.filter_service
        self.playback_service = shared_managers.playback_service
        self.now_playing_messages = {}
    
    def get_filter_manager(self, guild_id: int) -> AdvancedFilterManager:
        """Get or create advanced filter manager for a guild."""
        return self.filter_service.get_advanced_filter_manager(guild_id)
    
    def save_filter_state(self, guild_id: int):
        """Save current filter state to config."""
        self.filter_service.save_advanced_filter_state(guild_id)
    
    async def apply_filters_to_current_song(self, guild_id: int, channel=None):
        """Apply current filter settings to the currently playing song."""
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return False
        
        vc = guild.voice_client
        success = await self.playback_service.apply_filters_to_current_song(guild_id, vc)
        
        if success and channel:
            embed = discord.Embed(
                description="🎛️ **Filters applied to current song!**",
                color=discord.Color.green()
            )
            try:
                await channel.send(embed=embed)
            except:
                pass  # Ignore send errors
        
        return success

    async def after_playback(self, interaction: discord.Interaction, error):
        """Handle after playback completion."""
        if error:
            log.error(f"Error during playback in guild {interaction.guild.id}: {error}")
        else:
            log.info(f"Finished playing song in guild {interaction.guild.id}.")
        await self._play_next(interaction)

    async def _cleanup_now_playing(self, guild_id: int):
        """Clean up now playing message UI."""
        if guild_id in self.now_playing_messages:
            try:
                message = self.now_playing_messages[guild_id]
                view = MusicControlsView(self, timeout=1)
                for item in view.children:
                    item.disabled = True
                await message.edit(view=view)
            except (discord.NotFound, discord.Forbidden):
                pass
            finally:
                # Safely remove the guild_id if it still exists
                self.now_playing_messages.pop(guild_id, None)

    async def _play_next(self, interaction: discord.Interaction):
        """Play the next song in the queue."""
        guild_id = interaction.guild.id
        await self._cleanup_now_playing(guild_id)
        
        voice_client = interaction.guild.voice_client
        if not voice_client or not voice_client.is_connected():
            log.info(f"Voice client not connected in guild {guild_id}")
            return

        # Use playback service to handle the actual playback
        success = await self.playback_service.play_song(
            guild_id, 
            voice_client, 
            after_callback=lambda e: self.bot.loop.create_task(
                self.after_playback(interaction, e)
            )
        )
        
        if not success:
            log.info(f"No more songs in queue for guild {guild_id}")
            return

        # Get current song info for display
        current_song = self.playback_service.get_current_song(guild_id)
        if not current_song:
            return

        # Create and send now playing message
        embed = discord.Embed(
            title="🎵 Now Playing",
            description=f"**{current_song.title}**",
            color=discord.Color.blue()
        )
        
        if current_song.uploader:
            embed.add_field(name="Artist", value=current_song.uploader, inline=True)
        
        if current_song.duration:
            embed.add_field(
                name="Duration", 
                value=f"{current_song.duration // 60}:{current_song.duration % 60:02d}", 
                inline=True
            )
        
        if current_song.thumbnail:
            embed.set_thumbnail(url=current_song.thumbnail)

        view = EnhancedMusicControlsView(self)
        
        try:
            now_playing_message = await interaction.channel.send(embed=embed, view=view)
            self.now_playing_messages[guild_id] = now_playing_message
        except Exception as e:
            log.exception(f"Failed to send now playing message in guild {guild_id}")

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

        # Auto-apply user's saved preferences when they start playing music
        try:
            user_settings = shared_managers.user_settings_manager.get_user_settings(interaction.user.id)
            # Check if user has any non-default preferences
            if (user_settings.get("volume") != 75 or 
                user_settings.get("repeat_mode") != "off" or 
                user_settings.get("filters")):
                
                # Apply user preferences automatically
                filter_manager = self.get_filter_manager(interaction.guild.id)
                shared_managers.user_settings_manager.apply_user_preferences(
                    interaction.user.id,
                    interaction.guild.id,
                    self.music_service,
                    filter_manager
                )
                self.save_filter_state(interaction.guild.id)
                
                # Send a subtle notification
                await interaction.followup.send(
                    embed=discord.Embed(
                        description="🔄 **Applied your saved preferences** (volume, repeat, filters)",
                        color=discord.Color.blue()
                    ),
                    ephemeral=True
                )
        except Exception as e:
            # Don't fail the main operation if preference loading fails
            log.warning(f"Failed to auto-apply user preferences for {interaction.user.id}: {e}")

        # Use music service to search for the song
        song = await self.music_service.search_music(query)
        if not song:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Error",
                    description="Could not process query.",
                    color=discord.Color.red()
                )
            )
            return

        # Get current playback state
        playback_info = self.playback_service.get_playback_info(interaction.guild.id)
        
        if not playback_info["is_playing"] and not playback_info["queue"]:
            # Nothing playing and queue is empty - start immediately
            self.music_service.add_to_queue(interaction.guild.id, song)
            await self._play_next(interaction)
            
            embed = discord.Embed(
                description=f"🎵 **Now playing:** {song.title}",
                color=discord.Color.green()
            )
        else:
            # Add to queue
            self.music_service.add_to_queue(interaction.guild.id, song)
            queue_position = len(playback_info["queue"])
            
            embed = discord.Embed(
                description=f"✅ **Added to queue:** {song.title}\n📋 **Position:** {queue_position}",
                color=discord.Color.blue()
            )
        
        await interaction.followup.send(embed=embed)

    @discord.app_commands.command(
        name="queue", 
        description="Shows the current music queue."
    )
    async def queue(self, interaction: discord.Interaction):
        """Display the current music queue."""
        playback_info = self.playback_service.get_playback_info(interaction.guild.id)
        
        embed = discord.Embed(title="🎵 Music Queue", color=discord.Color.blue())
        
        if playback_info["current_song"]:
            embed.add_field(
                name="🎵 Now Playing",
                value=playback_info["current_song"].title,
                inline=False
            )
        
        if playback_info["queue"]:
            queue_text = ""
            for i, song in enumerate(playback_info["queue"][:10], 1):
                queue_text += f"{i}. {song.title}\n"
            
            if len(playback_info["queue"]) > 10:
                queue_text += f"... and {len(playback_info['queue']) - 10} more"
            
            embed.add_field(name="📋 Queue", value=queue_text, inline=False)
        else:
            embed.add_field(name="📋 Queue", value="Empty", inline=False)
        
        embed.add_field(
            name="🔁 Repeat Mode", 
            value=playback_info["repeat_mode"].value.title(), 
            inline=True
        )
        embed.add_field(
            name="🔊 Volume", 
            value=f"{playback_info['volume']}%", 
            inline=True
        )
        
        await interaction.response.send_message(embed=embed)

    @discord.app_commands.command(
        name="skip", 
        description="Skips the current song."
    )
    async def skip(self, interaction: discord.Interaction):
        """Skip the current song."""
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
        name="stop", 
        description="Stops playback and clears the queue."
    )
    async def stop(self, interaction: discord.Interaction):
        """Stop playback and clear the queue."""
        vc = interaction.guild.voice_client
        if vc and vc.is_connected():
            # Clear queue and current song using music service
            self.music_service.clear_queue(interaction.guild.id)
            self.playback_service.clear_current_song(interaction.guild.id)
            
            await vc.disconnect()
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="⏹️ **Playback stopped and queue cleared.**",
                    color=discord.Color.red()
                )
            )
        else:
            await interaction.response.send_message(
                "I'm not in a voice channel.", ephemeral=True
            )

    @discord.app_commands.command(
        name="pause", 
        description="Pauses or resumes playback."
    )
    async def pause(self, interaction: discord.Interaction):
        """Pause or resume playback."""
        vc = interaction.guild.voice_client
        if not vc or not vc.is_connected():
            await interaction.response.send_message(
                "I'm not in a voice channel.", ephemeral=True
            )
            return
        
        if vc.is_playing():
            vc.pause()
            self.playback_service.set_playback_state(interaction.guild.id, False, True)
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="⏸️ **Playback paused.**",
                    color=discord.Color.orange()
                )
            )
        elif vc.is_paused():
            vc.resume()
            self.playback_service.set_playback_state(interaction.guild.id, True, False)
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="▶️ **Playback resumed.**",
                    color=discord.Color.green()
                )
            )
        else:
            await interaction.response.send_message(
                "Nothing is currently playing.", ephemeral=True
            )

    @discord.app_commands.command(
        name="repeat", 
        description="Toggle repeat mode (off/song/queue)."
    )
    async def repeat_mode(self, interaction: discord.Interaction):
        """Toggle repeat mode between off, song, and queue."""
        from services.music_service import RepeatMode
        
        current_info = self.playback_service.get_playback_info(interaction.guild.id)
        current_mode = current_info["repeat_mode"]
        
        # Cycle through repeat modes: off -> song -> off
        if current_mode == RepeatMode.OFF:
            new_mode = RepeatMode.SONG
            emoji = "🔂"
            description = "Repeat mode set to **Song** - Current song will repeat"
        else:  # song
            new_mode = RepeatMode.OFF
            emoji = "⏹️"
            description = "Repeat mode **disabled**"
        
        self.music_service.set_repeat_mode(interaction.guild.id, new_mode)
        
        embed = discord.Embed(
            description=f"{emoji} {description}",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)

async def setup(bot: commands.Bot):
    """Setup function for the cog."""
    await bot.add_cog(PlaybackCog(bot))
