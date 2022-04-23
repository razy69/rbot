# Builtin modules
import asyncio
import itertools
import logging
import re
import traceback
from contextlib import suppress
from datetime import datetime
from typing import Optional

# External modules
import discord
import pytz
import youtube_dl
from async_timeout import timeout
from discord.ext import commands
from retrying import retry
from youtubesearchpython import VideosSearch

# Internal modules
from rbot.bot.commands.base import Base
from rbot.utils.settings import get_settings
from rbot.utils.yt_player import YTDLSource

MUSIC_ROLE = get_settings().music_role
YT_URL_RE = re.compile("^http(|s)://(www|m|).youtu(.be|be.com)/watch.+$")
TZ = pytz.timezone("Europe/Paris")
EMOJI_NUMBERS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]


def retry_if_exception(exception):
    """Retry if compat_HTTPError is raised."""
    return isinstance(exception, youtube_dl.compat.compat_HTTPError)


class MusicPlayer(commands.Cog):
    """A class which is assigned to each guild using the bot for Music.

    This class implements a queue and loop, which allows for different guilds to listen to different playlists
    simultaneously.
    When the bot disconnects from the Voice it's instance will be destroyed.
    """

    def __init__(self, ctx: commands.Context, logger: logging.Logger):
        self.logger = logger
        self.bot: commands.Bot = ctx.bot
        self._guild: discord.Guild = ctx.guild
        self._channel: discord.TextChannel = ctx.channel
        self._cog: commands.Cog = ctx.cog
        self.queue: asyncio.Queue = asyncio.Queue()
        self.next: asyncio.Event = asyncio.Event()
        self.np: Optional[discord.Message] = None  # Now playing message
        self.volume: int = 1
        self.current: Optional[YTDLSource] = None
        self.player_is_paused = False
        self.bot.loop.create_task(self.player_loop())

    def player_embed(self, title: str = "Now Playing", color: discord.Color = None) -> Optional[discord.Embed]:
        """Return a player embed, to be send in a discord.TextChannel."""
        if not color:
            color = discord.Color.green()
        source = self.current
        if not source:
            return None
        embed = discord.Embed(
            title=title,
            description=f"[{source.title}]({source.webpage_url}) - {source.duration}",
            color=color,
        )
        upcoming = self.get_queue()
        if upcoming:
            embed.add_field(
                name="____",
                value="Next songs:",
                inline=False,
            )
            for i, music in enumerate(upcoming):
                embed.add_field(
                    name=f"{EMOJI_NUMBERS[i]} {music['title']} - {music['duration']}",
                    value=f"{music['webpage_url']}",
                    inline=False,
                )
        embed.set_thumbnail(url=source.thumbnail)
        embed.timestamp = datetime.now(tz=TZ)
        return embed

    def player_components(self) -> list:
        """Button for the player."""
        return [
            discord.ActionRow(
                discord.Button(
                    label="Play",
                    custom_id="player_play_button",
                    style=discord.ButtonStyle.green,
                ).disable_if(not self.player_is_paused),
                discord.Button(
                    label="Pause",
                    custom_id="player_pause_button",
                    style=discord.ButtonStyle.grey,
                ).disable_if(self.player_is_paused),
                discord.Button(
                    label="Stop",
                    custom_id="player_stop_button",
                    style=discord.ButtonStyle.red,
                ),
                discord.Button(
                    label="Next",
                    custom_id="player_next_button",
                    style=discord.ButtonStyle.blurple,
                ).disable_if(not self.get_queue()),
            ),
        ]

    async def now_playing(self) -> None:
        """Send a discord.Message with a player and update self.np with that message."""
        source = self.current
        if not source:
            return
        await self.bot.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.listening,
                name=f"🎵 {source.title} 🎵",
            ),
        )
        if isinstance(self.np, discord.Message):
            with suppress(discord.HTTPException, discord.NotFound):
                await self.np.delete()
        embed = self.player_embed()
        if not embed:
            return
        components = self.player_components()
        self.np = await self._channel.send(embed=embed, components=components)

    async def player_loop(self) -> None:
        """Main player loop."""
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            source: Optional[YTDLSource] = None
            self.next.clear()
            if not self.current:
                try:
                    # Wait for the next song. If we timeout cancel the player and disconnect...
                    async with timeout(300):
                        source = await self.queue.get()
                except asyncio.TimeoutError:
                    self.logger.info("Player destroyed because no music to player for more than 10s")
                    self.destroy(self._guild)
                    return
            if not isinstance(source, YTDLSource):
                try:
                    source = await YTDLSource.regather_stream(source, self.bot.loop)
                except Exception as err:
                    self.logger.error("Exception in player_loop: %s", traceback.format_exc())
                    await self._channel.send(f"There was an error processing your song.\n" f"```css\n[{err}]\n```")
                    continue
            source.volume = self.volume
            self.current = source
            self._guild.voice_client.play(source, after=lambda _: self.bot.loop.call_soon_threadsafe(self.next.set))
            await self.now_playing()
            await self.next.wait()
            # Make sure the FFmpeg process is cleaned up.
            source.cleanup()
            self.current = None
            await self.bot.change_presence(status=discord.Status.idle)
            if isinstance(self.np, discord.Message):
                with suppress(discord.HTTPException, discord.NotFound):
                    # We are no longer playing this song...
                    await self.np.delete()

    def pause(self) -> None:
        """Pause the music player."""
        if self._guild.voice_client.is_paused():
            return
        self._guild.voice_client.pause()
        self.player_is_paused = True

    def resume(self) -> None:
        """Resume the paused music player."""
        if not self._guild.voice_client.is_paused():
            return
        self._guild.voice_client.resume()
        self.player_is_paused = False

    def next_song(self) -> None:
        """Skip the current song."""
        self._guild.voice_client.stop()

    def stop(self) -> None:
        """Destroy the current player."""
        self.destroy(self._guild)

    def get_queue(self) -> list:
        """Return the list of next musics from the Asyncio Queue."""
        queue = getattr(self.queue, "_queue", None)
        if self.queue.empty() or not queue:
            return []
        return list(itertools.islice(queue, 0, 9))

    def destroy(self, guild: discord.Guild) -> asyncio.Task:
        """Disconnect and cleanup the player."""
        return self.bot.loop.create_task(self._cog.cleanup(guild))


