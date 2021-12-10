# Built-in modules
import random

# External modules
from discord.ext import commands


class Roll(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def roll(self, ctx, number_of_dice: int = 1):
        dice = [str(random.choice(range(1, 7))) for _ in range(number_of_dice)]  # nosec
        await ctx.reply(", ".join(dice))

    @roll.error
    async def roll_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.reply("ERROR: It misses the number of dices to roll, eg: !roll 2")
        if isinstance(error, commands.BadArgument):
            await ctx.reply("ERROR: Bad argument, eg: !roll number_of_dice")
