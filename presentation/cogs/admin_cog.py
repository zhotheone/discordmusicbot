import logging
import discord
from discord.ext import commands
from discord import app_commands
from core.dependency_injection import DIContainer

logger = logging.getLogger(__name__)


class AdminCog(commands.Cog):
    """Administrative commands."""
    
    def __init__(self, container: DIContainer):
        self.container = container
    
    @app_commands.command(name="sync", description="Sync application commands (Admin only)")
    async def sync_commands(self, interaction: discord.Interaction) -> None:
        """Manually sync application commands."""
        # Check if user has administrator permissions
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ You need administrator permissions to use this command!", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            logger.info(f"Manual command sync requested by {interaction.user} in guild {interaction.guild.id}")
            synced = await interaction.client.tree.sync()
            await interaction.followup.send(f"✅ Successfully synced {len(synced)} commands!", ephemeral=True)
            logger.info(f"Manually synced {len(synced)} commands")
        except Exception as e:
            logger.error(f"Failed to sync commands: {e}")
            await interaction.followup.send(f"❌ Failed to sync commands: {e}", ephemeral=True)


async def setup(bot):
    container = bot.container
    await bot.add_cog(AdminCog(container))