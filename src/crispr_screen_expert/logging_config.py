"""Logging configuration using loguru."""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:  # pragma: no cover - typing aid
    from loguru import Logger

from .config import get_settings


def _configure_logger() -> None:
    settings = get_settings()
    log_level = os.getenv("LOG_LEVEL", "INFO")
    logger.remove()
    logger.add(sys.stderr, level=log_level)
    logfile = settings.logs_dir / "crispr_studio.log"
    logger.add(logfile, level=log_level, rotation="1 week", retention="4 weeks")


@lru_cache(1)
def get_logger(name: str = "crispr_studio") -> "Logger":
    _configure_logger()
    return logger.bind(context=name)
