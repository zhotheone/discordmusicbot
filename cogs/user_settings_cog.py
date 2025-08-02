"""User Settings Cog - Commands for managing personal music preferences."""

import discord
from discord.ext import commands
from discord import app_commands
from utils.shared_managers import shared_managers
from services.music_service import RepeatMode
import logging

log = logging.getLogger(__name__)

class UserSettingsCog(commands.Cog, name="User Settings"):
    """Commands for managing your personal music preferences."""
    
    def __init__(self, bot: commands.Bot):
        """Initialize the User Settings cog."""
        self.bot = bot
        self.user_settings = shared_managers.user_settings_manager
    
    @app_commands.command(
        name="my_settings",
        description="View your saved music preferences"
    )
    async def my_settings(self, interaction: discord.Interaction):
        """Display user's current saved settings."""
        user_settings = self.user_settings.get_user_settings(interaction.user.id)
        
        embed = discord.Embed(
            title="🎵 Your Music Preferences",
            description=f"Settings for {interaction.user.display_name}",
            color=discord.Color.blue()
        )
        
        # Volume preference
        volume = user_settings.get("volume", 75)
        embed.add_field(
            name="🔊 Preferred Volume",
            value=f"{volume}%",
            inline=True
        )
        
        # Repeat mode preference
        repeat_mode = user_settings.get("repeat_mode", "off")
        # Convert legacy queue mode to off for display
        if repeat_mode == "queue":
            repeat_mode = "off"
        repeat_emoji = {"off": "🔁", "song": "🔂"}
        embed.add_field(
            name="🔄 Preferred Repeat Mode",
            value=f"{repeat_emoji.get(repeat_mode, '🔁')} {repeat_mode.title()}",
            inline=True
        )
        
        # Filter preferences
        filters = user_settings.get("filters", {})
        enabled_filters = [name for name, data in filters.items() if data.get("enabled", False)]
        
        if enabled_filters:
            filter_emojis = {
                "bassboost": "🔊", "nightcore": "🚀", "slowed": "🐌", 
                "8d": "🌀", "equalizer": "🎛️", "compressor": "📈", "overdrive": "🔥"
            }
            filter_list = []
            for filter_name in enabled_filters:
                emoji = filter_emojis.get(filter_name, "🎵")
                filter_list.append(f"{emoji} {filter_name.title()}")
            
            embed.add_field(
                name="🎛️ Preferred Filters",
                value="\n".join(filter_list) if filter_list else "None",
                inline=False
            )
        else:
            embed.add_field(
                name="🎛️ Preferred Filters",
                value="None saved",
                inline=False
            )
        
        # Last used timestamp
        last_used = user_settings.get("last_used")
        if last_used:
            embed.add_field(
                name="🕒 Last Updated",
                value=f"<t:{int(__import__('datetime').datetime.fromisoformat(last_used).timestamp())}:R>",
                inline=False
            )
        
        embed.set_footer(text="💡 Your preferences are automatically saved when you change settings!")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(
        name="apply_my_preferences",
        description="Apply your saved preferences to this server"
    )
    async def apply_my_preferences(self, interaction: discord.Interaction):
        """Apply user's saved preferences to the current guild."""
        if not interaction.user.voice:
            await interaction.response.send_message(
                "❌ You need to be in a voice channel to apply your preferences.", 
                ephemeral=True
            )
            return
        
        user_settings = self.user_settings.get_user_settings(interaction.user.id)
        
        # Check if user has any saved preferences
        if (user_settings.get("volume") == 75 and 
            user_settings.get("repeat_mode") == "off" and 
            not user_settings.get("filters")):
            await interaction.response.send_message(
                "📭 You don't have any saved preferences yet! Start using the bot to build your preference profile.",
                ephemeral=True
            )
            return
        
        try:
            # Get services
            music_service = shared_managers.music_service
            filter_manager = shared_managers.get_filter_manager(interaction.guild.id)
            
            # Apply preferences
            self.user_settings.apply_user_preferences(
                interaction.user.id,
                interaction.guild.id,
                music_service,
                filter_manager
            )
            
            # Save the filter state
            shared_managers.save_filter_state(interaction.guild.id)
            
            embed = discord.Embed(
                title="✅ Preferences Applied!",
                description="Your saved preferences have been applied to this server",
                color=discord.Color.green()
            )
            
            # Show what was applied
            volume = user_settings.get("volume", 75)
            repeat_mode = user_settings.get("repeat_mode", "off")
            filters = user_settings.get("filters", {})
            enabled_filters = [name for name, data in filters.items() if data.get("enabled", False)]
            
            embed.add_field(name="🔊 Volume", value=f"{volume}%", inline=True)
            embed.add_field(name="🔄 Repeat", value=repeat_mode.title(), inline=True)
            
            if enabled_filters:
                embed.add_field(
                    name="🎛️ Filters", 
                    value=", ".join([f.title() for f in enabled_filters]), 
                    inline=False
                )
            
            embed.set_footer(text="💡 Use /skip to apply filters to the current song")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            log.error(f"Failed to apply user preferences: {e}")
            await interaction.response.send_message(
                "❌ Failed to apply your preferences. Please try again later.",
                ephemeral=True
            )
    
    @app_commands.command(
        name="clear_my_preferences",
        description="Clear all your saved preferences"
    )
    async def clear_my_preferences(self, interaction: discord.Interaction):
        """Clear user's saved preferences."""
        # Create confirmation view
        view = ClearPreferencesView(self.user_settings, interaction.user.id)
        
        embed = discord.Embed(
            title="⚠️ Clear All Preferences?",
            description="This will permanently delete all your saved music preferences including:\n"
                       "• Preferred volume level\n"
                       "• Preferred repeat mode\n" 
                       "• Preferred audio filters\n\n"
                       "**This action cannot be undone!**",
            color=discord.Color.orange()
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @app_commands.command(
        name="export_preferences",
        description="Export your preferences as a shareable code"
    )
    async def export_preferences(self, interaction: discord.Interaction):
        """Export user preferences as a shareable code."""
        import json
        import base64
        
        user_settings = self.user_settings.get_user_settings(interaction.user.id)
        
        # Remove timestamp and other metadata
        export_data = {
            "volume": user_settings.get("volume", 75),
            "repeat_mode": user_settings.get("repeat_mode", "off"),
            "filters": user_settings.get("filters", {})
        }
        
        # Encode as base64
        json_str = json.dumps(export_data, separators=(',', ':'))
        encoded = base64.b64encode(json_str.encode()).decode()
        
        embed = discord.Embed(
            title="📤 Export Your Preferences",
            description="Here's your preference code. You can share this with friends or save it as a backup!",
            color=discord.Color.blue()
        )
        
        # Split long codes into multiple fields if needed
        if len(encoded) > 1024:
            # Split into chunks
            chunk_size = 1024
            chunks = [encoded[i:i+chunk_size] for i in range(0, len(encoded), chunk_size)]
            for i, chunk in enumerate(chunks, 1):
                embed.add_field(
                    name=f"Code Part {i}",
                    value=f"```{chunk}```",
                    inline=False
                )
        else:
            embed.add_field(
                name="Your Preference Code",
                value=f"```{encoded}```",
                inline=False
            )
        
        embed.set_footer(text="💡 Use /import_preferences to load preferences from a code")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(
        name="current_settings",
        description="View the current server settings (what's actually being used)"
    )
    async def current_settings(self, interaction: discord.Interaction):
        """Display the current active settings in this server."""
        try:
            # Get current server settings
            playback_info = shared_managers.playback_service.get_playback_info(interaction.guild.id)
            filter_manager = shared_managers.get_filter_manager(interaction.guild.id)
            
            embed = discord.Embed(
                title="⚙️ Current Server Settings",
                description=f"Active settings in **{interaction.guild.name}**",
                color=discord.Color.green()
            )
            
            # Current volume
            current_volume = playback_info.get("volume", 75)
            embed.add_field(
                name="🔊 Current Volume",
                value=f"{current_volume}%",
                inline=True
            )
            
            # Current repeat mode
            current_repeat = playback_info.get("repeat_mode")
            if hasattr(current_repeat, 'value'):
                repeat_str = current_repeat.value
            else:
                repeat_str = str(current_repeat) if current_repeat else "off"
            
            repeat_emoji = {"off": "🔁", "song": "🔂"}
            embed.add_field(
                name="🔄 Current Repeat Mode",
                value=f"{repeat_emoji.get(repeat_str, '🔁')} {repeat_str.title()}",
                inline=True
            )
            
            # Current filters
            enabled_filters = filter_manager.get_enabled_filters()
            if enabled_filters:
                filter_emojis = {
                    "bassboost": "🔊", "nightcore": "🚀", "slowed": "🐌", 
                    "8d": "🌀", "equalizer": "🎛️", "compressor": "📈", "overdrive": "🔥"
                }
                filter_list = []
                for filter_name in enabled_filters:
                    emoji = filter_emojis.get(filter_name, "🎵")
                    filter_list.append(f"{emoji} {filter_name.title()}")
                
                embed.add_field(
                    name="🎛️ Active Filters",
                    value="\n".join(filter_list),
                    inline=False
                )
            else:
                embed.add_field(
                    name="🎛️ Active Filters",
                    value="None active",
                    inline=False
                )
            
            # Your saved preferences vs current
            user_settings = self.user_settings.get_user_settings(interaction.user.id)
            your_volume = user_settings.get("volume", 75)
            your_repeat = user_settings.get("repeat_mode", "off")
            
            if your_volume != current_volume or your_repeat != repeat_str:
                embed.add_field(
                    name="💡 Notice",
                    value=f"These settings differ from your saved preferences.\n"
                          f"Use `/apply_my_preferences` to apply your saved settings.",
                    inline=False
                )
            else:
                embed.add_field(
                    name="✅ Status",
                    value="Current settings match your saved preferences!",
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            log.error(f"Failed to get current settings: {e}")
            await interaction.response.send_message(
                "❌ Failed to retrieve current settings. Please try again later.",
                ephemeral=True
            )


class ClearPreferencesView(discord.ui.View):
    """View for confirming preference clearing."""
    
    def __init__(self, user_settings_manager, user_id: int):
        super().__init__(timeout=60)
        self.user_settings_manager = user_settings_manager
        self.user_id = user_id
    
    @discord.ui.button(label="Yes, Clear All", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def confirm_clear(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Confirm clearing preferences."""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ You can't clear someone else's preferences!", ephemeral=True)
            return
        
        self.user_settings_manager.clear_user_settings(self.user_id)
        
        embed = discord.Embed(
            title="✅ Preferences Cleared",
            description="All your saved preferences have been deleted.",
            color=discord.Color.green()
        )
        
        # Disable buttons
        for item in self.children:
            item.disabled = True
        
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_clear(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel clearing preferences."""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This isn't your confirmation dialog!", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="🛡️ Cancelled",
            description="Your preferences have been kept safe.",
            color=discord.Color.blue()
        )
        
        # Disable buttons
        for item in self.children:
            item.disabled = True
        
        await interaction.response.edit_message(embed=embed, view=self)


async def setup(bot: commands.Bot):
    """Setup function for the cog."""
    await bot.add_cog(UserSettingsCog(bot)) 