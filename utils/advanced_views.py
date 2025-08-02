"""Advanced Discord UI Views with filter management."""

import discord

class FilterManagementView(discord.ui.View):
    """View for managing audio filters with buttons."""
    
    def __init__(self, cog, guild_id: int, *, timeout=300):
        """Initialize the filter management view."""
        super().__init__(timeout=timeout)
        self.cog = cog
        self.guild_id = guild_id
    
    @discord.ui.select(
        placeholder="Select filters to enable/disable...",
        min_values=0,
        max_values=7,
        options=[
            discord.SelectOption(
                label="Bass Boost",
                value="bassboost",
                description="Enhance low-frequency sounds",
                emoji="🔊"
            ),
            discord.SelectOption(
                label="Nightcore",
                value="nightcore", 
                description="Speed up and pitch up audio",
                emoji="🚀"
            ),
            discord.SelectOption(
                label="Slowed + Reverb",
                value="slowed",
                description="Slow down with reverb effect",
                emoji="🐌"
            ),
            discord.SelectOption(
                label="8D Audio",
                value="8d",
                description="Create 8D surround sound effect",
                emoji="🌀"
            ),
            discord.SelectOption(
                label="Equalizer",
                value="equalizer",
                description="3-band frequency equalizer",
                emoji="🎛️"
            ),
            discord.SelectOption(
                label="Compressor",
                value="compressor",
                description="Dynamic range compression",
                emoji="📈"
            ),
            discord.SelectOption(
                label="Overdrive",
                value="overdrive",
                description="Warm tube-like overdrive effect",
                emoji="🔥"
            )
        ]
    )
    async def filter_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        """Handle filter selection."""
        if not hasattr(self.cog, 'get_filter_manager'):
            await interaction.response.send_message(
                "❌ Advanced filter system not available.", ephemeral=True
            )
            return
        
        filter_manager = self.cog.get_filter_manager(self.guild_id)
        selected_filters = select.values
        all_filters = filter_manager.list_available_filters()
        
        # Update filter states
        changes = []
        for filter_name in all_filters:
            was_enabled = filter_manager.get_filter(filter_name).enabled
            should_be_enabled = filter_name in selected_filters
            
            if should_be_enabled and not was_enabled:
                filter_manager.enable_filter(filter_name)
                changes.append(f"✅ Enabled {filter_name.capitalize()}")
            elif not should_be_enabled and was_enabled:
                filter_manager.disable_filter(filter_name)
                changes.append(f"❌ Disabled {filter_name.capitalize()}")
        
        # Save changes
        if hasattr(self.cog, 'save_filter_state'):
            self.cog.save_filter_state(self.guild_id)
        
        # Try to apply filters to current song
        applied_live = False
        playback_cog = None
        if hasattr(self.cog, 'bot'):
            playback_cog = self.cog.bot.get_cog("Playback Controls")
        
        if playback_cog and hasattr(playback_cog, 'apply_filters_to_current_song'):
            applied_live = await playback_cog.apply_filters_to_current_song(
                self.guild_id, interaction.channel
            )
        
        # Update select options to reflect current state
        enabled_filters = filter_manager.get_enabled_filters()
        for option in select.options:
            option.default = option.value in enabled_filters
        
        if changes:
            embed = discord.Embed(
                title="🎛️ Filter Settings Updated",
                description="\n".join(changes),
                color=discord.Color.green()
            )
            
            if applied_live:
                embed.add_field(
                    name="🔴 Applied Live",
                    value="Changes have been applied to the current song!",
                    inline=False
                )
            else:
                embed.add_field(
                    name="💡 Tip",
                    value="Use `/skip` to apply changes to the current song",
                    inline=False
                )
        else:
            embed = discord.Embed(
                title="🎛️ No Changes Made",
                description="Filter settings remain the same",
                color=discord.Color.orange()
            )
        
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Apply Preset", style=discord.ButtonStyle.secondary, emoji="🎵")
    async def apply_preset(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show preset selection modal."""
        modal = PresetSelectionModal(self.cog, self.guild_id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Clear All", style=discord.ButtonStyle.danger, emoji="🔄")
    async def clear_filters(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Clear all active filters."""
        if not hasattr(self.cog, 'get_filter_manager'):
            await interaction.response.send_message(
                "❌ Advanced filter system not available.", ephemeral=True
            )
            return
        
        filter_manager = self.cog.get_filter_manager(self.guild_id)
        
        # Disable all filters
        for filter_name in filter_manager.list_available_filters():
            filter_manager.disable_filter(filter_name)
        
        # Save changes
        if hasattr(self.cog, 'save_filter_state'):
            self.cog.save_filter_state(self.guild_id)
        
        # Update select menu
        for option in self.children[0].options:
            option.default = False
        
        embed = discord.Embed(
            title="🔄 All Filters Cleared",
            description="All audio filters have been disabled",
            color=discord.Color.orange()
        )
        
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Status", style=discord.ButtonStyle.primary, emoji="📊")
    async def show_status(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show current filter status."""
        if not hasattr(self.cog, 'get_filter_manager'):
            await interaction.response.send_message(
                "❌ Advanced filter system not available.", ephemeral=True
            )
            return
        
        filter_manager = self.cog.get_filter_manager(self.guild_id)
        enabled_filters = filter_manager.get_enabled_filters()
        
        embed = discord.Embed(
            title="📊 Current Filter Status",
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
                    # Show first 2 parameters to avoid clutter
                    params = list(info['parameters'].items())[:2]
                    for param_name, param_info in params:
                        filter_details.append(f"  └ {param_name}: {param_info['value']}")
                    if len(info['parameters']) > 2:
                        filter_details.append(f"  └ ... and {len(info['parameters']) - 2} more")
            
            embed.description = "\n".join(filter_details)
        
        # Show generated FFmpeg filter in a short form
        ffmpeg_filter = filter_manager.get_combined_ffmpeg_filter()
        if ffmpeg_filter:
            # Truncate if too long
            if len(ffmpeg_filter) > 200:
                ffmpeg_filter = ffmpeg_filter[:197] + "..."
            embed.add_field(
                name="Generated Filter Chain",
                value=f"```{ffmpeg_filter}```",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, emoji="⬅️")
    async def back_to_controls(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Return to the main music controls interface."""
        # Create the main music controls view
        controls_view = EnhancedMusicControlsView(self.cog)
        
        # Create an embed for the main controls
        embed = discord.Embed(
            title="🎵 Music Controls",
            description="Use the buttons below to control music playback",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Available Controls",
            value="⏸️ **Pause/Resume** - Pause or resume playback\n"
                  "⏭️ **Skip** - Skip to the next song\n"
                  "⏹️ **Stop** - Stop playback and clear queue\n"
                  "🔁 **Repeat** - Toggle repeat mode\n"
                  "🎛️ **Filters** - Manage audio filters",
            inline=False
        )
        
        await interaction.response.edit_message(embed=embed, view=controls_view)


class PresetSelectionModal(discord.ui.Modal, title="Select Filter Preset"):
    """Modal for selecting and applying filter presets."""
    
    def __init__(self, cog, guild_id: int):
        super().__init__()
        self.cog = cog
        self.guild_id = guild_id
    
    preset_name = discord.ui.TextInput(
        label="Preset Name",
        placeholder="Enter preset name (gaming, music, vocal, or custom)",
        max_length=50
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle preset selection submission."""
        if not hasattr(self.cog, 'get_filter_manager'):
            await interaction.response.send_message(
                "❌ Advanced filter system not available.", ephemeral=True
            )
            return
        
        filter_manager = self.cog.get_filter_manager(self.guild_id)
        preset_name = self.preset_name.value.lower().strip()
        
        if preset_name not in filter_manager.list_available_presets():
            available_presets = ", ".join(filter_manager.list_available_presets())
            await interaction.response.send_message(
                f"❌ Preset '{preset_name}' not found.\n"
                f"Available presets: {available_presets}",
                ephemeral=True
            )
            return
        
        if filter_manager.apply_preset(preset_name):
            # Save changes
            if hasattr(self.cog, 'save_filter_state'):
                self.cog.save_filter_state(self.guild_id)
            
            enabled_filters = filter_manager.get_enabled_filters()
            preset = filter_manager.presets[preset_name]
            
            embed = discord.Embed(
                title="🎵 Preset Applied Successfully",
                description=f"**{preset_name.capitalize()}** preset is now active",
                color=discord.Color.green()
            )
            
            if preset.description:
                embed.add_field(name="Description", value=preset.description, inline=False)
            
            if enabled_filters:
                embed.add_field(
                    name="Active Filters",
                    value=", ".join(f.capitalize() for f in enabled_filters),
                    inline=False
                )
            
            embed.add_field(
                name="💡 Next Steps",
                value="Use `/skip` to apply preset to current song\n"
                      "Use filter management to fine-tune settings",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message(
                f"❌ Failed to apply preset '{preset_name}'",
                ephemeral=True
            )


class EnhancedMusicControlsView(discord.ui.View):
    """Enhanced music controls with filter management."""
    
    def __init__(self, cog, *, timeout=None):
        """Initialize the enhanced music controls view."""
        super().__init__(timeout=timeout)
        self.cog = cog
    
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
        config = self.cog.config_manager.get_config(interaction.guild.id)
        current_mode = config.get("repeat_mode", "off")
        
        # Cycle through repeat modes: off -> song -> queue -> off
        if current_mode == "off":
            new_mode = "song"
            button.label = "Repeat: Song"
            button.emoji = "🔂"
            button.style = discord.ButtonStyle.success
        elif current_mode == "song":
            new_mode = "queue"
            button.label = "Repeat: Queue"
            button.emoji = "🔁"
            button.style = discord.ButtonStyle.primary
        else:  # queue
            new_mode = "off"
            button.label = "Repeat: Off"
            button.emoji = "🔁"
            button.style = discord.ButtonStyle.secondary
        
        config["repeat_mode"] = new_mode
        self.cog.config_manager.save_config(interaction.guild.id, config)
        
        await interaction.response.edit_message(view=self)

    @discord.ui.button(
        label="Filters", 
        style=discord.ButtonStyle.secondary, 
        emoji="🎛️"
    )
    async def manage_filters(
        self, 
        interaction: discord.Interaction, 
        button: discord.ui.Button
    ):
        """Open filter management interface."""
        embed = discord.Embed(
            title="🎛️ Audio Filter Management",
            description="Select filters to enable/disable or apply presets",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="How to Use",
            value="• Use the dropdown to select multiple filters\n"
                  "• Apply presets for quick setups\n"
                  "• Use `/filter_configure` for detailed parameter tuning",
            inline=False
        )
        
        view = FilterManagementView(self.cog, interaction.guild.id)
        
        # Set default selections based on current state
        if hasattr(self.cog, 'get_filter_manager'):
            filter_manager = self.cog.get_filter_manager(interaction.guild.id)
            enabled_filters = filter_manager.get_enabled_filters()
            
            for option in view.children[0].options:
                option.default = option.value in enabled_filters
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)