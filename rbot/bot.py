# Built-in modules
import logging

# External modules
import discord
from discord.ext import commands

# Internal modules
from rbot.commands.clear import Clear
from rbot.commands.roll import Roll

INTENTS = discord.Intents.default()
INTENTS.members = True


class Rbot(commands.Bot):
    """Discord Bot."""

    def __init__(
        self,
        config: dict,
        logger: logging.Logger = None,
        command_prefix: str = "!",
        intents=INTENTS,
    ):  # noqa:D107
        super().__init__(self, intents=intents)
        self.command_prefix = command_prefix
        self.config = config
        if not logger:
            self.logger = logging.getLogger()
        else:
            self.logger = logger

    def setup(self):
        """Register commands to the bot."""
        self.add_cog(Roll())
        self.add_cog(Clear())

    async def on_ready(self):
        """Events once bot is in ready state."""
        server = discord.utils.get(iterable=self.guilds, name=self.config.get("discord_server", ""))
        self.logger.info(
            f"[bold green]Connected to discord ![/bold green]\r\n\r\n"
            f"---\r\n"
            f"bot_name: {self.user}\r\n"
            f"server_name: {server.name}\r\n"
            f"server_id: {server.id}\r\n"
            f"---\r\n\r\n",
            extra={"markup": True},
        )
