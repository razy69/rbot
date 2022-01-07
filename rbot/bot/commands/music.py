# External modules
import discord
from discord.ext import commands

# Internal modules
from rbot.bot.commands.base import Base
from rbot.utils.yt_player import YTDLSource


class Music(Base):
    """Rbot Music stream music to a chan from youtube, or your computer."""

    def __init__(self, bot):  # noqa:D107
        super().__init__()
        self.bot = bot

    @commands.command(name="stop", help="To make the bot leave the voice channel")
    @commands.has_permissions(administrator=True)
    async def stop(self, ctx):
        """Stop command."""
        voice_client = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
        if voice_client.is_connected():
            await voice_client.disconnect()
            await ctx.reply("You stopped the Music player")
            await self.bot.change_presence(status=discord.Status.idle)
        else:
            await ctx.reply("The bot is not connected to a voice channel.")

    @stop.error
    async def stop_error(self, ctx, error):
        """Errors related to `stop` command."""
        if isinstance(error, commands.MissingPermissions):
            await ctx.reply("ERROR: You don't have the right permissions to do that")
        else:
            await ctx.reply(f"ERROR: {error}")

    @commands.command(name="play", help="Play music from your computer")
    @commands.has_permissions(administrator=True)
    async def play(self, ctx, *, query):
        """Plays a file from the local filesystem."""
        source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(query))
        ctx.voice_client.play(source, after=lambda e: print(f"Player error: {e}") if e else None)
        await ctx.reply(f"Now playing: {query}")

    @play.error
    async def play_error(self, ctx, error):
        """Errors related to `play` command."""
        if isinstance(error, commands.MissingRequiredArgument):
            return await ctx.reply("ERROR: It misses the query")
        if isinstance(error, commands.BadArgument):
            return await ctx.reply("ERROR: Bad argument")
        if isinstance(error, commands.MissingPermissions):
            return await ctx.reply("ERROR: You don't have the right permissions to do that")
        else:
            return await ctx.reply(f"ERROR: {error}")

    @commands.command(name="yt", help="Download yt video and play song")
    @commands.has_permissions(administrator=True)
    async def yt(self, ctx, *, url):
        """Plays from a url (almost anything youtube_dl supports)."""
        async with ctx.typing():
            player = await YTDLSource.from_url(url, loop=self.bot.loop)
            ctx.voice_client.play(player, after=lambda e: print(f"Player error: {e}") if e else None)
            await self.bot.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.listening,
                    name=f"🎵 {player.title} 🎵",
                ),
            )
        await ctx.reply(f"Now playing: {player.title}")

    @yt.error
    async def yt_error(self, ctx, error):
        """Errors related to `yt` command."""
        if isinstance(error, commands.MissingRequiredArgument):
            return await ctx.reply("ERROR: It misses the query")
        if isinstance(error, commands.BadArgument):
            return await ctx.reply("ERROR: Bad argument")
        if isinstance(error, commands.MissingPermissions):
            return await ctx.reply("ERROR: You don't have the right permissions to do that")
        else:
            return await ctx.reply(f"ERROR: {error}")

    @commands.command(name="stream", help="Stream yt music")
    @commands.has_permissions(administrator=True)
    async def stream(self, ctx, *, url):
        """Streams from a url (same as yt, but doesn't predownload)."""
        async with ctx.typing():
            player = await YTDLSource.from_url(url, loop=self.bot.loop, stream=True)
            ctx.voice_client.play(player, after=lambda e: print(f"Player error: {e}") if e else None)
            await self.bot.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.listening,
                    name=f"🎵 {player.title} 🎵",
                ),
            )
        return await ctx.reply(f"Now playing: {player.title}")

    @stream.error
    async def stream_error(self, ctx, error):
        """Errors related to `stream` command."""
        if isinstance(error, commands.MissingRequiredArgument):
            return await ctx.reply("ERROR: It misses the the url")
        if isinstance(error, commands.BadArgument):
            return await ctx.reply("ERROR: Bad argument")
        if isinstance(error, commands.MissingPermissions):
            return await ctx.reply("ERROR: You don't have the right permissions to do that")
        else:
            return await ctx.reply(f"ERROR: {error}")

    @commands.command(name="volume", help="Set Rbot volume")
    @commands.has_permissions(administrator=True)
    async def volume(self, ctx, volume: int):
        """Changes the player's volume."""
        if ctx.voice_client is None:
            return await ctx.reply("Not connected to a voice channel.")
        ctx.voice_client.source.volume = volume / 100
        return await ctx.reply(f"Changed volume to {volume}%")

    @volume.error
    async def volume_error(self, ctx, error):
        """Errors related to `volume` command."""
        if isinstance(error, commands.MissingRequiredArgument):
            return await ctx.reply("ERROR: It misses the volume to set")
        if isinstance(error, commands.BadArgument):
            return await ctx.reply("ERROR: Bad argument, eg: !volume 0.1")
        if isinstance(error, commands.MissingPermissions):
            return await ctx.reply("ERROR: You don't have the right permissions to do that")
        else:
            return await ctx.reply(f"ERROR: {error}")

    @play.before_invoke
    @yt.before_invoke
    @stream.before_invoke
    async def ensure_voice(self, ctx):
        """Ensure bot is connected to a channel before playing a music."""
        if ctx.voice_client is None:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
            else:
                await ctx.reply("You are not connected to a voice channel.")
                raise commands.CommandError("Author not connected to a voice channel.")
        elif ctx.voice_client.is_playing():
            ctx.voice_client.stop()
