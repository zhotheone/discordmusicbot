import logging

import discord
from discord import app_commands
from discord.ext import commands
from application.handlers.telegram_bridge import TelegramBridge
from core.dependency_injection import DIContainer


class AdminCog(commands.Cog):
    """Administrative commands."""

    def __init__(self, container: DIContainer):
        self.container = container
        # Optional bridge
        self.bridge: TelegramBridge | None = None
        try:
            self.bridge = container.get(TelegramBridge)
        except Exception:
            self.bridge = None

    @app_commands.command(
        name="sync", description="Sync application commands (Admin only)"
    )
    async def sync_commands(self, interaction: discord.Interaction) -> None:
        """Manually sync application commands."""
        # Check if user has administrator permissions
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ You need administrator permissions to use this command!",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            logger.info(
                f"Manual command sync requested by {interaction.user} in guild {interaction.guild.id}"
            )
            synced = await interaction.client.tree.sync()
            await interaction.followup.send(
                f"✅ Successfully synced {len(synced)} commands!", ephemeral=True
            )
            logger.info(f"Manually synced {len(synced)} commands")
        except Exception as e:
            logger.error(f"Failed to sync commands: {e}")
            await interaction.followup.send(
                f"❌ Failed to sync commands: {e}", ephemeral=True
            )

    @app_commands.command(
        name="sync_guild",
        description="Sync slash commands to this guild only (instant)",
    )
    async def sync_guild_commands(self, interaction: discord.Interaction) -> None:
        """Sync commands to the current guild to avoid global propagation delay."""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ You need administrator permissions to use this command!",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            guild = interaction.guild
            # Copy all global commands into this guild, then sync for instant availability
            interaction.client.tree.copy_global_to(guild=guild)
            synced = await interaction.client.tree.sync(guild=guild)
            await interaction.followup.send(
                f"✅ Synced {len(synced)} commands to this guild.", ephemeral=True
            )
        except Exception as e:
            logger.error(f"Failed to sync guild commands: {e}")
            await interaction.followup.send(
                f"❌ Failed to sync guild commands: {e}", ephemeral=True
            )

    @app_commands.command(
        name="all", description="Mention everyone in the linked Telegram chat"
    )
    @app_commands.describe(reason="Why are you summoning everyone?")
    async def mention_all(self, interaction: discord.Interaction, reason: str) -> None:
        if not self.bridge:
            await interaction.response.send_message(
                "Telegram bridge not available.", ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True)
        header = f"{interaction.user.display_name} визиває кавунів:\n{reason}\n\n"
        ok = await self.bridge.send_mention_all(interaction.guild.id, text=header)
        if ok:
            await interaction.followup.send("Sent @all to Telegram.", ephemeral=True)
        else:
            await interaction.followup.send(
                "No Telegram chat linked for this guild.", ephemeral=True
            )

    @app_commands.command(
        name="connect_telegram",
        description="Link this Discord server with a Telegram chat ID",
    )
    @app_commands.describe(chat_id="Telegram chat ID (numeric)")
    async def connect_telegram(
        self, interaction: discord.Interaction, chat_id: int
    ) -> None:
        if not self.bridge:
            await interaction.response.send_message(
                "Telegram bridge not available.", ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True)
        try:
            ok = await self.bridge.link_guild_to_chat(interaction.guild.id, chat_id)
            if ok:
                await interaction.followup.send(
                    f"Linked to Telegram chat {chat_id}.", ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "Failed to link. Ensure the Telegram bot is added to that chat and try again.",
                    ephemeral=True,
                )
        except Exception as e:
            #logger.error(f"connect_telegram failed: {e}")
            await interaction.followup.send(
                f"Unexpected error while linking. {e}", ephemeral=True
            )


async def setup(bot):
    container = bot.container
    await bot.add_cog(AdminCog(container))
