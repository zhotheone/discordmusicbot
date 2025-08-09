import logging
from discord.ext import commands
from core.dependency_injection import DIContainer


class AdminCog(commands.Cog):
    """Administrative commands."""
    
    def __init__(self, container: DIContainer):
        self.container = container


async def setup(bot):
    container = bot.container
    await bot.add_cog(AdminCog(container))