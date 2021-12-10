# External modules
from discord.ext import commands


class Clear(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.has_permissions(manage_messages=True, read_message_history=True)
    async def clear(self, ctx, number: int = 10):
        self.bot.logger.info(f"{ctx.author.name} deleted {number} messages from {ctx.channel.name}")
        await ctx.channel.purge(limit=number)

    @clear.error
    async def clear_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.reply("ERROR: It misses the number of messages to delete, eg: !clear 23")
        if isinstance(error, commands.BadArgument):
            await ctx.reply("ERROR: Bad argument, eg: !clear messages_to_delete")
        if isinstance(error, commands.MissingPermissions):
            await ctx.reply("ERROR: You don't have the right permissions to do that")
        else:
            await ctx.reply(f"ERROR: {error}")
