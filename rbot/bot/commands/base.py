# Built-in modules
import logging

# External modules
from discord.ext import commands


class Base(commands.Cog):
    """Rbot Base command."""

    def __init__(self, logger: logging.Logger = None):  # noqa:D107
        if logger:
            self.logger = logger
        else:
            self.logger = logging.getLogger("rich")
        self.logger.debug("%s command registered", self.__class__.__name__)

    async def cog_after_invoke(self, ctx: commands.Context) -> None:
        """Action run after each cog invoke."""
        params = ctx.args[2:]
        self.logger.info(f"Command '{ctx.invoked_with}' has been executed by '{ctx.author.name}' with {params=}")
