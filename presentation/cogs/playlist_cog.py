import logging
from discord.ext import commands
from core.dependency_injection import DIContainer
from domain.services.music_service import MusicService


class PlaylistCog(commands.Cog):
    """Playlist management commands."""
    
    def __init__(self, container: DIContainer):
        self.container = container
        self.music_service: MusicService = container.get(MusicService)


async def setup(bot):
    container = bot.container
    await bot.add_cog(PlaylistCog(container))