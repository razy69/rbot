# Builtin modules
import asyncio
import itertools
from contextlib import suppress
from datetime import datetime

# External modules
import discord
from async_timeout import timeout
from discord.ext import commands
from youtubesearchpython import VideosSearch

# Internal modules
from rbot.bot.commands.base import Base
from rbot.utils.settings import get_settings
from rbot.utils.yt_player import YTDLSource


MUSIC_ROLE = get_settings().music_role

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
        self.volume = 1
        self.current = None
        self.bot.loop.create_task(self.player_loop())

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
            embed = discord.Embed(
                title="Now Playing",
                description=f"[{source.title}]({source.webpage_url}) - {source.duration}",
                color=discord.Color.green(),
            )
            embed.set_thumbnail(url=source.thumbnail)
            embed.timestamp = datetime.now()
            self.np = await self._channel.send(embed=embed)
            await self.next.wait()
            # Make sure the FFmpeg process is cleaned up.
            source.cleanup()
            self.current = None
            with suppress(discord.HTTPException, discord.NotFound):
                # We are no longer playing this song...
                await self.np.delete()

    def destroy(self, guild):
        """Disconnect and cleanup the player."""
        return self.bot.loop.create_task(self._cog.cleanup(guild))


class Music(Base):
    """Rbot Music stream music to a chan from youtube."""

    def __init__(self, bot):  # noqa:D107
        super().__init__()
        self.bot = bot
        self.player: MusicPlayer = None
        self.playlist = None

    def get_player(self, ctx) -> MusicPlayer:
        """Retrieve the guild player, or generate one."""
        if not self.player:
            self.player = MusicPlayer(ctx)
        return self.player

    async def cleanup(self, guild):
        """Cleanup bot, disconnect it and properly remove player."""
        self.logger.info("Cleanup Music Player")
        await self.bot.change_presence(status=discord.Status.idle)
        if isinstance(self.playlist, discord.Message):
            with suppress(discord.HTTPException, discord.NotFound):
                await self.playlist.delete()
        if isinstance(self.player.np, discord.Message):
            with suppress(discord.HTTPException, discord.NotFound):
                await self.player.np.delete()
        if isinstance(self.player, MusicPlayer):
            self.player = None
        if isinstance(guild.voice_client, discord.VoiceProtocol):
            await guild.voice_client.disconnect()

    def is_invoked_in_music_chan(ctx):  # noqa: N805
        """Check if command has been invoked in the right chan."""
        if ctx.message.channel.name != ctx.bot.settings.music_chan:
            raise commands.UserInputError(f"You have to run command in the {ctx.bot.settings.music_chan} channel")
        return True

    def gen_yt_select_menu(self, search: str) -> discord.SelectMenu:
        """Generate a discord.SelectMenu using Youtube search results from youtubesearchpython."""
        videos_search = VideosSearch(search, limit = 10).result()
        videos_search = videos_search.get("result", [])
        emojis=["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        results = [
            discord.SelectOption(
                label=f"{video.get('title', '')}"[:25],
                description=f"{video.get('duration', '')} - {video.get('publishedTime', '')} - {video.get('viewCount', {}).get('short', '')} - {video.get('channel', {}).get('name')}"[:50],
                value=video.get("link", ""),
                emoji=emojis[i],
            )
            for i, video in enumerate(videos_search)
        ]
        results.append(
            discord.SelectOption(
                label="Quit",
                description="Stop your current search",
                value="_quit",
                emoji="❌",
            )
        )
        select_menu = discord.SelectMenu(
            custom_id="select_yt_result",
            options=results,
            placeholder="Select a song",
            max_values=1,
            min_values=1,
        )
        return select_menu

    @commands.command(name="search", aliases=["s"], help="Search a music from Youtube and play it !")
    @commands.check(is_invoked_in_music_chan)
    @commands.has_role(MUSIC_ROLE)
    @commands.guild_only()
    async def search(self, ctx, search: str, *args):
        """
        Play the given youtube search.

        Args:
            ctx (context): discord.ext.commands.Context
            search (str): a text to search a Youtube video.
        """
        _args = [arg for arg in args]
        if _args:
            search = f"{search.strip()} {' '.join(_args)}"
        self.logger.info("Search query: %s", search)
        select_songs = self.gen_yt_select_menu(search)
        msg_with_selects = await ctx.reply(
            title=f"Youtube search results for {search}:",
            components=[[select_songs]]
        )

        def check_selection(i: discord.Interaction, select_menu):
            return i.author == ctx.author and i.message == msg_with_selects

        _, select_menu = await self.bot.wait_for('selection_select', check=check_selection)
        with suppress(discord.HTTPException, discord.NotFound):
            await ctx.message.delete()
            await msg_with_selects.delete()
        if select_menu.values[0] == "_quit":
            return
        player = self.get_player(ctx)
        source = await YTDLSource.create_source(ctx, search=select_menu.values[0], loop=self.bot.loop)
        return await player.queue.put(source)
    
    @search.error
    async def search_error(self, ctx, error):
        """Errors related to `search` command."""
        if isinstance(error, commands.NoPrivateMessage):
            with suppress(discord.HTTPException):
                return await ctx.send("This command can not be used in Private Messages.")
        if isinstance(error, commands.MissingRequiredArgument):
            return await ctx.send("ERROR: It misses the the url")
        if isinstance(error, commands.BadArgument):
            return await ctx.send(f"ERROR: Bad argument -> {error}")
        if isinstance(error, commands.MissingPermissions):
            return await ctx.send("ERROR: You don't have the right permissions to do that")
        return await ctx.send(f"ERROR: {error}")
        
    @commands.command(name="play", aliases=["yt", "pl"], help="Play a song from Youtube url")
    @commands.check(is_invoked_in_music_chan)
    @commands.has_role(MUSIC_ROLE)
    @commands.guild_only()
    async def play(self, ctx, search: str):
        """
        Play the given youtube url.

        Args:
            ctx (context): discord.ext.commands.Context
            search (str): Url of a Youtube video.
        """
        with suppress(discord.HTTPException, discord.NotFound):
            await ctx.message.delete()
        player = self.get_player(ctx)
        source = await YTDLSource.create_source(ctx, search, loop=self.bot.loop)
        return await player.queue.put(source)

    @play.error
    async def play_error(self, ctx, error):
        """Errors related to `play` command."""
        if isinstance(error, commands.NoPrivateMessage):
            with suppress(discord.HTTPException):
                return await ctx.send("This command can not be used in Private Messages.")
        if isinstance(error, commands.MissingRequiredArgument):
            return await ctx.send("ERROR: It misses the the url")
        if isinstance(error, commands.BadArgument):
            return await ctx.send(f"ERROR: Bad argument -> {error}")
        if isinstance(error, commands.MissingPermissions):
            return await ctx.send("ERROR: You don't have the right permissions to do that")
        return await ctx.send(f"ERROR: {error}")

    @commands.command(name="pause", aliases=["pa"], help="Pause music")
    @commands.has_role(MUSIC_ROLE)
    @commands.guild_only()
    async def pause(self, ctx):
        """Pause the currently playing song."""
        with suppress(discord.HTTPException, discord.NotFound):
            await ctx.message.delete()
        if ctx.voice_client.is_paused():
            return await ctx.send(f"**`{ctx.author.name}`**: Player is already paused !")
        player = self.get_player(ctx)
        ctx.voice_client.pause()
        return await ctx.send(f"**`{ctx.author.name}`**: Paused `{player.current.title}`")

    @pause.error
    async def pause_error(self, ctx, error):
        """Errors related to `pause` command."""
        if isinstance(error, commands.NoPrivateMessage):
            with suppress(discord.HTTPException):
                return await ctx.send("This command can not be used in Private Messages.")
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("ERROR: You don't have the right permissions to do that")
        return await ctx.send(f"ERROR: {error}")

    @commands.command(name="resume", aliases=["unpause", "res"], help="Resume music")
    @commands.has_role(MUSIC_ROLE)
    @commands.guild_only()
    async def resume(self, ctx):
        """Resume the currently paused song."""
        with suppress(discord.HTTPException, discord.NotFound):
            await ctx.message.delete()
        if not ctx.voice_client.is_paused():
            return await ctx.send(f"**`{ctx.author.name}`**: Player is not paused !")
        player = self.get_player(ctx)
        ctx.voice_client.resume()
        return await ctx.send(f"**`{ctx.author.name}`**: Resumed `{player.current.title}`")

    @resume.error
    async def resume_error(self, ctx, error):
        """Errors related to `resume` command."""
        if isinstance(error, commands.NoPrivateMessage):
            with suppress(discord.HTTPException):
                return await ctx.send("This command can not be used in Private Messages.")
        if isinstance(error, commands.MissingPermissions):
            return await ctx.send("ERROR: You don't have the right permissions to do that")
        return await ctx.send(f"ERROR: {error}")

    @commands.command(name="skip", aliases=["skp", "next"], help="Play next music in the list")
    @commands.has_role(MUSIC_ROLE)
    @commands.guild_only()
    async def skip(self, ctx):
        """Skip the song."""
        with suppress(discord.HTTPException, discord.NotFound):
            await ctx.message.delete()
        if ctx.voice_client.is_paused():
            pass
        elif not ctx.voice_client.is_playing():
            return await ctx.send(f"**`{ctx.author.name}`**: Player is not playing a song!")
        player = self.get_player(ctx)
        ctx.voice_client.stop()
        return await ctx.send(f"**`{ctx.author.name}`**: Skipped `{player.current.title}`")

    @skip.error
    async def skip_error(self, ctx, error):
        """Errors related to `skip` command."""
        if isinstance(error, commands.NoPrivateMessage):
            with suppress(discord.HTTPException):
                return await ctx.send("This command can not be used in Private Messages.")
        if isinstance(error, commands.MissingPermissions):
            return await ctx.send("ERROR: You don't have the right permissions to do that")
        return await ctx.send(f"ERROR: {error}")

    @commands.command(name="now", aliases=["np", "current", "currentsong", "playing"], help="Show current music")
    @commands.has_role(MUSIC_ROLE)
    @commands.guild_only()
    async def now(self, ctx):
        """Display information about the currently playing song."""
        with suppress(discord.HTTPException, discord.NotFound):
            await ctx.message.delete()
        player = self.get_player(ctx)
        if not player.current:
            return await ctx.send("No music currently playing !")
        with suppress(discord.HTTPException, discord.NotFound):
            # Remove our previous now_playing message.
            await player.np.delete()
        embed = discord.Embed(
            title="Now Playing",
            description=f"[{player.current.title}]({player.current.webpage_url}) - {player.current.duration}",
            color=discord.Color.green(),
        )
        embed.set_thumbnail(url=player.current.thumbnail)
        embed.timestamp = datetime.now()
        player.np = await ctx.send(embed=embed)
        return player.np

    @now.error
    async def now_error(self, ctx, error):
        """Errors related to `now` command."""
        if isinstance(error, commands.NoPrivateMessage):
            with suppress(discord.HTTPException):
                return await ctx.send("This command can not be used in Private Messages.")
        if isinstance(error, commands.MissingPermissions):
            return await ctx.send("ERROR: You don't have the right permissions to do that")
        return await ctx.send(f"ERROR: {error}")

    @commands.command(name="queue", aliases=["ql", "playlist", "playlst"], help="Show next songs")
    @commands.guild_only()
    async def queue(self, ctx):
        """Retrieve a basic queue of upcoming songs."""
        with suppress(discord.HTTPException, discord.NotFound):
            await ctx.message.delete()
        player = self.get_player(ctx)
        if player.queue.empty():
            upcoming = []
        else:
            upcoming = list(itertools.islice(player.queue._queue, 0, 9))
        if not upcoming:
            desc = "No other music in the playlist."
        elif len(upcoming) == 1:
            desc = "1 music left in the playlist."
        else:
            desc = f"There are {len(upcoming)} musics in the queue."
        embed = discord.Embed(
            title="Music Playlist",
            description=desc,
            color=discord.Color.red(),
        )
        embed.set_thumbnail(url="https://upload.wikimedia.org/wikipedia/commons/d/d8/YouTubeMusic_Logo.png")
        embed.timestamp = datetime.now()
        for music in upcoming:
            embed.add_field(
                name=f"{music['title']} - {music['duration']}",
                value=f"{music['webpage_url']}",
                inline=False,
            )
        if self.playlist:
            with suppress(discord.HTTPException, discord.NotFound):
                await self.playlist.delete()
        self.playlist = await ctx.send(embed=embed)
        await self.now(ctx)

    @queue.error
    async def queue_error(self, ctx, error):
        """Errors related to `queue` command."""
        if isinstance(error, commands.NoPrivateMessage):
            with suppress(discord.HTTPException):
                return await ctx.send("This command can not be used in Private Messages.")
        if isinstance(error, commands.MissingPermissions):
            return await ctx.send("ERROR: You don't have the right permissions to do that")
        return await ctx.send(f"ERROR: {error}")

    @commands.command(name="stop", aliases=["stp"], help="To make the bot leave the voice channel")
    @commands.has_role(MUSIC_ROLE)
    @commands.guild_only()
    async def stop(self, ctx):
        """Stop command."""
        with suppress(discord.HTTPException, discord.NotFound):
            await ctx.message.delete()
        await self.cleanup(ctx.guild)
        await ctx.send(f"{ctx.author.name} stopped the Music player")

    @stop.error
    async def stop_error(self, ctx, error):
        """Errors related to `stop` command."""
        if isinstance(error, commands.NoPrivateMessage):
            with suppress(discord.HTTPException):
                return await ctx.send("This command can not be used in Private Messages.")
        if isinstance(error, commands.MissingPermissions):
            return await ctx.send("ERROR: You don't have the right permissions to do that")
        return await ctx.send(f"ERROR: {error}")

    @pause.before_invoke
    async def ensure_playing(self, ctx):
        """Ensure bot is connected and playing a music."""
        await self.ensure_voice(ctx)
        if not ctx.voice_client.is_playing():
            raise commands.CommandError("Bot is not playing a music.")

    @search.before_invoke
    @play.before_invoke
    @resume.before_invoke
    @skip.before_invoke
    @queue.before_invoke
    @stop.before_invoke
    async def ensure_voice(self, ctx) -> None:
        """Ensure bot is connected to a channel before playing a music."""
        if ctx.voice_client is not None and ctx.voice_client.is_connected():
            return
        if ctx.author.voice:
            await ctx.author.voice.channel.connect()
            return
        raise commands.CommandError(f"{ctx.author.name} not connected to a voice channel.")
