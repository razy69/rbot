# Built-in modules
import logging

# External modules
import discord
from discord.ext import commands

from rbot.bot.commands.clear import Clear
from rbot.bot.commands.history import History
from rbot.bot.commands.music import Music
from rbot.bot.commands.roll import Roll

# Internal modules
from rbot.utils.settings import get_settings

LOGGER = logging.getLogger("rich")
INTENTS = discord.Intents.default()
INTENTS.members = True


class Rbot(commands.Bot):
    """Discord Bot."""

    def __init__(
        self,
        intents=INTENTS,
    ):  # noqa:D107
        super().__init__(self, intents=intents)
        self.settings = get_settings()
        self.command_prefix = self.settings.command_prefix

    def setup(self):
        """Register commands to the bot."""
        self.add_cog(Roll())
        self.add_cog(Clear())
        self.add_cog(Music(bot=self))
        self.add_cog(History(bot=self))

    async def on_ready(self):
        """Events once bot is in ready state."""
        self.guild = discord.utils.get(iterable=self.guilds, name=self.settings.discord_server)
        LOGGER.info(
            f"[bold green]Connected to discord ![/bold green]\r\n\r\n"
            f"---\r\n"
            f"bot_name: {self.user}\r\n"
            f"guild_name: {self.guild.name}\r\n"
            f"guild_id: {self.guild.id}\r\n"
            f"---\r\n\r\n",
            extra={"markup": True},
        )
        status_chan = discord.utils.find(lambda chan: chan.name == self.settings.status_chan, self.guild.text_channels)
        await status_chan.send("Rbot activated.. 🚀")
        await self.change_presence(status=discord.Status.idle)


def start_bot() -> None:
    """Start a Discord Bot with settings from env (or .config)."""
    try:
        settings = get_settings()
        bot = Rbot()
        bot.setup()
        bot.run(settings.discord_token)
    except discord.errors.LoginFailure as _error:
        LOGGER.error(f"Failed to run bot: Authentication failure, check your token ({_error})")
    except discord.errors.PrivilegedIntentsRequired as _error:
        LOGGER.error(f"Failed to run bot: It doesn't have intents privileges explicitly enabled ({_error})")