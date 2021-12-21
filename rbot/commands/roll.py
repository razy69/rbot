# Built-in modules
import logging
import random

# External modules
from discord.ext import commands

LOGGER = logging.getLogger("rich")


class Roll(commands.Cog):
    """Rbot Roll command, you can get a dice roll using text chat."""

    def __init__(self):  # noqa:D107
        LOGGER.debug("Roll command registered")

    @commands.command()
    async def roll(self, ctx, number_of_dice: int = 1):
        """Roll command."""
        dice = [str(random.choice(range(1, 7))) for _ in range(number_of_dice)]  # nosec
        await ctx.reply(", ".join(dice))

    @roll.error
    async def roll_error(self, ctx, error):
        """Errors related to command."""
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.reply("ERROR: It misses the number of dices to roll, eg: !roll 2")
        if isinstance(error, commands.BadArgument):
            await ctx.reply("ERROR: Bad argument, eg: !roll number_of_dice")