class Music(Base):
    """Rbot Music stream music to a chan from youtube."""

    def __init__(self, bot: commands.Bot):  # noqa:D107
        super().__init__()
        self.bot: commands.Bot = bot
        self.player: Optional[MusicPlayer] = None

    def get_player(self, ctx: commands.Context) -> MusicPlayer:
        """Retrieve the guild player, or generate one."""
        if not self.player:
            self.player = MusicPlayer(ctx, self.logger)
        return self.player

    async def cleanup(self, guild: discord.Guild):
        """Cleanup bot, disconnect it and properly remove player."""
        self.logger.info("Cleanup Music Player")
        await self.bot.change_presence(status=discord.Status.idle)
        if isinstance(self.player, MusicPlayer) and isinstance(self.player.np, discord.Message):
            with suppress(discord.HTTPException, discord.NotFound):
                await self.player.np.delete()
        if isinstance(self.player, MusicPlayer):
            self.player = None
        if isinstance(guild.voice_client, discord.VoiceProtocol):
            await guild.voice_client.disconnect()

    def is_invoked_in_music_chan(ctx: commands.Context) -> bool:  # noqa: N805
        """Check if command has been invoked in the right chan."""
        if ctx.message.channel.name != ctx.bot.settings.music_chan:
            raise commands.UserInputError(f"You have to run command in the {ctx.bot.settings.music_chan} channel")
        return True

    def gen_yt_select_menu(self, search: str) -> discord.SelectMenu:
        """Generate a discord.SelectMenu using Youtube search results from youtubesearchpython."""
        videos_search = VideosSearch(search, limit=10).result()
        videos_search = videos_search.get("result", [])
        results = [
            discord.SelectOption(
                label=f"{video.get('title', '')}"[:25],
                description=f"{video.get('duration', '')} - {video.get('publishedTime', '')} - {video.get('viewCount', {}).get('short', '')} - {video.get('channel', {}).get('name')}"[  # noqa: E501
                    :50  # noqa: C812
                ],
                value=video.get("link", ""),
                emoji=EMOJI_NUMBERS[i],
            )
            for i, video in enumerate(videos_search)
        ]
        results.append(
            discord.SelectOption(
                label="Quit",
                description="Stop your current search",
                value="_quit",
                emoji="❌",
            ),
        )
        return discord.SelectMenu(
            custom_id="select_yt_result",
            options=results,
            placeholder="Select a song",
            max_values=1,
            min_values=1,
        )

    @retry(retry_on_exception=retry_if_exception)
    async def youtube_dl_source(
        self,
        ctx: commands.Context,
        search: str,
        loop: asyncio.AbstractEventLoop,
    ) -> dict:
        """Stream Music from search url."""
        return await YTDLSource.create_source(ctx, search, loop)

    @commands.command(
        name="play",
        aliases=["yt", "p", "pl", "s", "search"],
        help="Search a music from Youtube and play it, or use direct url instead of search !",
    )
    @commands.check(is_invoked_in_music_chan)
    @commands.has_role(MUSIC_ROLE)
    @commands.guild_only()
    async def play_music(self, ctx: commands.Context, search: str, *args) -> None:
        """
        Play the given youtube search.

        Args:
            ctx (context): discord.ext.commands.Context
            search (str): a text to search a Youtube video.
        """
        _args = [arg for arg in args]  # noqa: C416
        if _args:
            search = f"{search.strip()} {' '.join(_args)}"
        if not YT_URL_RE.match(search):
            self.logger.info("Search query: %s", search)
            select_songs = self.gen_yt_select_menu(search)
            msg_with_selects = await ctx.reply(
                title=f"Youtube search results for {search}:",
                components=[[select_songs]],
            )

            def check_selection(i: discord.Interaction, button):
                return i.author == ctx.author and i.message == msg_with_selects

            _, select_menu = await self.bot.wait_for("selection_select", check=check_selection)
            with suppress(discord.HTTPException, discord.NotFound):
                await msg_with_selects.delete()
            if select_menu.values[0] == "_quit":
                return
            search = select_menu.values[0]
        with suppress(discord.HTTPException, discord.NotFound):
            await ctx.message.delete()
        player = self.get_player(ctx)
        source = await self.youtube_dl_source(ctx, search, self.bot.loop)
        if not source:
            return
        await player.queue.put(source)
        if isinstance(player.np, discord.Message):
            with suppress(discord.HTTPException, discord.NotFound):
                await player.np.delete()
            await player.now_playing()
        with suppress(asyncio.TimeoutError):
            await self.bot.wait_for("player_play_button", timeout=1)
            await self.bot.wait_for("player_pause_button", timeout=1)
            await self.bot.wait_for("player_stop_button", timeout=1)
            await self.bot.wait_for("player_next_button", timeout=1)

    @commands.Cog.on_click(custom_id="player_play_button")
    async def player_play(self, i: discord.Interaction, button) -> None:
        """Action when Play button is triggered."""
        await i.defer()
        if not self.player:
            return
        self.player.resume()
        embed = self.player.player_embed()
        if not embed:
            return
        components = self.player.player_components()
        await i.edit(embed=embed, components=components)

    @commands.Cog.on_click(custom_id="player_pause_button")
    async def player_pause(self, i: discord.Interaction, button) -> None:
        """Action when Pause button is triggered."""
        await i.defer()
        if not self.player:
            return
        self.player.pause()
        embed = self.player.player_embed(title="Music Paused", color=discord.Color.light_grey())
        if not embed:
            return
        components = self.player.player_components()
        await i.edit(embed=embed, components=components)

    @commands.Cog.on_click(custom_id="player_stop_button")
    async def player_stop(self, i: discord.Interaction, button) -> None:
        """Action when Stop button is triggered."""
        await i.defer()
        if not self.player:
            return
        self.player.stop()

    @commands.Cog.on_click(custom_id="player_next_button")
    async def player_next(self, i: discord.Interaction, button) -> None:
        """Action when Next button is triggered."""
        await i.defer()
        if not self.player:
            return
        self.player.next_song()
        embed = self.player.player_embed()
        if not embed:
            return
        components = self.player.player_components()
        await i.edit(embed=embed, components=components)

    @play_music.error
    async def play_music_error(self, ctx: commands.Context, error: Exception) -> discord.Message:
        """Errors related to `play_music` command."""
        self.logger.error("Exception in play_music: %s", traceback.format_exc())
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

    @play_music.before_invoke
    async def ensure_voice(self, ctx: commands.Context) -> None:
        """Ensure bot is connected to a channel before playing a music."""
        if ctx.voice_client is not None and ctx.voice_client.is_connected():
            return
        if ctx.author.voice:
            await ctx.author.voice.channel.connect()
            return
        raise commands.CommandError(f"{ctx.author.name} not connected to a voice channel.")
