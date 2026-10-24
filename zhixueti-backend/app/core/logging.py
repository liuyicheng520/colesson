"""Logging configuration."""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging(debug: bool = False) -> None:
    log_dir = Path("logs")
    try:
        log_dir.mkdir(exist_ok=True)
    except OSError:
        pass

    level = logging.DEBUG if debug else logging.INFO
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    root.addHandler(console)

    try:
        file_handler = RotatingFileHandler(
            log_dir / "edunexus.log",
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
    except OSError as e:
        # 宝塔/www 用户无写权限时不阻断启动，仅控制台日志
        root.warning("file logging disabled: %s", e)
