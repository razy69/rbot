# Built-in modules
import asyncio
import io
from datetime import datetime, timedelta
from functools import partial
from typing import Union

# External modules
import discord
import pytz
import youtube_dl
from discord.ext import commands
from tenacity import retry, retry_if_exception_type

TZ = pytz.timezone("Europe/Paris")

# Suppress noise about console usage from errors
youtube_dl.utils.bug_reports_message = lambda: ""
ytdl_format_options = {
    "format": "bestaudio/best",
    "outtmpl": "%(extractor)s-%(id)s-%(title)s.%(ext)s",
    "restrictfilenames": True,
    "noplaylist": True,
    "nocheckcertificate": True,
    "ignoreerrors": False,
    "logtostderr": False,
    "quiet": True,
    "no_warnings": True,
    "default_search": "auto",
    "retries": 10,
    "source_address": "0.0.0.0",  # nosec
}
ffmpeg_options = {
    "executable": "/usr/bin/ffmpeg",
    "options": "-vn",
}
ytdl = youtube_dl.YoutubeDL(ytdl_format_options)


class YTDLSource(discord.PCMVolumeTransformer):
    """Create a discord.PCMVolumeTransformer using youtube_dl."""

    def __init__(self, source: Union[str, io.BufferedIOBase], data: dict, requester: str):
        super().__init__(source)
        self.webpage_url: str = data.get("webpage_url", "")
        self.requester: str = requester
        self.title: str = data.get("title", "")
        self.duration: str = str(timedelta(seconds=data.get("duration", 0)))
        self.duration_sec: int = int(data.get("duration", 0))
        self.thumbnail: str = data.get("thumbnail", "")
        # YTDL info dicts (data) have other useful information you might want
        # https://github.com/rg3/youtube-dl/blob/master/README.md

    def __getitem__(self, item: str):
        """Allows us to access attributes similar to a dict.

        This is only useful when you are NOT downloading.
        """
        return self.__getattribute__(item)

    @classmethod
    async def create_source(cls, ctx: commands.Context, url: str, loop: asyncio.AbstractEventLoop) -> dict:
        """Add `search` url to queue."""
        loop = loop or asyncio.get_event_loop()
        to_run = partial(ytdl.extract_info, url=url, download=False)
        data = await loop.run_in_executor(None, to_run)
        if "entries" in data:
            # take first item from a playlist
            data = data["entries"][0]
        title = data.get("title", "no_title")
        _url = data.get("webpage_url", "no_url")
        duration = str(timedelta(seconds=data.get("duration", 0)))
        duration_sec: int = int(data.get("duration", 0))
        thumbnail = data.get("thumbnail", "no_thumbnail")
        embed = discord.Embed(
            title=f"Music added by {ctx.author}",
            description=f"[{title}]({_url}) - {duration}",
            color=discord.Color.blue(),
        )
        embed.set_thumbnail(url=thumbnail)
        embed.timestamp = datetime.now(tz=TZ)
        await ctx.send(embed=embed)
        return {
            "url": _url,
            "requester": ctx.author,
            "title": title,
            "duration": duration,
            "duration_sec": duration_sec,
            "thumbnail": thumbnail,
        }

    @classmethod
    @retry(retry=retry_if_exception_type(Exception))
    async def regather_stream(cls, data: dict, loop: asyncio.AbstractEventLoop) -> "YTDLSource":
        """Used for preparing a stream.

        Since Youtube Streaming links expire.
        """
        loop = loop or asyncio.get_event_loop()
        requester = data.get("requester", "no_requester")
        to_run = partial(ytdl.extract_info, url=data.get("url", "no_url"), download=False)
        data = await loop.run_in_executor(None, to_run)
        return cls(
            source=discord.FFmpegPCMAudio(data.get("url", "no_url")),
            data=data,
            requester=requester,
        )
