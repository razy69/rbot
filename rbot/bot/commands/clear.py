# Built-in modules
from contextlib import suppress

# External modules
import discord
from discord.ext import commands

# Internal modules
from rbot.bot.commands.base import Base


class Clear(Base):
    """Rbot Clear command, you can get delete messages in a chan."""

    @commands.command(name="clear", help="Clear x messages from the current channel")
    @commands.has_permissions(manage_messages=True, read_message_history=True)
    @commands.guild_only()
    async def clear(self, ctx, number: int = 10):
        """Clear command."""
        with suppress(discord.HTTPException, discord.NotFound):
            await ctx.message.delete()
        return await ctx.channel.purge(limit=number)

    @clear.error
    async def clear_error(self, ctx, error):
        """Errors related to command."""
        if isinstance(error, commands.NoPrivateMessage):
            with suppress(discord.HTTPException):
                return await ctx.send("This command can not be used in Private Messages.")
        if isinstance(error, commands.MissingRequiredArgument):
            return await ctx.send("ERROR: It misses the number of messages to delete, eg: !clear 23")
        if isinstance(error, commands.BadArgument):
            return await ctx.send("ERROR: Bad argument, eg: !clear messages_to_delete")
        if isinstance(error, commands.MissingPermissions):
            return await ctx.send("ERROR: You don't have the right permissions to do that")
        return await ctx.send(f"ERROR: {error}")
