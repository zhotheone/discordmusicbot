import logging
from discord.ext import commands
from discord import app_commands
from core.dependency_injection import DIContainer
from domain.services.filter_service import FilterService


class FiltersCog(commands.Cog):
    """Audio filter commands."""
    
    def __init__(self, container: DIContainer):
        self.container = container
        self.filter_service: FilterService = container.get(FilterService)


async def setup(bot):
    container = bot.container
    await bot.add_cog(FiltersCog(container))