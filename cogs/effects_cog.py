import discord
from discord.ext import commands
import logging

from utils.shared_managers import shared_managers

log = logging.getLogger(__name__)

class EffectsCog(commands.Cog, name="Audio Effects"):
    """Commands to apply audio effects and control volume."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Use shared manager instead of creating new instance
        self.config_manager = shared_managers.config_manager

    async def _toggle_filter(self, interaction: discord.Interaction, filter_name: str):
        """Helper function to toggle a filter on or off."""
        log.info(f"'{interaction.user}' attempting to toggle filter '{filter_name}' in guild {interaction.guild.id}")
        config = self.config_manager.get_config(interaction.guild.id)
        current_filter = config.get("active_filter", "none")

        display_name = filter_name.capitalize()
        
        if current_filter == filter_name:
            # Filter is active, turn it off
            config["active_filter"] = "none"
            status = "OFF"
            color = discord.Color.dark_grey()
            emoji = "✅"
        else:
            # Filter is not active, turn it on
            config["active_filter"] = filter_name
            status = "ON"
            color = discord.Color.green()
            emoji = "🔊"
        
        self.config_manager.save_config(interaction.guild.id, config)

        embed = discord.Embed(
            description=f"{emoji} **{display_name}** filter turned **{status}**!",
            color=color
        )
        embed.set_footer(text="Effect applies to the next song. Use /skip to apply now.")
        await interaction.response.send_message(embed=embed)

    @discord.app_commands.command(name="volume", description="Sets the playback volume (0-150).")
    @discord.app_commands.describe(level="A number between 0 and 150")
    async def volume(self, interaction: discord.Interaction, level: int):
        if not 0 <= level <= 150:
            await interaction.response.send_message("Volume must be between 0 and 150.", ephemeral=True)
            return

        config = self.config_manager.get_config(interaction.guild.id)
        config["volume"] = level
        self.config_manager.save_config(interaction.guild.id, config)
        
        vc = interaction.guild.voice_client
        if vc and vc.source:
            vc.source.volume = level / 100.0
        
        await interaction.response.send_message(embed=discord.Embed(description=f"Volume set to **{level}%**", color=discord.Color.blue()))

    # --- Toggleable Filter Commands ---
    @discord.app_commands.command(name="nightcore", description="Toggles the nightcore (speed/pitch up) effect.")
    async def nightcore(self, interaction: discord.Interaction):
        await self._toggle_filter(interaction, "nightcore")

    @discord.app_commands.command(name="slowed", description="Toggles the slowed down effect.")
    async def slowed(self, interaction: discord.Interaction):
        await self._toggle_filter(interaction, "slowed")

    @discord.app_commands.command(name="bassboost", description="Toggles the bass boost effect.")
    async def bassboost(self, interaction: discord.Interaction):
        await self._toggle_filter(interaction, "bassboost")

    @discord.app_commands.command(name="8d", description="Toggles the 8D (surround sound) audio effect.")
    async def eight_d(self, interaction: discord.Interaction):
        await self._toggle_filter(interaction, "8d")

    @discord.app_commands.command(
        name="repeat", 
        description="Toggle repeat mode (off/song/queue)."
    )
    async def repeat_mode(self, interaction: discord.Interaction):
        """Toggle repeat mode between off, song, and queue."""
        config = self.config_manager.get_config(interaction.guild.id)
        current_mode = config.get("repeat_mode", "off")
        
        # Cycle through repeat modes: off -> song -> queue -> off
        if current_mode == "off":
            new_mode = "song"
            emoji = "🔂"
            description = "Repeat mode set to **Song** - Current song will repeat"
        elif current_mode == "song":
            new_mode = "queue"
            emoji = "🔁"
            description = "Repeat mode set to **Queue** - Entire queue will repeat"
        else:  # queue
            new_mode = "off"
            emoji = "⏹️"
            description = "Repeat mode **disabled**"
        
        config["repeat_mode"] = new_mode
        self.config_manager.save_config(interaction.guild.id, config)
        
        embed = discord.Embed(
            description=f"{emoji} {description}",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(EffectsCog(bot))
