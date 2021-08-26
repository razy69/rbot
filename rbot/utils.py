#!/usr/bin/env python3
import logging

from rich.logging import RichHandler
import yaml


def get_config(path: str = "../rbot-config.yaml") -> dict:
    with open(path, "r+") as _file:
        return yaml.safe_load(_file)


def get_logger(lvl: str = "INFO", fmt: str = "%(message)s", date_fmt: str = "[%x]") -> logging.Logger:
    # noinspection PyArgumentList
    logging.basicConfig(
        level=lvl,
        format=fmt,
        datefmt=date_fmt,
        handlers=[RichHandler(rich_tracebacks=True)]
    )
    return logging.getLogger("rich")
