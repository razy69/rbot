# Builtin modules
import asyncio
import itertools
from contextlib import suppress

# External modules
import discord
from async_timeout import timeout
from discord.ext import commands

# Internal modules
from rbot.bot.commands.base import Base
from rbot.utils.yt_player import YTDLSource


class MusicPlayer(commands.Cog):
    """A class which is assigned to each guild using the bot for Music.

    This class implements a queue and loop, which allows for different guilds to listen to different playlists
    simultaneously.
    When the bot disconnects from the Voice it's instance will be destroyed.
    """

    def __init__(self, ctx):
        self.bot = ctx.bot
        self._guild = ctx.guild
        self._channel = ctx.channel
        self._cog = ctx.cog
        self.queue = asyncio.Queue()
        self.next = asyncio.Event()
        self.np = None  # Now playing message
        self.volume = 0.5
        self.current = None
        ctx.bot.loop.create_task(self.player_loop())

    async def player_loop(self):
        """Our main player loop."""
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            self.next.clear()
            try:
                # Wait for the next song. If we timeout cancel the player and disconnect...
                async with timeout(300):
                    source = await self.queue.get()
            except asyncio.TimeoutError:
                return self.destroy(self._guild)
            if not isinstance(source, YTDLSource):
                try:
                    source = await YTDLSource.regather_stream(source, loop=self.bot.loop)
                except Exception as e:
                    await self._channel.send(f"There was an error processing your song.\n" f"```css\n[{e}]\n```")
                    continue
            source.volume = self.volume
            self.current = source
            self._guild.voice_client.play(source, after=lambda _: self.bot.loop.call_soon_threadsafe(self.next.set))
            await self.bot.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.listening,
                    name=f"🎵 {source.title} 🎵",
                ),
            )
            self.np = await self._channel.send(
                f"**Now Playing:** `{source.title}` requested by " f"`{source.requester}`",
            )
            await self.next.wait()
            # Make sure the FFmpeg process is cleaned up.
            source.cleanup()
            self.current = None
            with suppress(discord.HTTPException):
                # We are no longer playing this song...
                await self.np.delete()

    def destroy(self, guild):
        """Disconnect and cleanup the player."""
        return self.bot.loop.create_task(self._cog.cleanup(guild))


