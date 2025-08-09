import logging
from typing import Optional, List

import discord
from discord.ext import commands

from core.dependency_injection import DIContainer
from domain.services.music_service import MusicService
from domain.services.filter_service import FilterService
from domain.entities.playlist import RepeatMode
from domain.entities.track import Track

logger = logging.getLogger(__name__)


class FilterSelect(discord.ui.Select):
    """Dropdown for selecting audio filters."""
    
    def __init__(self, container: DIContainer, guild_id: int, current_filters: List[str] = None):
        self.container = container
        self.guild_id = guild_id
        self.filter_service: FilterService = container.get(FilterService)
        self.current_filters = current_filters or []
        
        # Available filters with descriptions
        filter_options = [
            discord.SelectOption(
                label="Clear All Filters",
                value="clear",
                description="Remove all active filters",
                emoji="🔄"
            ),
            discord.SelectOption(
                label="Bass Boost",
                value="bass_boost", 
                description="Enhance low frequencies",
                emoji="🔊"
            ),
            discord.SelectOption(
                label="Reverb",
                value="reverb",
                description="Add echo/reverb effect", 
                emoji="🌊"
            ),
            discord.SelectOption(
                label="Slow",
                value="slow",
                description="Slow down playback (0.75x speed)",
                emoji="🐌"
            ),
            discord.SelectOption(
                label="8D Audio",
                value="8d",
                description="Surround sound effect",
                emoji="🎧"
            ),
            discord.SelectOption(
                label="Nightcore",
                value="nightcore",
                description="Speed up with pitch increase",
                emoji="⚡"
            ),
            discord.SelectOption(
                label="Vaporwave", 
                value="vaporwave",
                description="Slow down with lower pitch",
                emoji="🌙"
            )
        ]
        
        super().__init__(
            placeholder="🎛️ Select audio filters to apply...",
            min_values=1,
            max_values=3,  # Allow multiple filter selection
            options=filter_options
        )
    
    async def callback(self, interaction: discord.Interaction):
        """Handle filter selection."""
        await interaction.response.defer()
        
        try:
            selected_filters = self.values
            
            # Handle clear all filters
            if "clear" in selected_filters:
                success = await self.filter_service.clear_filters(self.guild_id)
                if success:
                    embed = discord.Embed(
                        title="🔄 Filters Cleared",
                        description="All audio filters have been removed",
                        color=discord.Color.green()
                    )
                else:
                    embed = discord.Embed(
                        title="❌ Filter Error", 
                        description="Failed to clear filters",
                        color=discord.Color.red()
                    )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # Apply selected filters
            applied_filters = []
            failed_filters = []
            
            for filter_name in selected_filters:
                success = await self.filter_service.apply_filter(self.guild_id, filter_name)
                if success:
                    applied_filters.append(filter_name)
                else:
                    failed_filters.append(filter_name)
            
            # Create response embed
            if applied_filters:
                filter_emojis = {
                    "bass_boost": "🔊", "reverb": "🌊", "slow": "🐌", 
                    "8d": "🎧", "nightcore": "⚡", "vaporwave": "🌙"
                }
                
                applied_text = ", ".join([f"{filter_emojis.get(f, '🎛️')} {f.replace('_', ' ').title()}" for f in applied_filters])
                
                embed = discord.Embed(
                    title="🎛️ Filters Applied",
                    description=f"Applied: {applied_text}",
                    color=discord.Color.blue()
                )
                
                if failed_filters:
                    failed_text = ", ".join([f.replace("_", " ").title() for f in failed_filters])
                    embed.add_field(
                        name="⚠️ Failed",
                        value=failed_text,
                        inline=False
                    )
            else:
                embed = discord.Embed(
                    title="❌ Filter Error",
                    description="Failed to apply any filters",
                    color=discord.Color.red()
                )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error in filter selection: {e}")
            await interaction.followup.send("❌ An error occurred while applying filters", ephemeral=True)


