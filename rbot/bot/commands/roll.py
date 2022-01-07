# Built-in modules
import random

# External modules
from discord.ext import commands

# Internal modules
from rbot.bot.commands.base import Base


class Roll(Base):
    """Rbot Roll command, you can get a dice roll using text chat."""

    @commands.command(name="roll", help="Make a roll of x dice(s)")
    async def roll(self, ctx, number_of_dice: int = 1):
        """Roll command."""
        dice = [str(random.choice(range(1, 7))) for _ in range(number_of_dice)]  # nosec
        return await ctx.reply(", ".join(dice))

    @roll.error
    async def roll_error(self, ctx, error):
        """Errors related to command."""
        if isinstance(error, commands.MissingRequiredArgument):
            return await ctx.reply("ERROR: It misses the number of dices to roll, eg: !roll 2")
        if isinstance(error, commands.BadArgument):
            return await ctx.reply("ERROR: Bad argument, eg: !roll number_of_dice")
        else:
            return await ctx.reply(f"ERROR: {error}")