class Music(Base):
    """Rbot Music stream music to a chan from youtube, or your computer."""

    def __init__(self, bot):  # noqa:D107
        super().__init__()
        self.bot = bot
        self.players: dict = {}

    def get_player(self, ctx) -> MusicPlayer:
        """Retrieve the guild player, or generate one."""
        if not self.players.get(ctx.guild.id, None):
            self.players[ctx.guild.id] = MusicPlayer(ctx)
        return self.players[ctx.guild.id]

    async def cleanup(self, guild):
        """Cleanup bot, disconnect it and properly remove player."""
        with suppress(AttributeError):
            await guild.voice_client.disconnect()
        with suppress(KeyError):
            del self.players[guild.id]
        return await self.bot.change_presence(status=discord.Status.idle)

    def is_invoked_in_music_chan(ctx):  # noqa: N805
        """Check if command has been invoked in the right chan."""
        if ctx.message.channel.name != ctx.bot.settings.music_chan:
            raise commands.UserInputError(f"You have to run command in the {ctx.bot.settings.music_chan} channel")
        return True

    @commands.command(name="play", aliases=["yt", "pl"], help="Play a song from Youtube url")
    @commands.check(is_invoked_in_music_chan)
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def play(self, ctx, search: str):
        """Play the given youtube url.

        Args:
            ctx (context): discord.ext.commands.Context
            search (str): Url of a Youtube video.
        """
        player = self.get_player(ctx)
        source = await YTDLSource.create_source(ctx, search, loop=self.bot.loop)
        return await player.queue.put(source)

    @play.error
    async def play_error(self, ctx, error):
        """Errors related to `play` command."""
        if isinstance(error, commands.NoPrivateMessage):
            with suppress(discord.HTTPException):
                return await ctx.reply("This command can not be used in Private Messages.")
        if isinstance(error, commands.MissingRequiredArgument):
            return await ctx.reply("ERROR: It misses the the url")
        if isinstance(error, commands.BadArgument):
            return await ctx.reply(f"ERROR: Bad argument -> {error}")
        if isinstance(error, commands.MissingPermissions):
            return await ctx.reply("ERROR: You don't have the right permissions to do that")
        return await ctx.reply(f"ERROR: {error}")

    @commands.command(name="pause", aliases=["pa"], help="Pause music")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def pause(self, ctx):
        """Pause the currently playing song."""
        if ctx.voice_client.is_paused():
            return await ctx.reply(f"**`{ctx.author.name}`**: Error player is already paused!")
        ctx.voice_client.pause()
        return await ctx.reply(f"**`{ctx.author.name}`**: Paused the song!")

    @pause.error
    async def pause_error(self, ctx, error):
        """Errors related to `pause` command."""
        if isinstance(error, commands.NoPrivateMessage):
            with suppress(discord.HTTPException):
                return await ctx.reply("This command can not be used in Private Messages.")
        if isinstance(error, commands.MissingPermissions):
            await ctx.reply("ERROR: You don't have the right permissions to do that")
        return await ctx.reply(f"ERROR: {error}")

    @commands.command(name="resume", aliases=["unpause", "res"], help="Resume music")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def resume(self, ctx):
        """Resume the currently paused song."""
        if not ctx.voice_client.is_paused():
            return await ctx.reply(f"**`{ctx.author.name}`**: Error player is not paused!")
        ctx.voice_client.resume()
        return await ctx.reply(f"**`{ctx.author.name}`**: Resumed the song!")

    @resume.error
    async def resume_error(self, ctx, error):
        """Errors related to `resume` command."""
        if isinstance(error, commands.NoPrivateMessage):
            with suppress(discord.HTTPException):
                return await ctx.reply("This command can not be used in Private Messages.")
        if isinstance(error, commands.MissingPermissions):
            return await ctx.reply("ERROR: You don't have the right permissions to do that")
        return await ctx.reply(f"ERROR: {error}")

    @commands.command(name="skip", aliases=["skp"], help="Play next music in the list")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def skip(self, ctx):
        """Skip the song."""
        if ctx.voice_client.is_paused():
            pass
        elif not ctx.voice_client.is_playing():
            return await ctx.reply(f"**`{ctx.author.name}`**: Player is not playing a song!")
        ctx.voice_client.stop()
        return await ctx.reply(f"**`{ctx.author.name}`**: Skipped the song!")

    @skip.error
    async def skip_error(self, ctx, error):
        """Errors related to `skip` command."""
        if isinstance(error, commands.NoPrivateMessage):
            with suppress(discord.HTTPException):
                return await ctx.reply("This command can not be used in Private Messages.")
        if isinstance(error, commands.MissingPermissions):
            return await ctx.reply("ERROR: You don't have the right permissions to do that")
        return await ctx.reply(f"ERROR: {error}")

    @commands.command(name="queue", aliases=["ql", "playlist", "playlst"], help="Show next songs")
    @commands.guild_only()
    async def queue(self, ctx):
        """Retrieve a basic queue of upcoming songs."""
        player = self.get_player(ctx)
        if player.queue.empty():
            return await ctx.reply("There are currently no more queued songs.")
        # Grab up to 5 entries from the queue...
        upcoming = list(itertools.islice(player.queue._queue, 0, 9))
        fmt = "\n".join(f'**`{_["title"]}`**' for _ in upcoming)
        embed = discord.Embed(title=f"Playlist - Next {len(upcoming)} Songs", description=fmt)
        return await ctx.reply(embed=embed)

    @queue.error
    async def queue_error(self, ctx, error):
        """Errors related to `queue` command."""
        if isinstance(error, commands.NoPrivateMessage):
            with suppress(discord.HTTPException):
                return await ctx.reply("This command can not be used in Private Messages.")
        if isinstance(error, commands.MissingPermissions):
            return await ctx.reply("ERROR: You don't have the right permissions to do that")
        return await ctx.reply(f"ERROR: {error}")

    @commands.command(name="now", aliases=["np", "current", "currentsong", "playing"], help="Show current music")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def now(self, ctx):
        """Display information about the currently playing song."""
        player = self.get_player(ctx)
        if not player.current:
            return await ctx.reply("No music currently playing !")
        with suppress(discord.HTTPException):
            # Remove our previous now_playing message.
            await player.np.delete()
        return await ctx.reply(
            f"**Now Playing:** `{ctx.voice_client.source.title}` requested by `{ctx.voice_client.source.requester}`",
        )

    @now.error
    async def now_error(self, ctx, error):
        """Errors related to `now` command."""
        if isinstance(error, commands.NoPrivateMessage):
            with suppress(discord.HTTPException):
                return await ctx.reply("This command can not be used in Private Messages.")
        if isinstance(error, commands.MissingPermissions):
            return await ctx.reply("ERROR: You don't have the right permissions to do that")
        return await ctx.reply(f"ERROR: {error}")

    @commands.command(name="volume", aliases=["vol"], help="Change bot volume")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def volume(self, ctx, vol: float):
        """Command to set volume.

        Args:
            ctx (context): discord.ext.commands.Context
            vol (float): Volume in %, must be a value between 1 and 100
        """
        if not 0 < vol < 101:
            return await ctx.reply("Please enter a value between 1 and 100.")
        player = self.get_player(ctx)
        if ctx.voice_client.source:
            ctx.voice_client.source.volume = vol / 100
        player.volume = vol / 100
        embed = discord.Embed(title="Volume Message", description=f"The Volume Was Changed By **{ctx.author.name}**")
        embed.add_field(name="Current Volume", value=vol, inline=True)
        return await ctx.reply(embed=embed)

    @volume.error
    async def volume_error(self, ctx, error):
        """Errors related to `volume` command."""
        if isinstance(error, commands.NoPrivateMessage):
            with suppress(discord.HTTPException):
                return await ctx.reply("This command can not be used in Private Messages.")
        if isinstance(error, commands.MissingPermissions):
            return await ctx.reply("ERROR: You don't have the right permissions to do that")
        return await ctx.reply(f"ERROR: {error}")

    @commands.command(name="stop", aliases=["stp"], help="To make the bot leave the voice channel")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def stop(self, ctx):
        """Stop command."""
        self.cleanup(ctx.guild)
        await ctx.reply(f"{ctx.author.name} stopped the Music player")

    @stop.error
    async def stop_error(self, ctx, error):
        """Errors related to `stop` command."""
        if isinstance(error, commands.NoPrivateMessage):
            with suppress(discord.HTTPException):
                return await ctx.reply("This command can not be used in Private Messages.")
        if isinstance(error, commands.MissingPermissions):
            return await ctx.reply("ERROR: You don't have the right permissions to do that")
        return await ctx.reply(f"ERROR: {error}")

    @pause.before_invoke
    async def ensure_playing(self, ctx):
        """Ensure bot is connected and playing a music."""
        await self.ensure_voice(ctx)
        if not ctx.voice_client.is_playing():
            await ctx.reply("No music is playing.")
            raise commands.CommandError("Bot is not playing a music.")

    @play.before_invoke
    @resume.before_invoke
    @skip.before_invoke
    @queue.before_invoke
    @now.before_invoke
    @volume.before_invoke
    @stop.before_invoke
    async def ensure_voice(self, ctx):
        """Ensure bot is connected to a channel before playing a music."""
        if ctx.voice_client is not None and ctx.voice_client.is_connected():
            return
        if ctx.author.voice:
            await ctx.author.voice.channel.connect()
        else:
            await ctx.reply("You are not connected to a voice channel.")
            raise commands.CommandError(f"{ctx.author.name} not connected to a voice channel.")