class RepeatSelect(discord.ui.Select):
    """Dropdown for selecting repeat modes."""
    
    def __init__(self, container: DIContainer, guild_id: int, current_mode: RepeatMode = RepeatMode.OFF):
        self.container = container
        self.guild_id = guild_id
        self.music_service: MusicService = container.get(MusicService)
        
        options = [
            discord.SelectOption(
                label="Off",
                value="off",
                description="No repeat",
                emoji="➡️",
                default=(current_mode == RepeatMode.OFF)
            ),
            discord.SelectOption(
                label="Track",
                value="track", 
                description="Repeat current track",
                emoji="🔂",
                default=(current_mode == RepeatMode.TRACK)
            ),
            discord.SelectOption(
                label="Queue",
                value="queue",
                description="Repeat entire queue", 
                emoji="🔁",
                default=(current_mode == RepeatMode.QUEUE)
            )
        ]
        
        super().__init__(
            placeholder="🔁 Select repeat mode...",
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        """Handle repeat mode selection."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            mode = RepeatMode(self.values[0])
            success = await self.music_service.set_repeat_mode(self.guild_id, mode)
            
            if success:
                mode_emojis = {"off": "➡️", "track": "🔂", "queue": "🔁"}
                embed = discord.Embed(
                    title=f"{mode_emojis[mode.value]} Repeat Mode",
                    description=f"Set to: **{mode.value.title()}**",
                    color=discord.Color.blue()
                )
            else:
                embed = discord.Embed(
                    title="❌ Repeat Error",
                    description="Failed to set repeat mode",
                    color=discord.Color.red()
                )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error setting repeat mode: {e}")
            await interaction.followup.send("❌ An error occurred while setting repeat mode", ephemeral=True)


class MusicControlView(discord.ui.View):
    """Interactive music control panel with buttons and dropdowns."""
    
    def __init__(self, container: DIContainer, guild_id: int, current_track: Optional[Track] = None):
        super().__init__(timeout=300)  # 5 minute timeout
        self.container = container
        self.guild_id = guild_id
        self.music_service: MusicService = container.get(MusicService)
        self.filter_service: FilterService = container.get(FilterService)
        self.current_track = current_track
        
        # Get current state
        playlist = self.music_service.get_playlist(guild_id)
        is_playing = self.music_service.is_playing(guild_id)
        current_repeat_mode = playlist.repeat_mode if playlist else RepeatMode.OFF
        
        # Add dropdowns
        self.add_item(FilterSelect(container, guild_id))
        self.add_item(RepeatSelect(container, guild_id, current_repeat_mode))
        
        # Set initial button states
        self.play_pause_button.emoji = "⏸️" if is_playing else "▶️"
        self.play_pause_button.label = "Pause" if is_playing else "Resume"
        self.play_pause_button.style = discord.ButtonStyle.success if is_playing else discord.ButtonStyle.secondary
    
    @discord.ui.button(label="Resume", emoji="▶️", style=discord.ButtonStyle.secondary, row=2)
    async def play_pause_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Toggle play/pause."""
        await interaction.response.defer()
        
        try:
            is_playing = self.music_service.is_playing(self.guild_id)
            
            if is_playing:
                success = await self.music_service.pause(self.guild_id)
                action = "paused"
                new_emoji = "▶️"
                new_label = "Resume"
                new_style = discord.ButtonStyle.secondary
                color = discord.Color.orange()
            else:
                success = await self.music_service.resume(self.guild_id)
                action = "resumed"
                new_emoji = "⏸️" 
                new_label = "Pause"
                new_style = discord.ButtonStyle.success
                color = discord.Color.green()
            
            if success:
                # Update button
                button.emoji = new_emoji
                button.label = new_label
                button.style = new_style
                
                embed = discord.Embed(
                    title=f"{new_emoji} Playback {action.title()}",
                    color=color
                )
                
                if self.current_track:
                    embed.description = f"**{self.current_track.display_title}**"
                
                await interaction.edit_original_response(embed=embed, view=self)
            else:
                await interaction.followup.send("❌ Nothing is currently playing!", ephemeral=True)
                
        except Exception as e:
            logger.error(f"Error in play/pause: {e}")
            await interaction.followup.send("❌ An error occurred", ephemeral=True)
    
    @discord.ui.button(label="Skip", emoji="⏭️", style=discord.ButtonStyle.primary, row=2)
    async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Skip to next track."""
        await interaction.response.defer()
        
        try:
            next_track = await self.music_service.skip(self.guild_id)
            
            if next_track:
                embed = discord.Embed(
                    title="⏭️ Skipped",
                    description=f"Now playing: **{next_track.display_title}**",
                    color=discord.Color.blue()
                )
                self.current_track = next_track
                
                # Update play button state
                self.play_pause_button.emoji = "⏸️"
                self.play_pause_button.label = "Pause"
                self.play_pause_button.style = discord.ButtonStyle.success
                
                await interaction.edit_original_response(embed=embed, view=self)
            else:
                embed = discord.Embed(
                    title="⏭️ Skipped",
                    description="No more tracks in queue",
                    color=discord.Color.orange()
                )
                await interaction.edit_original_response(embed=embed, view=self)
                
        except Exception as e:
            logger.error(f"Error skipping track: {e}")
            await interaction.followup.send("❌ An error occurred while skipping", ephemeral=True)
    
    @discord.ui.button(label="Stop", emoji="⏹️", style=discord.ButtonStyle.danger, row=2)
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Stop playback and clear queue."""
        await interaction.response.defer()
        
        try:
            success = await self.music_service.stop(self.guild_id)
            
            if success:
                # Disconnect from voice
                if interaction.guild.voice_client:
                    await interaction.guild.voice_client.disconnect()
                
                embed = discord.Embed(
                    title="⏹️ Stopped",
                    description="Playback stopped and queue cleared",
                    color=discord.Color.red()
                )
                
                # Disable all buttons
                for item in self.children:
                    if isinstance(item, discord.ui.Button):
                        item.disabled = True
                
                await interaction.edit_original_response(embed=embed, view=self)
            else:
                await interaction.followup.send("❌ Nothing was playing!", ephemeral=True)
                
        except Exception as e:
            logger.error(f"Error stopping playback: {e}")
            await interaction.followup.send("❌ An error occurred while stopping", ephemeral=True)
    
    @discord.ui.button(label="Queue", emoji="📋", style=discord.ButtonStyle.secondary, row=2)
    async def queue_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show current queue."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            playlist = self.music_service.get_playlist(self.guild_id)
            
            if not playlist or not playlist.tracks:
                await interaction.followup.send("📭 Queue is empty!", ephemeral=True)
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
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error showing queue: {e}")
            await interaction.followup.send("❌ An error occurred while fetching queue", ephemeral=True)
    
    async def on_timeout(self):
        """Disable all items when view times out."""
        for item in self.children:
            item.disabled = True
        
        # Note: We can't edit the message here as we don't have the interaction reference
        logger.debug(f"Music control view timed out for guild {self.guild_id}")