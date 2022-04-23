#!/usr/bin/env python3

# Built-in modules
import logging

# External modules
from rich.logging import RichHandler

# Internal modules
from rbot.bot.bot import start_bot
from rbot.utils.settings import get_settings


def _init_logger(lvl: int = logging.INFO, fmt: str = "%(message)s", date_fmt: str = "[%Y-%m-%d %H:%M:%S]") -> None:
    logging.basicConfig(level=lvl, format=fmt, datefmt=date_fmt, handlers=[RichHandler(rich_tracebacks=True)])


def main() -> None:
    settings = get_settings()
    _init_logger(lvl=logging.DEBUG) if settings.debug else _init_logger(lvl=logging.INFO)
    logger = logging.getLogger("rich")
    logger.info("Starting application..")
    logger.debug("%s", settings)
    start_bot()


if __name__ == "__main__":
    main()
