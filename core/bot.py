import logging

import discord
from discord.ext import commands

from application.handlers.error_handler import ErrorHandler
from config.settings import Settings
from core.dependency_injection import DIContainer
from core.events import EventBus
from domain.services.filter_service import FilterService
from domain.services.music_service import MusicService
from domain.services.playlist_loader import PlaylistLoaderService
from domain.services.user_service import UserService
from presentation.cogs.admin_cog import AdminCog
from presentation.cogs.filters_cog import FiltersCog
from presentation.cogs.music_cog import MusicCog
from presentation.cogs.playlist_cog import PlaylistCog

logger = logging.getLogger(__name__)


class MusicBot(commands.Bot):
    """Main Discord music bot class."""

    def __init__(
        self,
        command_prefix: str,
        intents: discord.Intents,
        container: DIContainer,
        settings: Settings,
    ):
        super().__init__(
            command_prefix=command_prefix, intents=intents, help_command=None
        )

        self.container = container
        self.settings = settings
        self.event_bus = EventBus()

        # Register core services
        self.container.register(EventBus, self.event_bus)
        self.container.register("Bot", self)
        self.container.register(Settings, settings)

    async def setup_hook(self) -> None:
        """Initialize the bot components."""
        try:
            logger.info("Setting up bot components...")

            # Initialize services
            await self._setup_services()

            # Setup error handling
            error_handler = ErrorHandler(self.event_bus)
            self.container.register(ErrorHandler, error_handler)

            # Load cogs
            await self._load_cogs()

            logger.info("Bot setup completed successfully")

        except Exception as e:
            logger.error(f"Failed to setup bot: {e}")
            raise

    async def _setup_services(self) -> None:
        """Initialize domain services."""
        # Music service
        music_service = MusicService(
            container=self.container, event_bus=self.event_bus, settings=self.settings
        )
        self.container.register(MusicService, music_service)

        # User service
        user_service = UserService(container=self.container, event_bus=self.event_bus)
        self.container.register(UserService, user_service)

        # Filter service
        filter_service = FilterService(
            container=self.container, event_bus=self.event_bus
        )
        self.container.register(FilterService, filter_service)

        # Playlist loader service
        playlist_loader_service = PlaylistLoaderService(
            container=self.container, event_bus=self.event_bus
        )
        self.container.register(PlaylistLoaderService, playlist_loader_service)

    async def _load_cogs(self) -> None:
        """Load all bot cogs."""
        cogs = [
            MusicCog(self.container),
            FiltersCog(self.container),
            PlaylistCog(self.container),
            AdminCog(self.container),
        ]

        for cog in cogs:
            await self.add_cog(cog)
            logger.info(f"Loaded cog: {cog.__class__.__name__}")

    async def on_ready(self) -> None:
        """Called when the bot is ready."""
        logger.info(f"Bot is ready! Logged in as {self.user}")
        logger.info(f"Connected to {len(self.guilds)} guilds")

        # Sync commands if this is the first time ready or if needed
        if not hasattr(self, "_commands_synced"):
            try:
                logger.info("Syncing application commands...")
                synced = await self.tree.sync()
                logger.info(f"Synced {len(synced)} global commands")
                # Also sync to each guild for instant availability
                for guild in self.guilds:
                    try:
                        self.tree.copy_global_to(guild=guild)
                        g_synced = await self.tree.sync(guild=guild)
                        logger.info(
                            f"Synced {len(g_synced)} commands to guild {guild.name} ({guild.id})"
                        )
                    except Exception as ge:
                        logger.error(
                            f"Failed to sync commands to guild {guild.name} ({guild.id}): {ge}"
                        )
                self._commands_synced = True
            except Exception as e:
                logger.error(f"Failed to sync commands: {e}")

        # Set bot status
        activity = discord.Activity(
            type=discord.ActivityType.listening,
            name=f"{self.settings.command_prefix}play",
        )
        await self.change_presence(activity=activity)

    async def on_guild_join(self, guild: discord.Guild) -> None:
        """Called when the bot joins a guild."""
        logger.info(f"Joined guild: {guild.name} (ID: {guild.id})")
        await self.event_bus.publish("guild_joined", guild=guild)
        # Ensure commands are immediately available in the new guild
        try:
            self.tree.copy_global_to(guild=guild)
            g_synced = await self.tree.sync(guild=guild)
            logger.info(
                f"Synced {len(g_synced)} commands to new guild {guild.name} ({guild.id})"
            )
        except Exception as e:
            logger.error(
                f"Failed to sync commands to new guild {guild.name} ({guild.id}): {e}"
            )

    async def on_guild_remove(self, guild: discord.Guild) -> None:
        """Called when the bot leaves a guild."""
        logger.info(f"Left guild: {guild.name} (ID: {guild.id})")
        await self.event_bus.publish("guild_left", guild=guild)

    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        """Handle voice state updates."""
        if member.bot:
            return

        # User joined voice channel
        if before.channel is None and after.channel is not None:
            await self.event_bus.publish(
                "user_joined_voice", member=member, channel=after.channel
            )

        # User left voice channel
        elif before.channel is not None and after.channel is None:
            await self.event_bus.publish(
                "user_left_voice", member=member, channel=before.channel
            )

    async def close(self) -> None:
        """Clean shutdown of the bot."""
        logger.info("Shutting down bot...")

        # Disconnect from all voice channels
        for voice_client in self.voice_clients:
            await voice_client.disconnect()

        # Close database connections
        if self.container.has("DatabaseManager"):
            db_manager = self.container.get("DatabaseManager")
            await db_manager.close()

        # Close cache connections
        if self.container.has("Cache"):
            cache = self.container.get("Cache")
            if hasattr(cache, "close"):
                await cache.close()

        await super().close()
        logger.info("Bot shutdown complete")
