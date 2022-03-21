# Built-in modules
from functools import lru_cache

# External modules
from pydantic import BaseSettings


class Settings(BaseSettings):
    """Settings of Application."""

    name: str = "Rbot"
    debug: bool = False
    discord_token: str = ""
    discord_server: str = ""
    status_chan: str = "général"
    music_chan: str = "music"
    command_prefix: str = "!"

    class Config:
        """Configuration of Settings."""

        env_prefix = "rbot_"
        env_file = ".config"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Return the current application setting."""
    return Settings()
