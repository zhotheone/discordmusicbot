import discord

class MusicControlsView(discord.ui.View):
    """A View with music control buttons that interacts with the PlaybackCog."""
    def __init__(self, cog, *, timeout=None):
        super().__init__(timeout=timeout)
        self.cog = cog # The cog instance (PlaybackCog)

    @discord.ui.button(label="Pause", style=discord.ButtonStyle.secondary, emoji="⏸️")
    async def pause_resume(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if not vc or not vc.is_connected():
            return await interaction.response.send_message("I'm not in a voice channel!", ephemeral=True)
            
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

    @discord.ui.button(label="Skip", style=discord.ButtonStyle.primary, emoji="⏭️")
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop()
            await interaction.response.send_message("Skipped!", ephemeral=True, delete_after=5)
        else:
            await interaction.response.send_message("Not playing anything to skip.", ephemeral=True)

    @discord.ui.button(label="Stop", style=discord.ButtonStyle.danger, emoji="⏹️")
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if vc and vc.is_connected():
            # Stop the player, clear queue, and disconnect
            await self.cog.stop_player(interaction.guild)
            await interaction.response.send_message("Playback stopped and queue cleared.", ephemeral=True, delete_after=10)
            
            # Disable buttons on the original message after stopping
            for item in self.children:
                item.disabled = True
            await interaction.message.edit(view=self)
        else:
            await interaction.response.send_message("I'm not in a voice channel.", ephemeral=True)
