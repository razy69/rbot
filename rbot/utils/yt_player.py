# Built-in modules
import asyncio
from functools import partial

# External modules
import discord
import youtube_dl

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
    "source_address": "0.0.0.0",  # nosec
}
ffmpeg_options = {
    "executable": "/usr/bin/ffmpeg",
    "options": "-vn",
}
ytdl = youtube_dl.YoutubeDL(ytdl_format_options)


class YTDLSource(discord.PCMVolumeTransformer):
    """Create a discord.PCMVolumeTransformer using youtube_dl."""

    def __init__(self, source, data, requester):
        super().__init__(source)
        self.requester = requester
        self.title = data.get("title")
        self.web_url = data.get("webpage_url")
        # YTDL info dicts (data) have other useful information you might want
        # https://github.com/rg3/youtube-dl/blob/master/README.md

    def __getitem__(self, item: str):
        """Allows us to access attributes similar to a dict.

        This is only useful when you are NOT downloading.
        """
        return self.__getattribute__(item)

    @classmethod
    async def create_source(cls, ctx, search: str, loop):
        """Add `search` url to queue."""
        loop = loop or asyncio.get_event_loop()
        to_run = partial(ytdl.extract_info, url=search, download=False)
        data = await loop.run_in_executor(None, to_run)
        if "entries" in data:
            # take first item from a playlist
            data = data["entries"][0]
        await ctx.send(f'```ini\n[Added {data["title"]} to the Queue.]\n```')
        return {"webpage_url": data["webpage_url"], "requester": ctx.author, "title": data["title"]}

    @classmethod
    async def regather_stream(cls, data, loop):
        """Used for preparing a stream.

        Since Youtube Streaming links expire.
        """
        loop = loop or asyncio.get_event_loop()
        requester = data["requester"]
        to_run = partial(ytdl.extract_info, url=data["webpage_url"], download=False)
        data = await loop.run_in_executor(None, to_run)
        return cls(discord.FFmpegPCMAudio(data["url"]), data=data, requester=requester)
