from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from .config import Config
from .utils import ensure_dir


def setup_logger(cfg: Config) -> logging.Logger:
    ensure_dir(cfg.log_dir)
    logger = logging.getLogger("whisper-worker")
    logger.setLevel(getattr(logging, cfg.log_level.upper(), logging.INFO))
    logger.propagate = False

    for h in list(logger.handlers):
        logger.removeHandler(h)

    fmt = logging.Formatter(
        fmt="%(asctime)s %(levelname)s %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        cfg.log_dir / "worker.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(fmt)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger
