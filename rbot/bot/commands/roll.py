# Built-in modules
import random
import traceback
from contextlib import suppress

# External modules
import discord
from discord.ext import commands

# Internal modules
from rbot.bot.commands.base import Base


class Roll(Base):
    """Rbot Roll command, you can get a dice roll using text chat."""

    @commands.command(name="roll", help="Make a roll of x dice(s)")
    async def roll(self, ctx: commands.Context, number_of_dice: int = 1) -> discord.Message:
        """Roll command."""
        with suppress(discord.HTTPException, discord.NotFound):
            await ctx.message.delete()
        dice = [str(random.choice(range(1, 7))) for _ in range(number_of_dice)]  # nosec
        return await ctx.send(f"{ctx.author.name} throws {number_of_dice} dice(s): {', '.join(dice)}")

    @roll.error
    async def roll_error(self, ctx: commands.Context, error: Exception) -> discord.Message:
        """Errors related to command."""
        self.logger.error("Exception in roll: %s", traceback.format_exc())
        if isinstance(error, commands.MissingRequiredArgument):
            return await ctx.send("ERROR: It misses the number of dices to roll, eg: !roll 2")
        if isinstance(error, commands.BadArgument):
            return await ctx.send("ERROR: Bad argument, eg: !roll number_of_dice")
        return await ctx.send(f"ERROR: {error}")
