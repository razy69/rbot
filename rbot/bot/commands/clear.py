# External modules
from discord.ext import commands

# Internal modules
from rbot.bot.commands.base import Base


class Clear(Base):
    """Rbot Clear command, you can get delete messages in a chan."""

    @commands.command(name="clear", help="Clear x messages from the current channel")
    @commands.has_permissions(manage_messages=True, read_message_history=True)
    async def clear(self, ctx, number: int = 10):
        """Clear command."""
        return await ctx.channel.purge(limit=number)

    @clear.error
    async def clear_error(self, ctx, error):
        """Errors related to command."""
        if isinstance(error, commands.MissingRequiredArgument):
            return await ctx.reply("ERROR: It misses the number of messages to delete, eg: !clear 23")
        if isinstance(error, commands.BadArgument):
            return await ctx.reply("ERROR: Bad argument, eg: !clear messages_to_delete")
        if isinstance(error, commands.MissingPermissions):
            return await ctx.reply("ERROR: You don't have the right permissions to do that")
        else:
            return await ctx.reply(f"ERROR: {error}")
