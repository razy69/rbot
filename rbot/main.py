#!/usr/bin/env python3

# External modules
import discord

# Internal modules
import rbot.utils as utils
from rbot.bot import Rbot


LOGGER = utils.get_logger()

try:
    CONFIG = utils.get_config()
except Exception as _err:
    LOGGER.error(f"! Failed to get config: {_err}")
    exit(1)


def main():
    token = CONFIG.get("discord_token", "")
    if not token:
        LOGGER.error(f"! Token is empty")
        exit(1)
    try:
        bot = Rbot(config=CONFIG, logger=LOGGER)
        bot.setup()
        LOGGER.info(f"Dir: {dir(bot)}")
        LOGGER.info(f"Type: {type(bot)}")
        bot.run(token)
    except discord.errors.LoginFailure as _error:
        LOGGER.error(f"! Failed to run bot: Authentication failure, check your token ({_error})")
    except discord.errors.PrivilegedIntentsRequired as _error:
        LOGGER.error(f"! Failed to run bot: It doesn't have intents privileges explicitly enabled ({_error})")


if __name__ == "__main__":
    main()
