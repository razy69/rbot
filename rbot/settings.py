# Built-in modules
from functools import lru_cache

# External modules
from pydantic import BaseSettings


class Settings(BaseSettings):
    """Settings of Application."""

    name: str = "Rbot"
    debug: bool = False

    class Config:
        """Configuration of Settings."""

        env_prefix = "rbot_"


@lru_cache()
def get_settings() -> Settings:
    """Return the current application setting."""
    return Settings()
