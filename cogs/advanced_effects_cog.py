"""Advanced Effects Cog - Runtime configurable audio filters."""

import discord
from discord.ext import commands
import logging

from utils.shared_managers import shared_managers
from utils.advanced_filters import AdvancedFilterManager

# Import error handling system
from error_handling import (
    handle_errors,
    raise_if_not_in_voice,
    raise_if_bot_not_connected,
    UserInputException,
    MusicException
)

log = logging.getLogger(__name__)


class AdvancedEffectsCog(commands.Cog, name="Advanced Audio Effects"):
    """Commands for advanced audio effects with runtime configuration."""
    
    def __init__(self, bot: commands.Bot):
        """Initialize the Advanced Effects cog."""
        self.bot = bot
        # Use shared services instead of handling business logic directly
        self.filter_service = shared_managers.filter_service
        self.playback_service = shared_managers.playback_service
    
    def get_filter_manager(self, guild_id: int) -> AdvancedFilterManager:
        """Get or create filter manager for a guild."""
        return self.filter_service.get_advanced_filter_manager(guild_id)
    
    def save_filter_state(self, guild_id: int):
        """Save current filter state to config."""
        self.filter_service.save_advanced_filter_state(guild_id)

    @discord.app_commands.command(
        name="filter_list",
        description="List all available audio filters"
    )
    async def filter_list(self, interaction: discord.Interaction):
        """List all available audio filters."""
        filter_manager = self.get_filter_manager(interaction.guild.id)
        filters = filter_manager.list_available_filters()
        enabled_filters = filter_manager.get_enabled_filters()
        
        embed = discord.Embed(
            title="🎛️ Available Audio Filters",
            color=discord.Color.blue()
        )
        
        filter_info = []
        for filter_name in filters:
            status = "✅ **ENABLED**" if filter_name in enabled_filters else "❌ Disabled"
            info = filter_manager.get_filter_info(filter_name)
            filter_info.append(f"**{filter_name.capitalize()}** - {status}")
            if info and info['description']:
                filter_info.append(f"  └ {info['description']}")
        
        embed.description = "\n".join(filter_info)
        embed.add_field(
            name="Usage",
            value="Use `/filter_enable <name>` to enable a filter\nUse `/filter_configure` to adjust parameters",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)

    @discord.app_commands.command(
        name="filter_enable",
        description="Enable an audio filter"
    )
    @discord.app_commands.describe(filter_name="Name of the filter to enable")
    async def filter_enable(self, interaction: discord.Interaction, filter_name: str):
        """Enable a specific audio filter."""
        filter_manager = self.get_filter_manager(interaction.guild.id)
        
        if filter_name not in filter_manager.list_available_filters():
            await interaction.response.send_message(
                f"❌ Filter '{filter_name}' not found. Use `/filter_list` to see available filters.",
                ephemeral=True
            )
            return
        
        if filter_manager.enable_filter(filter_name):
            self.save_filter_state(interaction.guild.id)
            
            # Try to apply to current song
            playback_cog = self.bot.get_cog("Playback Controls")
            applied_live = False
            if playback_cog and hasattr(playback_cog, 'apply_filters_to_current_song'):
                applied_live = await playback_cog.apply_filters_to_current_song(
                    interaction.guild.id, interaction.channel
                )
            
            info = filter_manager.get_filter_info(filter_name)
            embed = discord.Embed(
                title="✅ Filter Enabled",
                description=f"**{filter_name.capitalize()}** filter is now active",
                color=discord.Color.green()
            )
            
            if applied_live:
                embed.add_field(
                    name="🔴 Applied Live",
                    value="Filter has been applied to the current song!",
                    inline=False
                )
            
            if info and info['description']:
                embed.add_field(name="Description", value=info['description'], inline=False)
            
            # Show current parameters
            if info and info['parameters']:
                param_text = []
                for param_name, param_info in info['parameters'].items():
                    param_text.append(
                        f"**{param_name}**: {param_info['value']} "
                        f"(range: {param_info['min']}-{param_info['max']})"
                    )
                embed.add_field(
                    name="Current Parameters",
                    value="\n".join(param_text),
                    inline=False
                )
            
            next_steps = f"Use `/filter_configure {filter_name}` to adjust parameters"
            if not applied_live:
                next_steps += f"\nUse `/skip` to apply to current song"
            
            embed.add_field(
                name="Next Steps",
                value=next_steps,
                inline=False
            )
            
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message(
                f"❌ Failed to enable filter '{filter_name}'",
                ephemeral=True
            )

    @discord.app_commands.command(
        name="filter_disable",
        description="Disable an audio filter"
    )
    @discord.app_commands.describe(filter_name="Name of the filter to disable")
    async def filter_disable(self, interaction: discord.Interaction, filter_name: str):
        """Disable a specific audio filter."""
        filter_manager = self.get_filter_manager(interaction.guild.id)
        
        if filter_name not in filter_manager.list_available_filters():
            await interaction.response.send_message(
                f"❌ Filter '{filter_name}' not found.",
                ephemeral=True
            )
            return
        
        if filter_manager.disable_filter(filter_name):
            self.save_filter_state(interaction.guild.id)
            
            embed = discord.Embed(
                title="❌ Filter Disabled",
                description=f"**{filter_name.capitalize()}** filter is now inactive",
                color=discord.Color.orange()
            )
            
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message(
                f"❌ Failed to disable filter '{filter_name}'",
                ephemeral=True
            )

    @discord.app_commands.command(
        name="filter_configure",
        description="Configure filter parameters"
    )
    @discord.app_commands.describe(
        filter_name="Name of the filter to configure",
        parameter="Parameter name to modify",
        value="New parameter value"
    )
    async def filter_configure(
        self,
        interaction: discord.Interaction,
        filter_name: str,
        parameter: str,
        value: float
    ):
        """Configure parameters for a specific filter."""
        filter_manager = self.get_filter_manager(interaction.guild.id)
        
        if filter_name not in filter_manager.list_available_filters():
            await interaction.response.send_message(
                f"❌ Filter '{filter_name}' not found.",
                ephemeral=True
            )
            return
        
        info = filter_manager.get_filter_info(filter_name)
        if not info or parameter not in info['parameters']:
            param_list = list(info['parameters'].keys()) if info else []
            await interaction.response.send_message(
                f"❌ Parameter '{parameter}' not found for filter '{filter_name}'.\n"
                f"Available parameters: {', '.join(param_list)}",
                ephemeral=True
            )
            return
        
        param_info = info['parameters'][parameter]
        if not (param_info['min'] <= value <= param_info['max']):
            await interaction.response.send_message(
                f"❌ Value {value} is out of range for parameter '{parameter}'.\n"
                f"Valid range: {param_info['min']} - {param_info['max']}",
                ephemeral=True
            )
            return
        
        if filter_manager.set_filter_parameter(filter_name, parameter, value):
            self.save_filter_state(interaction.guild.id)
            
            # Try to apply to current song
            playback_cog = self.bot.get_cog("Playback Controls")
            applied_live = False
            if playback_cog and hasattr(playback_cog, 'apply_filters_to_current_song'):
                applied_live = await playback_cog.apply_filters_to_current_song(
                    interaction.guild.id, interaction.channel
                )
            
            embed = discord.Embed(
                title="🎛️ Parameter Updated",
                description=f"**{filter_name.capitalize()}** → **{parameter}** = {value}",
                color=discord.Color.green()
            )
            
            if applied_live:
                embed.add_field(
                    name="🔴 Applied Live",
                    value="Changes have been applied to the current song!",
                    inline=False
                )
            
            embed.add_field(
                name="Parameter Info",
                value=f"{param_info['description']}\nRange: {param_info['min']} - {param_info['max']}",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message(
                f"❌ Failed to set parameter '{parameter}' for filter '{filter_name}'",
                ephemeral=True
            )

    @discord.app_commands.command(
        name="filter_info",
        description="Get detailed information about a filter"
    )
    @discord.app_commands.describe(filter_name="Name of the filter to inspect")
    async def filter_info(self, interaction: discord.Interaction, filter_name: str):
        """Get detailed information about a specific filter."""
        filter_manager = self.get_filter_manager(interaction.guild.id)
        
        info = filter_manager.get_filter_info(filter_name)
        if not info:
            await interaction.response.send_message(
                f"❌ Filter '{filter_name}' not found.",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title=f"🎛️ Filter: {filter_name.capitalize()}",
            description=info['description'],
            color=discord.Color.green() if info['enabled'] else discord.Color.grey()
        )
        
        embed.add_field(
            name="Status",
            value="✅ Enabled" if info['enabled'] else "❌ Disabled",
            inline=True
        )
        
        if info['parameters']:
            param_text = []
            for param_name, param_info in info['parameters'].items():
                param_text.append(
                    f"**{param_name}**: {param_info['value']}\n"
                    f"  └ {param_info['description']}\n"
                    f"  └ Range: {param_info['min']} - {param_info['max']}"
                )
            
            embed.add_field(
                name="Parameters",
                value="\n\n".join(param_text),
                inline=False
            )
        
        await interaction.response.send_message(embed=embed)

    @discord.app_commands.command(
        name="preset_list",
        description="List available filter presets"
    )
    async def preset_list(self, interaction: discord.Interaction):
        """List all available filter presets."""
        filter_manager = self.get_filter_manager(interaction.guild.id)
        presets = filter_manager.list_available_presets()
        
        embed = discord.Embed(
            title="🎵 Filter Presets",
            color=discord.Color.purple()
        )
        
        if not presets:
            embed.description = "No presets available."
        else:
            preset_info = []
            for preset_name in presets:
                preset = filter_manager.presets[preset_name]
                preset_info.append(f"**{preset_name.capitalize()}**")
                if preset.description:
                    preset_info.append(f"  └ {preset.description}")
            
            embed.description = "\n".join(preset_info)
        
        embed.add_field(
            name="Usage",
            value="Use `/preset_apply <name>` to apply a preset",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)

    @discord.app_commands.command(
        name="preset_apply",
        description="Apply a filter preset"
    )
    @discord.app_commands.describe(preset_name="Name of the preset to apply")
    async def preset_apply(self, interaction: discord.Interaction, preset_name: str):
        """Apply a filter preset."""
        filter_manager = self.get_filter_manager(interaction.guild.id)
        
        if preset_name not in filter_manager.list_available_presets():
            await interaction.response.send_message(
                f"❌ Preset '{preset_name}' not found. Use `/preset_list` to see available presets.",
                ephemeral=True
            )
            return
        
        if filter_manager.apply_preset(preset_name):
            self.save_filter_state(interaction.guild.id)
            
            # Try to apply to current song
            playback_cog = self.bot.get_cog("Playback Controls")
            applied_live = False
            if playback_cog and hasattr(playback_cog, 'apply_filters_to_current_song'):
                applied_live = await playback_cog.apply_filters_to_current_song(
                    interaction.guild.id, interaction.channel
                )
            
            enabled_filters = filter_manager.get_enabled_filters()
            preset = filter_manager.presets[preset_name]
            
            embed = discord.Embed(
                title="🎵 Preset Applied",
                description=f"**{preset_name.capitalize()}** preset is now active",
                color=discord.Color.purple()
            )
            
            if applied_live:
                embed.add_field(
                    name="🔴 Applied Live",
                    value="Preset has been applied to the current song!",
                    inline=False
                )
            
            if preset.description:
                embed.add_field(name="Description", value=preset.description, inline=False)
            
            if enabled_filters:
                embed.add_field(
                    name="Active Filters",
                    value=", ".join(f.capitalize() for f in enabled_filters),
                    inline=False
                )
            
            next_steps = "Use `/filter_configure` to fine-tune individual filters"
            if not applied_live:
                next_steps = "Use `/skip` to apply preset to current song\n" + next_steps
            
            embed.add_field(
                name="Next Steps",
                value=next_steps,
                inline=False
            )
            
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message(
                f"❌ Failed to apply preset '{preset_name}'",
                ephemeral=True
            )

    @discord.app_commands.command(
        name="filter_clear",
        description="Clear all active filters"
    )
    async def filter_clear(self, interaction: discord.Interaction):
        """Clear all active filters."""
        filter_manager = self.get_filter_manager(interaction.guild.id)
        
        # Disable all filters
        for filter_name in filter_manager.list_available_filters():
            filter_manager.disable_filter(filter_name)
        
        self.save_filter_state(interaction.guild.id)
        
        embed = discord.Embed(
            title="🔄 Filters Cleared",
            description="All audio filters have been disabled",
            color=discord.Color.orange()
        )
        
        await interaction.response.send_message(embed=embed)

    @discord.app_commands.command(
        name="filter_status",
        description="Show current filter status"
    )
    async def filter_status(self, interaction: discord.Interaction):
        """Show current filter status and settings."""
        filter_manager = self.get_filter_manager(interaction.guild.id)
        enabled_filters = filter_manager.get_enabled_filters()
        
        embed = discord.Embed(
            title="🎛️ Current Filter Status",
            color=discord.Color.blue()
        )
        
        if not enabled_filters:
            embed.description = "No filters are currently active."
        else:
            filter_details = []
            for filter_name in enabled_filters:
                info = filter_manager.get_filter_info(filter_name)
                filter_details.append(f"**{filter_name.capitalize()}** ✅")
                
                if info and info['parameters']:
                    params = []
                    for param_name, param_info in info['parameters'].items():
                        params.append(f"  └ {param_name}: {param_info['value']}")
                    filter_details.extend(params)
            
            embed.description = "\n".join(filter_details)
        
        # Show generated FFmpeg filter
        ffmpeg_filter = filter_manager.get_combined_ffmpeg_filter()
        if ffmpeg_filter:
            embed.add_field(
                name="Generated FFmpeg Filter",
                value=f"```{ffmpeg_filter}```",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed)

    @discord.app_commands.command(
        name="apply_filters_live",
        description="Apply current filter settings to the playing song"
    )
    async def apply_filters_live(self, interaction: discord.Interaction):
        """Apply current filter settings to the currently playing song."""
        # Check if there's a song playing
        vc = interaction.guild.voice_client
        if not vc or not vc.is_connected():
            await interaction.response.send_message(
                "❌ Bot is not connected to a voice channel.", ephemeral=True
            )
            return
        
        if not (vc.is_playing() or vc.is_paused()):
            await interaction.response.send_message(
                "❌ No song is currently playing.", ephemeral=True
            )
            return
        
        # Try to apply filters
        playback_cog = self.bot.get_cog("Playback Controls")
        if not playback_cog or not hasattr(playback_cog, 'apply_filters_to_current_song'):
            await interaction.response.send_message(
                "❌ Live filter application is not available.", ephemeral=True
            )
            return
        
        await interaction.response.defer()
        
        applied = await playback_cog.apply_filters_to_current_song(
            interaction.guild.id, interaction.channel
        )
        
        if applied:
            filter_manager = self.get_filter_manager(interaction.guild.id)
            enabled_filters = filter_manager.get_enabled_filters()
            
            embed = discord.Embed(
                title="🔴 Filters Applied Live!",
                description="Filter settings have been applied to the current song",
                color=discord.Color.green()
            )
            
            if enabled_filters:
                embed.add_field(
                    name="Active Filters",
                    value=", ".join(f.capitalize() for f in enabled_filters),
                    inline=False
                )
            else:
                embed.add_field(
                    name="Status",
                    value="All filters cleared from current song",
                    inline=False
                )
            
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send(
                "❌ Failed to apply filters to the current song. "
                "The song may have ended or there was an audio processing error.",
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    """Set up the Advanced Effects cog."""
    await bot.add_cog(AdvancedEffectsCog(bot))