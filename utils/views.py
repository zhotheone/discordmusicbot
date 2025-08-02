"""Discord UI Views for music controls."""

import discord
from services.music_service import RepeatMode
from utils.shared_managers import shared_managers

class MusicControlsView(discord.ui.View):
    """A View with music control buttons that interacts with the PlaybackCog."""
    
    def __init__(self, cog, *, timeout=None):
        """Initialize the music controls view."""
        super().__init__(timeout=timeout)
        self.cog = cog  # The cog instance (PlaybackCog)
        self._setup_repeat_button()

    @discord.ui.button(
        label="Pause", 
        style=discord.ButtonStyle.secondary, 
        emoji="⏸️"
    )
    async def pause_resume(
        self, 
        interaction: discord.Interaction, 
        button: discord.ui.Button
    ):
        """Handle pause/resume button interaction."""
        vc = interaction.guild.voice_client
        if not vc or not vc.is_connected():
            return await interaction.response.send_message(
                "I'm not in a voice channel!", ephemeral=True
            )
            
        if vc.is_playing():
            vc.pause()
            button.label = "Resume"
            button.emoji = "▶️"
            await interaction.response.edit_message(view=self)
        elif vc.is_paused():
            vc.resume()
            button.label = "Pause"
            button.emoji = "⏸️"
            await interaction.response.edit_message(view=self)
        else:
            await interaction.response.defer()

    @discord.ui.button(
        label="Skip", 
        style=discord.ButtonStyle.primary, 
        emoji="⏭️"
    )
    async def skip(
        self, 
        interaction: discord.Interaction, 
        button: discord.ui.Button
    ):
        """Handle skip button interaction."""
        vc = interaction.guild.voice_client
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop()
            await interaction.response.send_message(
                "Skipped!", ephemeral=True, delete_after=5
            )
        else:
            await interaction.response.send_message(
                "Not playing anything to skip.", ephemeral=True
            )

    @discord.ui.button(
        label="Stop", 
        style=discord.ButtonStyle.danger, 
        emoji="⏹️"
    )
    async def stop(
        self, 
        interaction: discord.Interaction, 
        button: discord.ui.Button
    ):
        """Handle stop button interaction."""
        vc = interaction.guild.voice_client
        if vc and vc.is_connected():
            # Clear queue and current song using the cog's services
            if hasattr(self.cog, 'music_service'):
                self.cog.music_service.clear_queue(interaction.guild.id)
            if hasattr(self.cog, 'playback_service'):
                self.cog.playback_service.clear_current_song(interaction.guild.id)
            
            # Disconnect from voice channel
            await vc.disconnect()
            
            await interaction.response.send_message(
                "Playback stopped and queue cleared.",
                ephemeral=True,
                delete_after=10
            )
            
            # Disable buttons on the original message after stopping
            for item in self.children:
                item.disabled = True
            await interaction.message.edit(view=self)
        else:
            await interaction.response.send_message(
                "I'm not in a voice channel.", ephemeral=True
            )

    @discord.ui.button(
        label="Repeat: Off", 
        style=discord.ButtonStyle.secondary, 
        emoji="🔁"
    )
    async def repeat_toggle(
        self, 
        interaction: discord.Interaction, 
        button: discord.ui.Button
    ):
        """Handle repeat mode toggle button interaction."""
        # Get current repeat mode from the music service
        current_info = self.cog.playback_service.get_playback_info(interaction.guild.id)
        current_mode = current_info["repeat_mode"]
        
        # Cycle through repeat modes: off -> song -> off
        if current_mode == RepeatMode.OFF:
            new_mode = RepeatMode.SONG
            button.label = "Repeat: Song"
            button.emoji = "🔂"
            button.style = discord.ButtonStyle.success
        else:  # song
            new_mode = RepeatMode.OFF
            button.label = "Repeat: Off"
            button.emoji = "🔁"
            button.style = discord.ButtonStyle.secondary
        
        # Set the new repeat mode using the music service
        self.cog.music_service.set_repeat_mode(interaction.guild.id, new_mode)
        
        # Save user's repeat mode preference
        shared_managers.user_settings_manager.save_user_repeat_mode(interaction.user.id, new_mode)
        
        await interaction.response.edit_message(view=self)
    
    def _setup_repeat_button(self):
        """Set up the repeat button with the current guild's repeat mode."""
        # This will be called when creating the view in a guild context
        pass  # We'll update the button state when the message is sent
