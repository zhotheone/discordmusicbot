import discord
from discord.ext import commands
import logging

from utils.shared_managers import shared_managers
from services.filter_service import FilterToggleResult

log = logging.getLogger(__name__)

class EffectsCog(commands.Cog, name="Audio Effects"):
    """Commands to apply audio effects and control volume."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Use shared services
        self.filter_service = shared_managers.filter_service

    async def _toggle_filter(self, interaction: discord.Interaction, filter_name: str):
        """Helper function to toggle a filter on or off."""
        log.info(f"'{interaction.user}' attempting to toggle filter '{filter_name}' in guild {interaction.guild.id}")
        
        # Use filter service to handle business logic
        result, message = self.filter_service.toggle_legacy_filter(interaction.guild.id, filter_name)
        
        # Determine Discord response based on service result
        if result == FilterToggleResult.ENABLED:
            color = discord.Color.green()
            emoji = "🔊"
        elif result == FilterToggleResult.DISABLED:
            color = discord.Color.dark_grey()
            emoji = "✅"
        else:  # ERROR
            color = discord.Color.red()
            emoji = "❌"

        embed = discord.Embed(
            description=f"{emoji} {message}",
            color=color
        )
        
        if result != FilterToggleResult.ERROR:
            embed.set_footer(text="Effect applies to the next song. Use /skip to apply now.")
        
        await interaction.response.send_message(embed=embed)

    @discord.app_commands.command(name="volume", description="Sets the playback volume (0-150).")
    @discord.app_commands.describe(level="A number between 0 and 150")
    async def volume(self, interaction: discord.Interaction, level: int):
        """Set the playback volume."""
        log.info(f"Volume set to {level} in guild {interaction.guild.id} by {interaction.user}")
        
        # Use filter service to handle business logic
        success, message = self.filter_service.set_volume(interaction.guild.id, level)
        
        if success:
            # Update voice client volume if currently playing
            voice_client = interaction.guild.voice_client
            if voice_client and voice_client.source:
                voice_client.source.volume = level / 100.0
            
            # Save user's volume preference
            shared_managers.user_settings_manager.save_user_volume(interaction.user.id, level)
            
            embed = discord.Embed(
                description=f"🔊 {message}",
                color=discord.Color.blue()
            )
            
            # Add memorization notice
            embed.add_field(
                name="💾 Saved",
                value="Your volume preference has been memorized!",
                inline=False
            )
        else:
            embed = discord.Embed(
                description=f"❌ {message}",
                color=discord.Color.red()
            )
        
        await interaction.response.send_message(embed=embed)

    @discord.app_commands.command(name="nightcore", description="Toggles the nightcore (speed/pitch up) effect.")
    async def nightcore(self, interaction: discord.Interaction):
        """Toggle nightcore effect."""
        await self._toggle_filter(interaction, "nightcore")

    @discord.app_commands.command(name="slowed", description="Toggles the slowed down effect.")
    async def slowed(self, interaction: discord.Interaction):
        """Toggle slowed effect."""
        await self._toggle_filter(interaction, "slowed")

    @discord.app_commands.command(name="bassboost", description="Toggles the bass boost effect.")
    async def bassboost(self, interaction: discord.Interaction):
        """Toggle bass boost effect."""
        await self._toggle_filter(interaction, "bassboost")

    @discord.app_commands.command(name="8d", description="Toggles the 8D (surround sound) audio effect.")
    async def eight_d(self, interaction: discord.Interaction):
        """Toggle 8D audio effect."""
        await self._toggle_filter(interaction, "8d")

    @discord.app_commands.command(
        name="tremolo", 
        description="Toggles the tremolo (amplitude modulation) effect."
    )
    async def tremolo(self, interaction: discord.Interaction):
        """Toggle tremolo effect."""
        await self._toggle_filter(interaction, "tremolo")

    @discord.app_commands.command(name="vibrato", description="Toggles the vibrato (frequency modulation) effect.")
    async def vibrato(self, interaction: discord.Interaction):
        """Toggle vibrato effect."""
        await self._toggle_filter(interaction, "vibrato")

    @discord.app_commands.command(name="reverse", description="Toggles the reverse audio effect.")
    async def reverse(self, interaction: discord.Interaction):
        """Toggle reverse effect."""
        await self._toggle_filter(interaction, "reverse")

async def setup(bot: commands.Bot):
    """Setup function for the cog."""
    await bot.add_cog(EffectsCog(bot))
