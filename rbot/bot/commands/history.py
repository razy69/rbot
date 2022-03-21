# Built-in modules
import json
from contextlib import suppress

# External modules
import discord
from discord.ext import commands

# Internal modules
from rbot.bot.commands.base import Base


class History(Base):
    """."""

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    @commands.command(name="history", help="Save x lines of a channel")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def history(self, ctx, channel: str, limit: int = 10000):
        """History command."""
        history: list = []
        chan = discord.utils.find(lambda c: c.name == channel, self.bot.guild.text_channels)
        async for msg in chan.history(limit=limit):
            if msg.author == ctx.author or msg.author.name == self.bot.user.name:
                continue
            if len(history) == limit:
                break
            history.append(
                {
                    "content": msg.content,
                    "created_at": msg.created_at.strftime("%Y-%m-%dT%H:%M:%S"),
                    "author_name": msg.author.name,
                },
            )
        if not history:
            return await ctx.reply(
                f"In the {limit} message of `{channel}`, no messages",
                f"to save of other users (not @{ctx.author.name} or the bot)",
            )
        await History._to_json(history)
        return await ctx.reply(
            f"{len(history)} messages of channel `{channel}` have been saved.",
        )

    @history.error
    async def history_error(self, ctx, error):
        """Errors related to command."""
        if isinstance(error, commands.NoPrivateMessage):
            with suppress(discord.HTTPException):
                return await ctx.reply("This command can not be used in Private Messages.")
        if isinstance(error, commands.MissingRequiredArgument):
            return await ctx.reply(
                "ERROR: It misses the channel and/or the number of messages to save, eg: !history général 2",
            )
        if isinstance(error, commands.BadArgument):
            return await ctx.reply("ERROR: Bad argument, eg: !history <channel> <number_of_messages>")
        else:
            return await ctx.reply(f"ERROR: {error}")

    @staticmethod
    async def _to_json(data, path: str = "./history.json"):
        with open(path, "w+", encoding="utf-8") as _file:
            return json.dump(data, _file, ensure_ascii=False, indent=4)
