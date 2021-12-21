#!/usr/bin/env python3

# Built-in modules
import logging

# External modules
import discord
from rich.logging import RichHandler

# Internal modules
import rbot.utils as utils
from rbot.bot import Rbot
from rbot.settings import get_settings


def _init_logger(lvl: int = logging.INFO, fmt: str = "%(message)s", date_fmt: str = "[%x]") -> None:
    logging.basicConfig(level=lvl, format=fmt, datefmt=date_fmt, handlers=[RichHandler(rich_tracebacks=True)])


def _get_token(config: dict) -> str:
    token = config.get("discord_token", "")
    if not token:
        raise ValueError("Token is empty")
    return token


def _get_config():
    try:
        config = utils.get_config()
    except Exception as err:
        raise ValueError("Failed to get config") from err
    else:
        return config


def main():
    settings = get_settings()
    _init_logger(lvl=logging.DEBUG) if settings.debug else _init_logger(lvl=logging.INFO)
    logger = logging.getLogger("rich")
    logger.info("Starting application..")
    config = _get_config()
    token = _get_token(config)
    try:
        bot = Rbot(config=config, logger=logger)
        bot.setup()
        bot.run(token)
    except discord.errors.LoginFailure as _error:
        logger.error(f"Failed to run bot: Authentication failure, check your token ({_error})")
    except discord.errors.PrivilegedIntentsRequired as _error:
        logger.error(f"Failed to run bot: It doesn't have intents privileges explicitly enabled ({_error})")


if __name__ == "__main__":
    main()
